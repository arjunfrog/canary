"""Guards for the brief's security rules. Each test fails if a later change breaks a rule."""
import importlib.metadata
import json
import re
import stat
import sys
import threading
from pathlib import Path

import pytest

from canary import analyze, audit, check, config, db, evidence, leaks, pdf, seed, sim, worker
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import leak_text
from canary.vault import Vault

PACKAGE = Path(config.PACKAGE_DIR)
SOURCES = sorted(PACKAGE.rglob("*.py"))
PASSPHRASE = "a long test passphrase"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x09" * 64


def code_of(path: Path) -> str:
    """The file without comments and docstrings, so rules can be stated in prose without tripping the guards."""
    text = re.sub(r'"""[\s\S]*?"""', '""', path.read_text(encoding="utf-8"))
    return "\n".join(line.split("  #")[0] for line in text.splitlines() if not line.strip().startswith("#"))


def test_the_app_opens_no_port_and_serves_nothing():
    forbidden = [r"\bhttp\.server\b", r"\bsocketserver\b", r"\.listen\(", r"\.bind\(", r"\bstart_server\b", r"\bcreate_server\b",
                 r"\bflask\b", r"\bfastapi\b", r"\buvicorn\b", r"\baiohttp\.web\b", r"\bwebbrowser\b", r"QtNetwork", r"QTcpServer",
                 r"QLocalServer", r"QtWebEngine", r"QtWebSockets", r"QDesktopServices"]
    for path in SOURCES:
        code = code_of(path)
        for pattern in forbidden:
            assert not re.search(pattern, code), f"{path.name} uses {pattern}"


def test_only_the_allowed_qt_modules_are_imported_and_never_pyqt():
    allowed = {"QtCore", "QtGui", "QtWidgets", "QtSvg"}
    for path in SOURCES:
        code = code_of(path)
        assert "PyQt" not in code, path.name
        for module in re.findall(r"PySide6\.(Qt\w+)", code):
            assert module in allowed, f"{path.name} imports PySide6.{module}"
        assert "QtCharts" not in code and "QtDataVisualization" not in code


def test_no_gpl_qt_packages_are_installed_or_declared():
    names = {d.metadata["Name"].lower().replace("-", "_") for d in importlib.metadata.distributions()}
    assert not {n for n in names if n.startswith("pyqt")} and "pyside6_addons" not in names and "pyside6" not in names
    declared = (PACKAGE.parent / "pyproject.toml").read_text()
    assert "PySide6-Essentials" in declared and "PySide6-Addons" not in declared and "PyQt" not in declared


def test_the_only_outside_address_in_the_code_is_telegram():
    hosts = set()
    for path in SOURCES:
        hosts |= set(re.findall(r"https?://[A-Za-z0-9.\-]+|[a-z0-9\-]+\.googleapis\.com", code_of(path)))
    assert hosts <= {"https://t.me"}, hosts


def test_no_shell_commands_and_no_dynamic_code():
    for path in SOURCES:
        code = code_of(path)
        for pattern in (r"\bsubprocess\b", r"os\.system", r"os\.popen", r"(?<![.\w])eval\(", r"(?<![.\w])exec\(", r"\bpickle\b", r"shell=True",
                        r"os\.fork", r"\bpwd\b", r"\bfcntl\b"):
            assert not re.search(pattern, code), f"{path.name} uses {pattern}"


def test_no_dark_theme_and_no_stylesheet_fonts_on_plain_widgets():
    from canary.ui import theme
    assert "dark" not in theme.STYLESHEET.lower()
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", theme.STYLESHEET):
        if selector.strip() in ("QLabel", "QWidget", "*"):
            assert "font" not in body, selector
    assert not re.search(r"font-family", theme.STYLESHEET)


