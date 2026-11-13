import pytest

from canary import audit, config, db
from canary.vault import Vault

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from canary.ui import theme  # noqa: E402
from canary.ui.main_window import MainWindow  # noqa: E402
from canary.ui.widgets import Pill, VerdictBadge  # noqa: E402

PASSPHRASE = "a long test passphrase"


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance() or QApplication([])
    theme.apply(application)
    return application


@pytest.fixture
def window(app, canary_home):
    config.ensure_home()
    Vault.create(config.vault_path(), PASSPHRASE)
    win = MainWindow()
    yield win
    win.close()


def actions():
    return [r["action"] for r in db.connect().execute("SELECT action FROM audit_log ORDER BY id")]


def test_opens_locked_with_navigation_hidden(window):
    assert window.locked
    assert window.nav_bar.isHidden()
    assert window.vault is None


def test_wrong_passphrase_stays_locked_and_is_logged(window):
    window.try_unlock("not it")
    assert window.locked and window.vault is None
    assert "not right" in window.lock_page.message.text()
    assert actions() == ["failed unlock"]


def test_right_passphrase_unlocks_and_shows_leaks(window):
    window.try_unlock(PASSPHRASE)
    assert not window.locked
    assert window.stack.currentWidget() is window.pages["leaks"]
    assert window.background.isRunning()
    assert actions() == ["unlocked"]


def test_idle_window_locks_again_and_needs_the_passphrase(window):
    window.try_unlock(PASSPHRASE)
    window._last_activity -= config.IDLE_LOCK_SECONDS + 1
    window._check_idle()
    assert window.locked
    window.try_unlock("not it")
    assert window.locked
    window.try_unlock(PASSPHRASE)
    assert not window.locked
    assert actions() == ["unlocked", "locked", "failed unlock", "unlocked"]
    assert audit.verify(db.connect()) == (True, None)


def test_pages_cannot_be_opened_while_no_vault_is_open(window):
    window.show_page("limits")
    assert window.locked


def test_without_a_vault_it_says_how_to_make_one(app, canary_home):
    win = MainWindow()
    assert "canary init" in win.lock_page.prompt.text()
    assert not win.lock_page.field.isEnabled()
    win.close()


def test_screenshot_writes_an_image_per_screen(app, canary_home, tmp_path):
    from canary.ui.screenshot import render_all
    names = sorted(p.name for p in render_all(tmp_path / "shots"))
    assert {"case.png", "leaks.png", "limits.png", "lock.png"} <= set(names)
    assert all((tmp_path / "shots" / n).stat().st_size > 2000 for n in names)


def test_base_widgets_build(app):
    assert (Pill("Traced", "traced").text(), Pill("Traced", "traced").tone()) == ("Traced", "traced")
    words = {"traced": "Traced", "strong_lead": "Strong lead", "inconclusive": "Not enough to name anyone yet",
             "not_our_paper": "Not our paper"}
    for verdict, title in words.items():
        badge = VerdictBadge(verdict)
        assert badge.verdict == verdict and badge.title.text() == title and badge.note.text()


# ---- task 8: opening cases

KEY_FOR_APP = None


@pytest.fixture
def case_window(window):
    """An unlocked window over a seeded database holding one traced case and one unreadable leak."""
    from canary import analyze, leaks, seed, worker
    from canary import fingerprint as fp
    from canary.bank import load_bank
    from canary.samples import garble, leak_text
    window.try_unlock(PASSPHRASE)
    window.background.stop()                                   # the tests process leaks themselves
    conn, bank = window.conn, load_bank()
    key = bytes.fromhex(window.vault.get("fingerprint_key"))
    seed.seed(conn)
    paper = leak_text(fp.render_translator_copy(key, 1, 23, bank)[:14])
    traced = leaks.add_manual_leak(conn, text=paper)
    unreadable = leaks.add_manual_leak(conn, text=garble(paper, 0.4, seed=3))
    while worker.process_next(conn, lambda c, leak: analyze.analyze_leak(c, leak, key, None, bank)):
        pass
    window.ids = {"traced": traced, "unreadable": unreadable,
                  "case": conn.execute("SELECT id FROM cases WHERE leak_id = ?", (traced,)).fetchone()[0]}
    return window


def test_open_case_switches_to_the_case_screen_and_writes_the_audit_row(case_window):
    win = case_window
    assert win.open_case(win.ids["case"], play=False)
    assert win.stack.currentWidget() is win.pages["case"] and win.pages["case"].case_id == win.ids["case"]
    row = db.connect().execute("SELECT action, detail FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    assert (row["action"], row["detail"]) == ("case viewed", '{"case_id": %d}' % win.ids["case"])
    assert not win.open_case(99999)


def test_the_sidebar_shows_which_screen_is_open_and_a_case_belongs_to_leaks(case_window):
    win = case_window
    win.show_page("limits")
    assert win._buttons["limits"].isChecked() and not win._buttons["leaks"].isChecked()
    win.open_case(win.ids["case"], play=False)
    assert win._buttons["leaks"].isChecked() and not win._buttons["limits"].isChecked()
    win.show_page("leaks")
    assert win._buttons["leaks"].isChecked()


def test_nothing_can_be_opened_while_the_window_is_locked(case_window):
    win = case_window
    win.lock()
    before = actions()
    assert not win.open_case(win.ids["case"]) and not win.open_leak(win.ids["unreadable"])
    win.show_page("leaks")
    win.show_page("limits")
    win.on_case_created(win.ids["case"])
    win.on_leak_changed(win.ids["traced"])
    assert win.locked and win.stack.currentWidget() is win.lock_page
    assert actions() == before                                 # and nothing was recorded as viewed
    win.try_unlock(PASSPHRASE)
    assert win.open_case(win.ids["case"], play=False)


def test_the_background_thread_reports_leaks_and_cases_separately(app):
    from canary.ui.background import Background
    assert hasattr(Background, "leak_changed") and hasattr(Background, "case_created")
    assert not hasattr(Background, "changed")


def test_follow_new_leaks_opens_each_new_case_by_itself(case_window):
    win = case_window
    win.show_page("leaks")
    win.on_case_created(win.ids["case"])
    assert win.stack.currentWidget() is win.pages["leaks"]     # the switch is off
    win.pages["leaks"].follow_toggle.setChecked(True)
    win.on_case_created(win.ids["case"])
    assert win.stack.currentWidget() is win.pages["case"] and win.pages["case"].case_id == win.ids["case"]
