import json

import pytest

from canary import analyze, audit, check, cli, config, db, evidence, leaks, queries, seed, worker
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import leak_text
from canary.vault import Vault

PASSPHRASE = "a long test passphrase"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x07" * 64


@pytest.fixture
def vault(canary_home):
    config.ensure_home()
    return Vault.create(config.vault_path(), PASSPHRASE)


def counts(conn):
    return tuple(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("leaks", "cases", "leak_questions"))


def traced_case(conn, vault, stage="translation", copy_no=23):
    key, bank = bytes.fromhex(vault.get("fingerprint_key")), load_bank()
    render = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    leak_id = leaks.add_manual_leak(conn, text=leak_text(render(key, 1, copy_no, bank)[:14]))
    while worker.process_next(conn, lambda c, leak: analyze.analyze_leak(c, leak, key, None, bank)):
        pass
    return conn.execute("SELECT id FROM cases WHERE leak_id = ?", (leak_id,)).fetchone()[0]


# ---- check

def test_check_passes_three_times_in_a_row_and_leaves_no_rows(conn, vault):
    seed.seed(conn)
    for _ in range(3):
        lines = []
        assert check.check(conn, vault, say=lines.append)
        assert lines[-1].startswith("PASS") and any("translator copy" in line and "ms" in line for line in lines)
        assert any("printed copy" in line for line in lines) and any("fake paper" in line for line in lines)
        assert counts(conn) == (0, 0, 0)
    assert audit.verify(conn) == (True, None)
    passed = [json.loads(r[0]) for r in conn.execute("SELECT detail FROM audit_log WHERE action = 'health check'")]
    assert passed == [{"passed": True, "reason": None}] * 3


def test_check_works_before_the_seed_and_leaves_other_leaks_alone(conn, vault):
    mine = leaks.add_manual_leak(conn, text="an operator's own leak " * 20)
    assert check.check(conn, vault, say=lambda line: None)
    assert [r["id"] for r in conn.execute("SELECT id FROM leaks")] == [mine]
    assert conn.execute("SELECT status FROM leaks").fetchone()[0] == "queued"


def test_check_fails_with_the_reason_when_tracing_is_wrong(conn, vault, monkeypatch):
    real = fp.decode

    def off_by_one(*args, **kwargs):
        result = real(*args, **kwargs)
        if result.copy_no is not None:
            result.copy_no = result.copy_no % 50 + 1
        return result
    monkeypatch.setattr(fp, "decode", off_by_one)
    lines = []
    assert not check.check(conn, vault, say=lines.append)
    assert lines[-1].startswith("FAIL") and "copy_no was" in lines[-1] and counts(conn) == (0, 0, 0)


def test_check_fails_when_the_audit_log_was_edited(conn, vault):
    audit.record(conn, "unlocked")
    audit.record(conn, "case viewed", {"case_id": 1})
    conn.execute("UPDATE audit_log SET action = 'nothing' WHERE id = 1")
    conn.commit()
    lines = []
    assert not check.check(conn, vault, say=lines.append)
    assert "audit log is broken at row 1" in lines[-1]


def test_check_command_asks_for_the_passphrase_and_prints_pass(conn, vault, monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    assert cli.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and vault.get("fingerprint_key") not in out


# ---- reset

def test_reset_deletes_leaks_cases_and_evidence_but_keeps_the_rest(conn, vault, monkeypatch, capsys):
    seed.seed(conn)
    case_id = traced_case(conn, vault)
    evidence.build_evidence(conn, vault, case_id)
    leaks.save_image(PNG)
    before_audit = conn.execute("SELECT count(*) FROM audit_log").fetchone()[0]
    monkeypatch.setattr("getpass.getpass", lambda prompt="": PASSPHRASE)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert cli.main(["reset"]) == 1 and counts(conn)[0] == 1                 # not confirmed: nothing deleted
    assert cli.main(["reset", "--yes"]) == 0
    assert "kept" in capsys.readouterr().out
    assert counts(conn) == (0, 0, 0)
    assert not list((config.home() / "evidence").iterdir()) and not list((config.home() / "leaks").iterdir())
    assert seed.row_counts(conn)["print copies"] == 5000 and seed.row_counts(conn)["custody events"] == 20150
    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == before_audit + 1
    assert audit.verify(conn) == (True, None) and config.vault_path().exists()


# ---- replay

def test_export_case_writes_a_replay_that_loads_from_the_file_alone(conn, vault, monkeypatch, capsys):
    seed.seed(conn)
    case_id = traced_case(conn, vault, "print", 4821)
    assert cli.main(["export-case", str(case_id)]) == 0
    assert f"run --replay case-{case_id}" in capsys.readouterr().out
    path = check.replay_dir() / f"case-{case_id}.json"
    assert path.exists() and vault.get("fingerprint_key") not in path.read_text()
    conn.close()

    def no_database(*args, **kwargs):
        raise AssertionError("a replay must not open the database")
    monkeypatch.setattr(db, "connect", no_database)
    view = check.load_replay(f"case-{case_id}")
    assert isinstance(view, queries.CaseView)
    assert (view.verdict, view.stage, view.copy_no, len(view.steps)) == ("traced", "print", 4821, 14)
    assert view.replay_label.startswith("Replay of a real run from ") and view.holder_at_leak.to_role == "Centre superintendent"
    assert view.evidence_path is None


def test_replay_names_cannot_leave_the_replay_folder(conn, vault):
    (config.home() / "secret.json").write_text(json.dumps({"format": check.REPLAY_FORMAT, "view": {}}))
    for name in ("../secret", "../secret.json", "/etc/passwd", "missing"):
        with pytest.raises(LookupError):
            check.load_replay(name)
    (check.replay_dir() / "bad.json").write_text("{not json")
    with pytest.raises(LookupError, match="not a usable replay file"):
        check.load_replay("bad")
    with pytest.raises(SystemExit):
        cli.main(["export-case", "999"])
    with pytest.raises(SystemExit):
        cli.main(["run", "--replay", "missing"])


def test_the_replay_window_still_asks_for_the_passphrase_and_starts_nothing(conn, vault):
    PySide6 = pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from canary.ui import theme
    from canary.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    seed.seed(conn)
    case_id = traced_case(conn, vault)
    check.export_case(conn, case_id)
    win = MainWindow(replay=check.load_replay(f"case-{case_id}"))
    try:
        assert win.locked
        win.try_unlock("not it")
        assert win.locked
        win.try_unlock(PASSPHRASE)
        case = win.pages["case"]
        assert win.stack.currentWidget() is case and win.background is None           # no worker, no listener, no network
        assert case.replay_label.text().startswith("Replay of a real run from ") and case.view.copy_no == 23
        assert case.issue.isHidden() and case.back.isHidden() and "Replay" in win.status.text()
        win.show_page("leaks")
        assert win.stack.currentWidget() is case                                      # a replay shows one case and nothing else
        assert not win.open_case(case_id)
    finally:
        win.close()
    actions = [r[0] for r in db.connect().execute("SELECT action FROM audit_log ORDER BY id DESC LIMIT 3")]
    assert actions == ["stopped", "replay opened", "unlocked"]


def test_every_command_is_built():
    assert cli.NOT_BUILT == {}
    parser = cli.build_parser()
    commands = set(next(a for a in parser._actions if a.dest == "command").choices)
    assert {"init", "vault", "run", "seed", "decode", "print-copies", "verify-chain", "read", "add-leak", "cases", "tg-login",
            "watch", "unwatch", "verify", "sim", "check", "reset", "export-case", "screenshot", "verify-audit"} <= commands
