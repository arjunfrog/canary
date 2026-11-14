import secrets

import pytest

from canary import analyze, audit, cli, config, demo
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.vault import Vault

PASSPHRASE = "a long test passphrase"


def test_every_first_page_question_has_hindi_wording():
    bank = load_bank()
    first_page = [q for q in bank.paper if q.position is not None and q.position <= 14]
    assert {q.id for q in first_page} == set(demo.HINDI)
    for q in first_page:
        for value_set in q.value_sets:                        # every value appears, whatever set a copy holds
            stem = demo.HINDI[q.id].format(**value_set.params)
            assert sorted(analyze.numbers_in(stem)) == sorted(analyze.numbers_in(value_set.stem)), q.id


def test_a_typed_hindi_copy_traces_to_its_translator():
    key, bank = secrets.token_bytes(32), load_bank()
    copy_no = 1 + secrets.randbelow(config.N_TRANSLATORS)
    rendered = fp.render_translator_copy(key, config.EXAM_ID, copy_no, bank)
    text = demo.hindi_text(demo.hindi_questions(rendered[:5], bank))
    assert "विराम" in text
    result = analyze.analyse_text(text, key)
    assert result.verdict == "traced" and result.stage == "translation" and result.decoded.copy_no == copy_no


def test_prepare_clears_old_leaks_and_adds_one_of_each_verdict(conn, tmp_path):
    key = secrets.token_bytes(32)
    conn.execute("INSERT INTO leaks (source, raw_text, posted_at, received_at, status) VALUES "
                 "('manual', 'an old leak', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', 'queued')")
    conn.commit()
    made = demo.prepare(conn, key, tmp_path / "demo", paper_copy=9)
    assert made["cleared"]["leaks"] == 1
    assert conn.execute("SELECT count(*) FROM leaks WHERE raw_text = 'an old leak'").fetchone()[0] == 0
    verdicts = [leak.verdict for leak in made["leaks"]]
    assert verdicts.count("traced") == 4 and verdicts.count("strong_lead") == 1 and verdicts.count("not_our_paper") == 1
    for leak in made["leaks"]:
        assert leak.found_copy == leak.copy_no               # every named copy is the one it was made from
    used = {leak.copy_no for leak in made["leaks"] if leak.stage == "translation"}
    assert made["paper_copy"] == 9 and 9 not in used         # the paper to leak is not already traced
    names = sorted(path.name for path in made["files"])
    assert names == ["english-paper-translator-09.pdf", "hindi-paper-translator-09.pdf", "sealed-slip-translator-09.pdf"]
    for path in made["files"]:
        assert path.read_bytes().startswith(b"%PDF") and (path.stat().st_mode & 0o777) == 0o600
    assert (tmp_path / "demo").stat().st_mode & 0o777 == 0o700
    assert audit.verify(conn)[0]


def test_prepare_refuses_a_copy_number_out_of_range_before_clearing(conn, tmp_path):
    conn.execute("INSERT INTO leaks (source, raw_text, posted_at, received_at, status) VALUES "
                 "('manual', 'kept', '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', 'queued')")
    conn.commit()
    with pytest.raises(ValueError):
        demo.prepare(conn, secrets.token_bytes(32), tmp_path / "demo", paper_copy=config.N_TRANSLATORS + 1)
    assert conn.execute("SELECT count(*) FROM leaks").fetchone()[0] == 1


def test_prepare_demo_command(monkeypatch, tmp_path, capsys):
    config.ensure_home()
    Vault.create(config.vault_path(), PASSPHRASE)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    assert cli.main(["prepare-demo", "--yes", "--out", str(tmp_path / "demo"), "--paper", "3"]) == 0
    out = capsys.readouterr().out
    assert "translator copy 3" in out and "Traced" in out and "Strong lead" in out and "Not our paper" in out


def test_prepare_demo_asks_first(monkeypatch, tmp_path):
    config.ensure_home()
    Vault.create(config.vault_path(), PASSPHRASE)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert cli.main(["prepare-demo", "--out", str(tmp_path / "demo")]) == 1
    assert not (tmp_path / "demo").exists()
