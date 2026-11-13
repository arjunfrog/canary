"""The signed evidence file for a traced or strong-lead case, and the recommended response.

An evidence folder holds manifest.json, a detached Ed25519 signature (manifest.sig), the public key
(public_key.pem) and a copy of the leak itself. `python -m canary verify` checks all of it with no
passphrase. The manifest never contains the fingerprint key, the real values or the reserve questions.
"""
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import __version__, audit, config, db, seed
from . import fingerprint as fp
from .bank import load_bank
from .chain import GENESIS, link_hash

FORMAT = "canary-evidence-1"
STATEMENT = "This is a lead for investigators, not a finding of guilt."
LEAD_NOTICE = ("LEAD ONLY. This match is under the strong-lead bar but not the traced bar. "
               "A person must investigate before any action is taken.")
HOW = ("Every clue has a chance rate: 1/8 for a decoy value set, the share of translators holding that trap for a "
       "trap question, and 1/24 for an option order (1/6 when the last option is fixed). The copy's score is the "
       "number of clues that match it. tail is the exact probability of at least that many matches by luck "
       "(Poisson-binomial, no approximation). Expected false matches = candidate copies x tail. "
       "Traced needs at most 1e-6. Strong lead needs at most 1e-3.")
CORRIGENDUM_SHARE = 0.10


class NoEvidence(Exception):
    """This case cannot have an evidence file. The message says why."""


def case_dir(case_id: int) -> Path:
    return config.home() / "evidence" / f"case-{int(case_id)}"


def manifest_path(case_id: int) -> Path:
    return case_dir(case_id) / "manifest.json"


def _signing_key(vault) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(vault.get("signing_key")))


def key_fingerprint(public: Ed25519PublicKey) -> str:
    """A short name for a signing key: the SHA-256 of its raw bytes."""
    raw = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def signing_fingerprint(vault) -> str:
    return key_fingerprint(_signing_key(vault).public_key())


