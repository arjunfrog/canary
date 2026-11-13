"""The health check, reset and replay export."""
import json
import os
import secrets
import shutil
import sqlite3
import time
from pathlib import Path

from . import analyze, audit, config, db, queries
from . import fingerprint as fp
from .bank import load_bank
from .samples import fake_paper_text, leak_text

REPLAY_FORMAT = "canary-replay-1"
CHECK_QUESTIONS = 14


class CheckFailed(Exception):
    pass


def _run_leak(conn: sqlite3.Connection, key: bytes, bank, text: str, made: list[int]) -> dict:
    """Put one typed leak through the real analysis path and return what was stored. Its id is added to `made`."""
    now = db.now()
    cur = conn.execute("INSERT INTO leaks (source, raw_text, posted_at, received_at, status) VALUES ('manual', ?, ?, ?, 'reading')",
                       (text, now, now))                          # "reading", so a running app's worker leaves it alone
    conn.commit()
    leak_id = cur.lastrowid
    made.append(leak_id)
    leak = conn.execute("SELECT * FROM leaks WHERE id = ?", (leak_id,)).fetchone()
    analyze.analyze_leak(conn, leak, key, None, bank)
    row = conn.execute("""SELECT l.status, c.verdict, c.stage, c.steps, c.expected_false_matches FROM leaks l
                          LEFT JOIN cases c ON c.leak_id = l.id WHERE l.id = ?""", (leak_id,)).fetchone()
    stored = json.loads(row["steps"]) if row["steps"] else {}
    return {"status": row["status"], "verdict": row["verdict"], "stage": row["stage"],
                     "copy_no": stored.get("copy_no"), "expected": row["expected_false_matches"]}


def check(conn: sqlite3.Connection, vault, say=print) -> bool:
    """Run known leaks end to end and print PASS or FAIL. Its leaks and cases are deleted afterwards.

    A translator copy and a printed copy are picked at random each time, typed out as a leak of page 1,
    and must come back traced to exactly that copy. A fake paper must come back as not our paper.
    """
    key = bytes.fromhex(vault.get("fingerprint_key"))
    bank = load_bank()
    made, timings, started = [], [], time.monotonic()
    translator = 1 + secrets.randbelow(config.N_TRANSLATORS)
    printed = 1 + secrets.randbelow(config.N_PRINT_COPIES)
    steps = [
        (f"translator copy {translator}", lambda: leak_text(fp.render_translator_copy(key, config.EXAM_ID, translator, bank)[:CHECK_QUESTIONS]),
         {"status": "done", "verdict": "traced", "stage": "translation", "copy_no": translator}),
        (f"printed copy {printed}", lambda: leak_text(fp.render_print_copy(key, config.EXAM_ID, printed, bank)[:CHECK_QUESTIONS]),
         {"status": "done", "verdict": "traced", "stage": "print", "copy_no": printed}),
        ("fake paper", lambda: fake_paper_text(CHECK_QUESTIONS),
         {"status": "done", "verdict": "not_our_paper", "stage": None, "copy_no": None}),
    ]
    reason = None
    try:
        for name, make, want in steps:
            t0 = time.monotonic()
            got = _run_leak(conn, key, bank, make(), made)
            timings.append((name, time.monotonic() - t0))
            wrong = {k: (got[k], v) for k, v in want.items() if got[k] != v}
            if wrong:
                details = ", ".join(f"{k} was {a!r}, expected {b!r}" for k, (a, b) in wrong.items())
                raise CheckFailed(f"{name}: {details}")
            if want["verdict"] == "traced" and not got["expected"] <= fp.TRACED_BAR:
                raise CheckFailed(f"{name}: traced with expected false matches {got['expected']!r}, over the bar")
        t0 = time.monotonic()
        ok, bad = audit.verify(conn)
        timings.append(("audit chain", time.monotonic() - t0))
        if not ok:
            raise CheckFailed(f"the audit log is broken at row {bad}")
    except CheckFailed as exc:
        reason = str(exc)
    except Exception as exc:                                       # anything unexpected is a failure with its reason
        reason = f"{type(exc).__name__}: {exc}"
    finally:
        for leak_id in made:
            conn.execute("DELETE FROM leaks WHERE id = ?", (leak_id,))          # cases and leak_questions go with it
        db.scrub(conn)                                                 # a typed-out copy must not linger in the file
    total = time.monotonic() - started
    audit.record(conn, "health check", {"passed": reason is None, "reason": reason})
    for name, seconds in timings:
        say(f"  {name:24} {seconds * 1000:7.0f} ms")
    if reason is None:
        say(f"PASS  translator copy, printed copy, fake paper and audit chain, in {total:.2f} s")
        return True
    say(f"FAIL  {reason}")
    return False


def reset(conn: sqlite3.Connection) -> dict:
    """Delete leaks, cases and evidence files. Keep the exam, copies and audit log."""
    counts = {"leaks": conn.execute("SELECT count(*) FROM leaks").fetchone()[0],
              "cases": conn.execute("SELECT count(*) FROM cases").fetchone()[0], "evidence files": 0, "leak images": 0}
    conn.execute("DELETE FROM leak_questions")
    conn.execute("DELETE FROM cases")
    conn.execute("DELETE FROM leaks")
    db.scrub(conn)
    for folder, name in (("evidence", "evidence files"), ("leaks", "leak images"), ("cache", None)):
        root = config.home() / folder
        if not root.is_dir():
            continue
        for entry in list(root.iterdir()):
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            if name:
                counts[name] += 1
    audit.record(conn, "reset", counts)
    return counts


def replay_dir() -> Path:
    return config.home() / "replay"


def export_case(conn: sqlite3.Connection, case_id: int) -> Path:
    """Write one case as a replay file into CANARY_HOME/replay. The file holds everything the Case screen shows."""
    view = queries.get_case(conn, case_id)
    if view is None:
        raise LookupError(f"There is no case {case_id}.")
    config.ensure_home()
    folder = replay_dir()
    image_file = None
    if view.image_path and Path(view.image_path).is_file():
        image_file = f"case-{case_id}{Path(view.image_path).suffix}"
        shutil.copyfile(view.image_path, folder / image_file)
        os.chmod(folder / image_file, 0o600)
    data = view.to_json()
    data["image_path"], data["evidence_path"] = None, None
    out = folder / f"case-{case_id}.json"
    fd = os.open(out, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"format": REPLAY_FORMAT, "exported_at": db.now(), "image_file": image_file, "view": data}, handle,
                  ensure_ascii=False, indent=1)
    audit.record(conn, "case exported for replay", {"case_id": case_id})
    return out


def load_replay(name: str) -> queries.CaseView:
    """Read a replay file from CANARY_HOME/replay by name. Uses that file alone: no database, no network."""
    from .ui.widgets.text import when
    stem = Path(name).name                                           # a name only, never a path out of the folder
    path = replay_dir() / (stem if stem.endswith(".json") else f"{stem}.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != REPLAY_FORMAT:
            raise ValueError("not a replay file")
        view = queries.CaseView.from_json(data["view"])
    except FileNotFoundError:
        raise LookupError(f"There is no replay called {stem} in {replay_dir()}. Make one with: python -m canary export-case ID") from None
    except (ValueError, KeyError, TypeError) as exc:
        raise LookupError(f"{path.name} is not a usable replay file ({type(exc).__name__}).") from None
    image_file = data.get("image_file")
    view.image_path = str(replay_dir() / Path(image_file).name) if image_file else None
    view.evidence_path = None
    view.replay_label = f"Replay of a real run from {when(view.created_at or data.get('exported_at'))}"
    return view