@pytest.fixture
def lived_in(conn):
    """A CANARY_HOME after an ordinary day: vault, seed, leaks, an image, a case, evidence, a PDF, a replay, the sim."""
    config.ensure_home()
    vault = Vault.create(config.vault_path(), PASSPHRASE, {"tg_api_id": "1234567",
                                                           "tg_api_hash": "0123456789abcdef0123456789abcdef",
                                                           "tg_session": "1BVtsOHQBu-session-string"})
    key, bank = bytes.fromhex(vault.get("fingerprint_key")), load_bank()
    seed.seed(conn)
    leak_id = leaks.add_manual_leak(conn, text=leak_text(fp.render_translator_copy(key, 1, 23, bank)[:14]))
    photo = config.home() / "incoming.png"
    photo.write_bytes(PNG)
    leaks.add_manual_leak(conn, image_path=photo)
    photo.unlink()

    def reader(image):
        return {"questions": [{"number": 1, "legible": False, "stem": "?", "options": []}]}, "mock reader"
    while worker.process_next(conn, lambda c, leak: analyze.analyze_leak(c, leak, key, reader, bank)):
        pass
    case_id = conn.execute("SELECT id FROM cases WHERE leak_id = ?", (leak_id,)).fetchone()[0]
    evidence.build_evidence(conn, vault, case_id)
    pdf.export_copy(conn, key, "translation", 23)
    check.export_case(conn, case_id)
    sim.run_sim(trials=500)
    assert check.check(conn, vault, say=lambda line: None)
    audit.record(conn, "secret changed", {"name": "tg_api_hash"})
    return conn, vault


@pytest.mark.skipif(sys.platform == "win32", reason="Windows ignores file modes")
def test_every_directory_is_0700_and_every_file_0600(lived_in):
    entries = list(config.home().rglob("*"))
    assert len(entries) > 15
    for entry in [config.home(), *entries]:
        mode = stat.S_IMODE(entry.stat().st_mode)
        assert mode == (0o700 if entry.is_dir() else 0o600), f"{entry.relative_to(config.home().parent)} is {oct(mode)}"


def test_no_secret_reaches_the_database_the_logs_or_any_other_file(lived_in, caplog):
    conn, vault = lived_in
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    secrets = [vault.get(n) for n in ("fingerprint_key", "signing_key", "tg_api_hash", "tg_session")]
    needles = [s.encode() for s in secrets] + [bytes.fromhex(vault.get("fingerprint_key")), bytes.fromhex(vault.get("signing_key")),
                                                PASSPHRASE.encode()]
    for entry in config.home().rglob("*"):
        if entry.is_file():
            blob = entry.read_bytes()
            for needle in needles:
                assert needle not in blob, f"a secret is in {entry.name}"
    assert not any(s in caplog.text for s in secrets)
    assert not any(s in repr(vault) or s in str(vault.names()) for s in secrets)


def test_nothing_derived_from_the_key_is_written_down_except_the_named_copy(lived_in):
    conn, vault = lived_in
    key, bank = bytes.fromhex(vault.get("fingerprint_key")), load_bank()
    # The health check typed out a random translator copy and deleted it again. Nothing of any copy other
    # than the named one (23) may be left behind, not even in the database's freed pages.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    kept = {r.stem for r in fp.render_translator_copy(key, 1, 23, bank)}
    others = set()
    for copy_no in range(1, 51):
        others |= {r.stem for r in fp.render_translator_copy(key, 1, copy_no, bank) if r.set_no} - kept
    everything = b"".join(e.read_bytes() for e in config.home().rglob("*") if e.is_file() and e.suffix != ".pdf")
    assert len(others) > 300 and not [stem for stem in others if stem.encode() in everything]


def test_the_audit_chain_stays_whole_when_threads_write_at_once(conn):
    def writer(n):
        mine = db.connect()
        for i in range(25):
            audit.record(mine, "case viewed", {"case_id": n * 100 + i})
        mine.close()
    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 100
    assert audit.verify(conn) == (True, None)
    assert audit.head(conn)[0] == 100 and len(audit.head(conn)[1]) == 64


