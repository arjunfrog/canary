import json
import shutil

import pytest

from canary import analyze, audit, cli, config, evidence, leaks, seed, worker
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import fake_paper_text, leak_text
from canary.vault import Vault

PASSPHRASE = "a long test passphrase"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x05" * 64


@pytest.fixture
def world(conn):
    config.ensure_home()
    vault = Vault.create(config.vault_path(), PASSPHRASE)
    key = bytes.fromhex(vault.get("fingerprint_key"))
    seed.seed(conn)
    bank = load_bank()
    translator, printed = fp.render_translator_copy(key, 1, 23, bank), fp.render_print_copy(key, 1, 4821, bank)
    first_trap = next(i for i, r in enumerate(translator) if r.is_trap)      # the key is random, so find where a trap landed
    ids = {
        "traced": leaks.add_manual_leak(conn, text=leak_text(translator[:14])),
        "lead": leaks.add_manual_leak(conn, text=leak_text(translator[20:26], options=False)),
        "few": leaks.add_manual_leak(conn, text=leak_text(translator[20:24], options=False)),
        "fake": leaks.add_manual_leak(conn, text=fake_paper_text()),
        "print": leaks.add_manual_leak(conn, text=leak_text(printed[:14])),
        "print_wide": leaks.add_manual_leak(conn, text=leak_text(printed[:30])),
        "bio": leaks.add_manual_leak(conn, text=leak_text(translator[first_trap - 10:first_trap + 20])),
    }
    conn.execute("""UPDATE leaks SET source = 'telegram', chat_title = 'Exam leaks demo', chat_username = 'examleaks_demo',
                    chat_id = -100123, message_id = 41, message_url = 'https://t.me/examleaks_demo/41',
                    sender_name = 'Paper Seller', sender_username = 'paper_seller', sender_id = 777 WHERE id = ?""", (ids["traced"],))
    conn.commit()
    while worker.process_next(conn, lambda c, leak: analyze.analyze_leak(c, leak, key, None, bank)):
        pass
    cases = {name: (conn.execute("SELECT id FROM cases WHERE leak_id = ?", (leak_id,)).fetchone() or [None])[0]
             for name, leak_id in ids.items()}
    return conn, vault, cases


def failed(checks):
    return [name for name, ok in checks if not ok]


def test_a_traced_case_gets_a_signed_manifest_that_verifies(world):
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["traced"])
    folder = config.home() / "evidence" / f"case-{cases['traced']}"
    assert path == folder / "manifest.json"
    assert sorted(p.name for p in folder.iterdir()) == ["leak.txt", "manifest.json", "manifest.sig", "public_key.pem"]
    data = json.loads(path.read_text())
    assert data["source"]["chat"] == "Exam leaks demo" and data["source"]["message_link"] == "https://t.me/examleaks_demo/41"
    assert data["source"]["sender_name"] == "Paper Seller" and data["source"]["posted_at"]
    assert (data["verdict"], data["kind"], data["stage"], data["copy_no"], data["notice"]) == ("traced", "traced", "translation", 23, None)
    assert data["statement"] == "This is a lead for investigators, not a finding of guilt."
    assert data["reader"] == "typed text" and data["code_version"] and data["exam"]["synthetic"] is True
    assert len(data["clues"]) == 28 and data["score"]["clues_matched"] == 28 and data["score"]["candidates"] == 50
    assert data["score"]["expected_false_matches"] < 1e-6 and "Poisson-binomial" in data["score"]["how_computed"]
    assert data["custody"]["verifies"] is True and len(data["custody"]["events"]) == 3
    assert all(len(e["event_hash"]) == 64 for e in data["custody"]["events"])
    checks = evidence.verify_file(path)
    assert len(checks) >= 10 and failed(checks) == []
    last = conn.execute("SELECT action, detail FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    assert last["action"] == "evidence issued" and json.loads(last["detail"])["case_id"] == cases["traced"]


def test_the_manifest_holds_no_secrets_and_no_real_values(world):
    conn, vault, cases = world
    folder = evidence.build_evidence(conn, vault, cases["traced"]).parent
    everything = b"".join(p.read_bytes() for p in folder.iterdir())
    for secret in ("fingerprint_key", "signing_key"):
        assert vault.get(secret).encode() not in everything and bytes.fromhex(vault.get(secret)) not in everything
    bank = load_bank()
    manifest = (folder / "manifest.json").read_text()
    assert not any(q.real.stem in manifest for q in bank.paper if q.kind == "numeric")
    assert not any(q.stem in manifest for q in bank.reserves)


def test_a_strong_lead_file_is_clearly_marked_as_a_lead(world):
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["lead"])
    data = json.loads(path.read_text())
    assert data["kind"] == "lead" and data["verdict"] == "strong_lead" and data["notice"].startswith("LEAD ONLY")
    assert data["score"]["bar"] == 1e-3 and failed(evidence.verify_file(path)) == []


