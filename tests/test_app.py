import pytest

from canary import audit, config, db
from canary.vault import Vault

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from canary.ui import theme  # noqa: E402
from canary.ui.main_window import MainWindow  # noqa: E402
from canary.ui.widgets import OMRNumber, VerdictBanner  # noqa: E402

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
    assert names == ["case.png", "leaks.png", "limits.png", "lock.png"]
    assert all((tmp_path / "shots" / n).stat().st_size > 2000 for n in names)


def test_base_widgets_build(app):
    assert OMRNumber(4821).accessibleName() == "Copy 4821"
    for verdict in ("traced", "strong_lead", "inconclusive", "not_our_paper"):
        assert VerdictBanner(verdict).verdict == verdict