def _write(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _chance(question, kind: str, book: fp.Codebook) -> float | None:
    if kind == "value":
        return fp.CHANCE_VALUE
    if kind == "trap":
        return book.trap_share(question.id)
    return fp.order_chance(question)


def build_evidence(conn: sqlite3.Connection, vault, case_id: int) -> Path:
    """Write and sign the evidence folder for a traced or strong-lead case. Returns the manifest's path."""
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None:
        raise NoEvidence("There is no such case.")
    if case["verdict"] not in ("traced", "strong_lead") or case["copy_id"] is None:
        raise NoEvidence("An evidence file is only issued when a copy is named: for a traced case or a strong lead.")
    leak = conn.execute("SELECT * FROM leaks WHERE id = ?", (case["leak_id"],)).fetchone()
    copy = conn.execute("""SELECT c.stage, c.copy_no, p.display_name, p.role, p.organisation FROM copies c
                           LEFT JOIN people p ON p.id = c.holder_id WHERE c.id = ?""", (case["copy_id"],)).fetchone()
    exam = conn.execute("SELECT title, is_synthetic FROM exams WHERE id = ?", (config.EXAM_ID,)).fetchone()
    bank = load_bank()
    book = fp.codebook(bytes.fromhex(vault.get("fingerprint_key")), config.EXAM_ID, bank, config.N_TRANSLATORS,
                       config.N_PRINT_COPIES)
    clues = []
    for r in conn.execute("SELECT * FROM leak_questions WHERE leak_id = ? AND clue_type IS NOT NULL ORDER BY id", (leak["id"],)):
        detail = json.loads(r["clue"] or "{}")
        question = bank.by_id.get(detail.get("bank_id"))
        if question is None or detail.get("matched") is None:
            continue                                             # not a scored clue (for example, real values)
        clues.append({"question_in_leak": detail.get("number"), "bank_id": question.id, "type": r["clue_type"],
                      "chance": _chance(question, r["clue_type"], book), "matched": bool(detail["matched"])})
    events, chain_ok = seed.custody_chain(conn, case["copy_id"])
    folder = case_dir(case_id)
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)

    leak_file = None
    if leak["image_path"] and Path(leak["image_path"]).exists():
        leak_file = "leak" + Path(leak["image_path"]).suffix
        shutil.copyfile(leak["image_path"], folder / leak_file)
        os.chmod(folder / leak_file, 0o600)
    elif leak["raw_text"]:
        leak_file = "leak.txt"
        _write(folder / leak_file, leak["raw_text"].encode("utf-8"))
    lead = case["verdict"] == "strong_lead"
    manifest = {
        "format": FORMAT,
        "kind": "lead" if lead else "traced",
        "notice": LEAD_NOTICE if lead else None,
        "statement": STATEMENT,
        "case_id": case_id,
        "issued_at": db.now(),
        "code_version": __version__,
        "exam": {"title": exam["title"] if exam else None, "synthetic": bool(exam["is_synthetic"]) if exam else True},
        "source": {"kind": leak["source"], "chat": leak["chat_title"], "chat_username": leak["chat_username"],
                   "message_link": leak["message_url"], "sender_name": leak["sender_name"],
                   "sender_username": leak["sender_username"], "sender_id": leak["sender_id"],
                   "posted_at": leak["posted_at"], "received_at": leak["received_at"]},
        "leak_file": leak_file,
        "leak_sha256": hashlib.sha256((folder / leak_file).read_bytes()).hexdigest() if leak_file else None,
        "image_sha256": leak["image_sha256"],
        "reader": case["reader"],
        "verdict": case["verdict"],
        "stage": copy["stage"],
        "copy_no": copy["copy_no"],
        "issued_to": {"name": copy["display_name"], "role": copy["role"], "organisation": copy["organisation"]},
        "score": {"clues_scored": len(clues), "clues_matched": sum(c["matched"] for c in clues),
                  "candidates": config.N_TRANSLATORS if copy["stage"] == "translation" else config.N_PRINT_COPIES,
                  "expected_false_matches": case["expected_false_matches"],
                  "bar": fp.STRONG_LEAD_BAR if lead else fp.TRACED_BAR, "how_computed": HOW},
        "clues": clues,
        "custody": {"verifies": chain_ok, "events": [
            {"at": e["at"], "note": e["note"], "from_id": e["from_id"], "to_id": e["to_id"], "from": e["from_name"],
             "to": e["to_name"], "to_role": e["to_role"], "to_organisation": e["to_organisation"],
             "prev_hash": e["prev_hash"], "event_hash": e["event_hash"]} for e in events]},
    }
    stored = json.loads(case["steps"] or "{}")
    if stored.get("candidates"):
        manifest["score"]["candidates"] = stored["candidates"]
    body = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
    key = _signing_key(vault)
    _write(folder / "manifest.json", body)
    _write(folder / "manifest.sig", key.sign(body).hex().encode("ascii"))
    _write(folder / "public_key.pem", key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    audit.record(conn, "evidence issued", {"case_id": case_id, "kind": manifest["kind"],
                                           "manifest_sha256": hashlib.sha256(body).hexdigest()})
    return folder / "manifest.json"


def verify_file(manifest: Path, expect_fingerprint: str | None = None) -> list[tuple[str, bool]]:
    """Check signature, hashes, custody chain and the score. Needs no passphrase. Returns (check, passed) pairs."""
    manifest = Path(manifest)
    folder, checks = manifest.parent, []
    try:
        body = manifest.read_bytes()
        public = serialization.load_pem_public_key((folder / "public_key.pem").read_bytes())
        signature = bytes.fromhex((folder / "manifest.sig").read_text(encoding="ascii").strip())
        if not isinstance(public, Ed25519PublicKey):
            raise ValueError("not an Ed25519 key")
    except (OSError, ValueError) as exc:
        return [(f"The manifest, its signature and its public key can be read ({type(exc).__name__})", False)]
    try:
        public.verify(signature, body)
        signed = True
    except InvalidSignature:
        signed = False
    checks.append(("The signature matches the manifest, byte for byte", signed))
    fingerprint = key_fingerprint(public)
    if expect_fingerprint:
        checks.append((f"The signing key is the expected one ({fingerprint[:16]}...)",
                       fingerprint == expect_fingerprint.strip().lower()))
    else:
        checks.append((f"Signing key fingerprint, to compare with the exam authority's: {fingerprint}", True))
    try:
        data = json.loads(body)
        if data.get("format") != FORMAT:
            raise ValueError("unknown format")
        leak_file = data.get("leak_file")
        if leak_file:
            target = folder / Path(leak_file).name
            same = target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == data.get("leak_sha256")
            checks.append(("The leak file matches its recorded hash", same))
            if data.get("image_sha256"):
                checks.append(("The image hash recorded when the leak arrived matches the file",
                               data["image_sha256"] == data.get("leak_sha256")))
        prev, linked = GENESIS, True
        events = data["custody"]["events"]
        for i, e in enumerate(events, start=1):
            want = link_hash(prev, seed.event_body(data["stage"], data["copy_no"], e["from_id"], e["to_id"], e["at"], e["note"]))
            ok = e["prev_hash"] == prev and e["event_hash"] == want
            checks.append((f"Custody event {i} ({e['note']}) has the right hash", ok))
            linked = linked and ok
            prev = e["event_hash"]
        checks.append(("The custody chain links from first handover to last", linked and bool(events)))
        checks.append(("The manifest itself says the custody chain verified when issued", data["custody"]["verifies"] is True))
        score = data["score"]
        chances = [c["chance"] for c in data["clues"]]
        matched = sum(1 for c in data["clues"] if c["matched"])
        expected = fp.expected_false_matches(score["candidates"], chances, matched)
        recorded = score["expected_false_matches"]
        checks.append(("The expected false matches can be recomputed from the clues",
                       matched == score["clues_matched"] and abs(expected - recorded) <= 1e-9 * max(expected, recorded, 1e-300) + 1e-300))
        checks.append((f"The score is under the bar for a {data['kind']} file", recorded <= score["bar"]
                       and fp.verdict_for(recorded) == data["verdict"]))
        checks.append(("The file carries the investigators' statement", data.get("statement") == STATEMENT
                       and (data["kind"] != "lead" or data.get("notice") == LEAD_NOTICE)))
    except (ValueError, KeyError, TypeError) as exc:
        checks.append((f"The manifest has the expected contents ({type(exc).__name__})", False))
    return checks


def response_for(conn: sqlite3.Connection, case_id: int) -> dict | None:
    """Exposed questions, suggested reserves, and a recommendation for a person to decide.

    Exposed questions are the real questions the leak shows. Trap questions are never exposed questions:
    they were never going to be in the exam.
    """
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None or case["verdict"] == "not_our_paper":
        return None
    bank = load_bank()
    exposed, seen = [], set()
    for r in conn.execute("SELECT clue FROM leak_questions WHERE leak_id = ? ORDER BY id", (case["leak_id"],)):
        question = bank.by_id.get(json.loads(r["clue"] or "{}").get("bank_id"))
        if question is None or question.kind == "trap" or question.position is None or question.id in seen:
            continue
        seen.add(question.id)
        exposed.append(question)
    exposed.sort(key=lambda q: q.position)
    paper = len(bank.paper)
    out = {"stage": case["stage"], "paper_size": paper, "exposed_count": len(exposed),
           "exposed": [{"position": q.position, "question_id": q.id, "subject": q.subject, "difficulty": q.difficulty,
                        "topic": q.topic} for q in exposed],
           "swaps": [], "summary": "", "recommendation": ""}
    if not exposed:
        out["summary"] = "No real question from the paper was recognised in this leak."
        out["recommendation"] = "Nothing to replace. A person should still look at the leak."
        return out
    count = f"{len(exposed)} of the {paper} real questions" if len(exposed) > 1 else f"1 of the {paper} real questions"
    if case["stage"] == "translation":
        free = [q for q in bank.reserves]
        for q in exposed:
            pick = next((r for r in free if r.subject == q.subject and r.difficulty == q.difficulty and r.kind == q.kind), None) \
                or next((r for r in free if r.subject == q.subject and r.difficulty == q.difficulty), None) \
                or next((r for r in free if r.subject == q.subject), None)
            if pick is not None:
                free.remove(pick)
            out["swaps"].append({"position": q.position, "question_id": q.id, "subject": q.subject,
                                 "difficulty": q.difficulty, "reserve_id": pick.id if pick else None,
                                 "reserve_topic": pick.topic if pick else None})
        short = sum(1 for s in out["swaps"] if s["reserve_id"] is None)
        out["summary"] = (f"This leak shows {count}. It came from a translator's copy, so the real values were never "
                          "shown: the numbers in the leak are decoys, and any trap questions in it were never going to be asked.")
        out["recommendation"] = ("Recommended, for a person to decide: before printing, swap each exposed question for a "
                                 "reserve question of the same subject and difficulty."
                                 + (f" The reserve pool has no match for {short} of them." if short else ""))
    elif case["stage"] == "print":
        share = len(exposed) / paper
        out["summary"] = f"This leak shows {count} as printed, with the real values ({share:.0%} of the paper)."
        if share <= CORRIGENDUM_SHARE:
            out["recommendation"] = ("Recommended, for a person to decide: issue a corrigendum that replaces or drops these "
                                     "questions. At most 10% of the paper is exposed.")
        else:
            out["recommendation"] = ("Recommended, for a person to decide: use the reserve set. More than 10% of the paper "
                                     "is exposed, which is too much for a corrigendum.")
    else:
        out["summary"] = f"This leak shows {count}, but not enough to tell whether it came from before or after printing."
        out["recommendation"] = ("Recommended, for a person to decide: treat these questions as exposed, and look for a "
                                 "fuller version of the leak before choosing between reserves and a corrigendum.")
    return out