def test_no_evidence_file_unless_a_copy_is_named(world):
    conn, vault, cases = world
    for name in ("few", "fake"):
        with pytest.raises(evidence.NoEvidence):
            evidence.build_evidence(conn, vault, cases[name])
    with pytest.raises(evidence.NoEvidence):
        evidence.build_evidence(conn, vault, 99999)
    assert not (config.home() / "evidence" / f"case-{cases['few']}").exists()


def test_changing_any_byte_makes_verification_fail(world):
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["traced"])
    original = path.read_bytes()
    step = max(1, len(original) // 60)
    for at in list(range(0, len(original), step)) + [len(original) - 1]:
        changed = bytearray(original)
        changed[at] ^= 0x01
        path.write_bytes(bytes(changed))
        assert failed(evidence.verify_file(path)), f"a change at byte {at} was not noticed"
    path.write_bytes(original + b" ")
    assert failed(evidence.verify_file(path))
    path.write_bytes(original)
    assert failed(evidence.verify_file(path)) == []
    for other in ("manifest.sig", "leak.txt"):
        target = path.parent / other
        keep = target.read_bytes()
        target.write_bytes(keep[:-1] + bytes([keep[-1] ^ 0x01]))
        assert failed(evidence.verify_file(path)), other
        target.write_bytes(keep)


def test_changing_a_custody_event_makes_verification_fail(world):
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["traced"])
    data = json.loads(path.read_text())
    for field, value in (("to", "Somebody Else"), ("at", "2026-01-01T00:00:00+00:00"), ("to_id", 1), ("note", "Never handed over")):
        edited = json.loads(json.dumps(data))
        edited["custody"]["events"][1][field] = value
        path.write_text(json.dumps(edited, indent=2, ensure_ascii=False, sort_keys=True))
        assert "The signature matches the manifest, byte for byte" in failed(evidence.verify_file(path))

    # an insider who edits the handover log in the database before the file is issued is caught by the chain
    conn.execute("UPDATE custody_events SET to_id = 1 WHERE copy_id = 23 AND note = 'Handed to the translator'")
    conn.commit()
    path = evidence.build_evidence(conn, vault, cases["traced"])
    bad = failed(evidence.verify_file(path))
    assert "The signature matches the manifest, byte for byte" not in bad
    assert any("Custody event 2" in name for name in bad) and "The custody chain links from first handover to last" in bad
    assert "The manifest itself says the custody chain verified when issued" in bad