def test_two_workers_never_take_the_same_leak(conn):
    for i in range(40):
        conn.execute("INSERT INTO leaks (source, raw_text, received_at) VALUES ('manual', ?, ?)", (f"leak {i}", db.now()))
    conn.commit()
    taken, lock = [], threading.Lock()

    def run():
        mine = db.connect()
        while (row := worker.claim_next(mine)) is not None:
            with lock:
                taken.append(row["id"])
        mine.close()
    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(taken) == list(range(1, 41))


def test_five_wrong_tries_block_even_the_right_passphrase_for_a_minute(canary_home):
    PySide6 = pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from canary.ui import theme
    from canary.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    config.ensure_home()
    Vault.create(config.vault_path(), PASSPHRASE)
    win = MainWindow()
    try:
        now = [1000.0]
        win.lock_page.guard._clock = lambda: now[0]
        for _ in range(5):
            win.try_unlock("wrong guess")
        assert win.lock_page.guard.blocked_for() == 60 and "Too many wrong tries" in win.lock_page.message.text()
        win.try_unlock(PASSPHRASE)
        assert win.locked and win.vault is None                   # the right passphrase is refused during the wait
        now[0] += 61
        win.try_unlock(PASSPHRASE)
        assert not win.locked
        failed = db.connect().execute("SELECT count(*) FROM audit_log WHERE action = 'failed unlock'").fetchone()[0]
        assert failed == 5
    finally:
        win.close()


def test_the_lock_screen_hides_the_passphrase_and_the_vault_is_never_shown(canary_home):
    PySide6 = pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

    from canary.ui import theme
    from canary.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    config.ensure_home()
    vault = Vault.create(config.vault_path(), PASSPHRASE, {"tg_api_hash": "g-secret-key-123"})
    win = MainWindow()
    try:
        assert win.lock_page.field.echoMode() == QLineEdit.EchoMode.Password
        win.try_unlock(PASSPHRASE)
        win.refresh_status()
        shown = " ".join(label.text() for label in win.findChildren(QLabel))
        for name in ("fingerprint_key", "signing_key", "tg_api_hash"):
            assert vault.get(name) not in shown
        assert win.lock_page.field.text() == ""
    finally:
        win.close()


def test_the_reader_keeps_indic_joiners_but_drops_other_hidden_characters():
    from canary import reader
    assert reader.clean("क्\u200dष \u202eabc\u2066\x1b[31m") == "क्\u200dष abc[31m"
    text, _ = reader.assemble([reader.Box("1. a\u202eb", 1.0, 0.1, 0.9, 0.02)])
    assert text == "1. ab"


def test_verify_audit_prints_the_newest_hash_to_keep_elsewhere(conn, capsys):
    from canary import cli
    audit.record(conn, "unlocked")
    assert cli.main(["verify-audit"]) == 0
    out = capsys.readouterr().out
    assert audit.head(conn)[1] in out and "1 rows" in out


def test_every_data_file_the_package_reads_is_declared_for_install_and_for_the_packaged_app():
    root = PACKAGE.parent
    spec, project = (root / "packaging" / "canary.spec").read_text(), (root / "pyproject.toml").read_text()
    data_files = sorted(p.name for p in (PACKAGE / "data").iterdir() if p.is_file() and not p.name.startswith("."))
    assert data_files == ["bank.db", "score_set.json", "score_set_2.json"]
    for name in data_files:
        assert f'"{name}"' in spec and f"data/{name}" in project, name
    assert '"schema.sql"' in spec and '"fonts"' in spec and "ui/fonts/*.ttf" in project


def test_the_photo_reader_makes_no_network_connection(monkeypatch):
    import socket
    from canary import reader
    if not reader.available()[0]:
        pytest.skip("the Mac's text recognition is not available here")

    def no_network(*args, **kwargs):
        raise AssertionError("the photo reader tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    from tests.test_reader import page_image
    data = reader.read_image(page_image("1. A car starts from rest and accelerates uniformly at 2 m/s for 5 s."))
    assert "car starts from rest" in data["readings"][0]["text"]