def test_a_file_resigned_with_another_key_fails_the_fingerprint_check(world, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["traced"])
    real = evidence.signing_fingerprint(vault)
    assert failed(evidence.verify_file(path, expect_fingerprint=real)) == []
    forged = tmp_path / "forged"
    shutil.copytree(path.parent, forged)
    data = json.loads((forged / "manifest.json").read_text())
    data["copy_no"] = 24                                         # frame another translator
    body = json.dumps(data, indent=2, sort_keys=True).encode()
    attacker = Ed25519PrivateKey.generate()
    (forged / "manifest.json").write_bytes(body)
    (forged / "manifest.sig").write_text(attacker.sign(body).hex())
    (forged / "public_key.pem").write_bytes(attacker.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    bad = failed(evidence.verify_file(forged / "manifest.json", expect_fingerprint=real))
    assert any("expected one" in name for name in bad)
    assert any("Custody event" in name for name in bad)          # the chain is bound to the copy number too


def test_an_image_leak_is_copied_in_and_its_hash_checked(world):
    conn, vault, cases = world
    image = config.home() / "photo.png"
    image.write_bytes(PNG)
    stored, sha = leaks.save_image(PNG)
    leak_id = conn.execute("SELECT leak_id FROM cases WHERE id = ?", (cases["traced"],)).fetchone()[0]
    conn.execute("UPDATE leaks SET image_path = ?, image_sha256 = ?, raw_text = NULL WHERE id = ?", (stored, sha, leak_id))
    conn.commit()
    path = evidence.build_evidence(conn, vault, cases["traced"])
    data = json.loads(path.read_text())
    assert data["leak_file"] == "leak.png" and data["image_sha256"] == data["leak_sha256"] == sha
    assert failed(evidence.verify_file(path)) == []
    (path.parent / "leak.png").write_bytes(PNG + b"\x00")
    assert "The leak file matches its recorded hash" in failed(evidence.verify_file(path))


def test_verify_command_needs_no_passphrase_and_prints_each_check(world, monkeypatch, capsys):
    conn, vault, cases = world
    path = evidence.build_evidence(conn, vault, cases["traced"])

    def no_passphrase(prompt=""):
        raise AssertionError("verify must not ask for the passphrase")
    monkeypatch.setattr("getpass.getpass", no_passphrase)
    assert cli.main(["verify", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.count("ok  ") >= 10 and "This evidence file verifies." in out and "FAIL" not in out
    path.write_bytes(path.read_bytes().replace(b'"copy_no": 23', b'"copy_no": 32'))
    assert cli.main(["verify", str(path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL  The signature matches" in out and "does NOT verify" in out
    assert cli.main(["verify", str(path.parent / "missing.json")]) == 1


def test_evidence_command_issues_a_file(world, monkeypatch, capsys):
    conn, vault, cases = world
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    assert cli.main(["evidence", str(cases["print"])]) == 0
    out = capsys.readouterr().out
    assert "manifest.json" in out and evidence.signing_fingerprint(vault) in out
    with pytest.raises(SystemExit):
        cli.main(["evidence", str(cases["fake"])])
    assert audit.verify(conn) == (True, None)


# ---- the recommended response

def test_a_translator_leak_exposes_questions_but_never_the_real_values_and_suggests_reserves(world):
    conn, vault, cases = world
    response = evidence.response_for(conn, cases["traced"])
    assert response["stage"] == "translation" and response["exposed_count"] == 14
    assert [q["position"] for q in response["exposed"]] == list(range(1, 15))
    assert "real values were never shown" in response["summary"]
    assert response["recommendation"].startswith("Recommended, for a person to decide:") and "before printing" in response["recommendation"]
    bank = load_bank()
    reserves = [s["reserve_id"] for s in response["swaps"] if s["reserve_id"]]
    assert len(reserves) == len(set(reserves)) >= 9              # the pool has 9 numeric physics reserves
    for swap in response["swaps"]:
        if swap["reserve_id"]:
            reserve = bank.by_id[swap["reserve_id"]]
            assert reserve.is_reserve and reserve.subject == swap["subject"] == "physics"


def test_trap_questions_are_never_exposed_questions(world):
    conn, vault, cases = world
    response = evidence.response_for(conn, cases["bio"])
    bank = load_bank()
    trap_ids = {q.id for q in bank.traps}
    leak_id = conn.execute("SELECT leak_id FROM cases WHERE id = ?", (cases["bio"],)).fetchone()[0]
    seen = {json.loads(r[0]).get("bank_id") for r in conn.execute("SELECT clue FROM leak_questions WHERE leak_id = ?", (leak_id,))}
    assert seen & trap_ids, "this leak should include at least one trap"
    assert not {q["question_id"] for q in response["exposed"]} & trap_ids
    assert response["exposed_count"] == len(seen - trap_ids - {None})


def test_a_print_leak_gets_a_corrigendum_up_to_ten_percent_and_the_reserve_set_beyond(world):
    conn, vault, cases = world
    small = evidence.response_for(conn, cases["print"])
    assert small["stage"] == "print" and small["exposed_count"] == 14 and "corrigendum" in small["recommendation"]
    assert small["swaps"] == [] and "real values" in small["summary"]
    wide = evidence.response_for(conn, cases["print_wide"])
    assert wide["exposed_count"] == 30 and "reserve set" in wide["recommendation"] and "corrigendum" in wide["recommendation"]
    assert wide["recommendation"].startswith("Recommended, for a person to decide:")
    assert evidence.response_for(conn, cases["fake"]) is None
