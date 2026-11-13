import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QHeaderView  # noqa: E402

from canary import analyze, config, db, leaks, lurker, queries, seed, worker  # noqa: E402
from canary import fingerprint as fp  # noqa: E402
from canary.bank import load_bank  # noqa: E402
from canary.samples import fake_paper_text, leak_text  # noqa: E402
from canary.ui import theme  # noqa: E402
from canary.ui.main_window import MainWindow  # noqa: E402
from canary.ui.pages.leaks import AddLeakDialog, verdict_words  # noqa: E402
from canary.ui.widgets import StatusLine  # noqa: E402
from canary.ui.widgets.ruled_table import ToneRole  # noqa: E402
from canary.vault import Vault  # noqa: E402

PASSPHRASE = "a long test passphrase"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x03" * 64


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    theme.apply(application)
    return application


@pytest.fixture
def window(app, canary_home):
    config.ensure_home()
    Vault.create(config.vault_path(), PASSPHRASE)
    win = MainWindow()
    win.try_unlock(PASSPHRASE)
    win.background.stop()                                        # the tests run the worker themselves
    seed.seed(win.conn)
    win.key = bytes.fromhex(win.vault.get("fingerprint_key"))
    yield win
    win.close()


def work(win):
    bank = load_bank()
    while worker.process_next(win.conn, lambda c, leak: analyze.analyze_leak(c, leak, win.key, None, bank)):
        pass


def paper(win, stage="translation", copy_no=23, count=14):
    render = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    return leak_text(render(win.key, 1, copy_no, load_bank())[:count])


def test_the_list_is_empty_at_first_and_says_what_to_do(window):
    page = window.pages["leaks"]
    page.refresh()
    assert page.model.rowCount() == 0 and page.table.isHidden()
    assert "No leaks yet" in page.message.text() and "Add a leak" in page.message.text()


def test_rows_show_chat_sender_time_status_and_verdict(window):
    page = window.pages["leaks"]
    leaks.add_manual_leak(window.conn, text=paper(window))
    leaks.add_manual_leak(window.conn, text=fake_paper_text())
    work(window)
    leaks.add_manual_leak(window.conn, text=paper(window, "print", 4821))
    window.on_leak_changed(3)                                    # what the background thread's signal does
    model = page.model
    assert model.rowCount() == 3 and not page.table.isHidden() and page.message.isHidden()
    cell = lambda r, c: model.data(model.index(r, c))
    assert [model.headerData(c, Qt.Orientation.Horizontal) for c in range(5)] == ["Posted", "Chat", "Sender", "Status", "Verdict"]
    assert (cell(0, 3), cell(0, 4)) == ("Waiting to be read", "No verdict yet")
    assert (cell(1, 3), cell(1, 4)) == ("Read", "Not our paper")
    assert (cell(2, 1), cell(2, 2), cell(2, 4)) == ("Added by hand", "Added by hand", "Traced: translator copy 23")
    assert model.data(model.index(2, 4), ToneRole) == "traced" and model.data(model.index(1, 4), ToneRole) == "seal"
    assert "3 leaks, 1 waiting" in page.summary.text()
    work(window)
    window.on_leak_changed(3)
    assert cell(0, 4) == "Traced: printed copy 4821"


def test_the_table_follows_the_design_rules(window):
    table = window.pages["leaks"].table
    assert not table.showGrid() and not table.verticalHeader().isVisible() and not table.alternatingRowColors()
    assert table.font().family() == "Mukta" and table.horizontalHeader().font().family() == "Mukta"
    assert isinstance(table.horizontalHeader(), QHeaderView) and not table.horizontalHeader().sectionsClickable()


def test_opening_a_row_opens_its_case_and_a_caseless_row_opens_the_leak(window):
    page = window.pages["leaks"]
    leaks.add_manual_leak(window.conn, text=paper(window))
    work(window)
    leaks.add_manual_leak(window.conn, text="waiting " * 40)
    page.refresh()
    page.open_row(1)
    case = window.pages["case"]
    assert window.stack.currentWidget() is case and case.view.verdict == "traced" and case.view.copy_no == 23
    window.show_page("leaks")
    page.open_row(0)
    assert case.view.status == "queued" and case.banner.title.text() == "Waiting to be read"
    work(window)
    window.on_leak_changed(case.leak_id)                         # the leak on screen has now been read
    assert case.banner.title.text() == "We couldn't read this clearly."


def test_follow_new_leaks_opens_the_new_case_and_plays_its_real_funnel(window, monkeypatch):
    monkeypatch.delenv("CANARY_REDUCE_MOTION", raising=False)
    page, case = window.pages["leaks"], window.pages["case"]
    window.show_page("leaks")
    page.follow_toggle.click()
    assert page.follow
    leak_id = leaks.add_manual_leak(window.conn, text=paper(window, "print", 4821))
    work(window)
    case_id = window.conn.execute("SELECT id FROM cases WHERE leak_id = ?", (leak_id,)).fetchone()[0]
    window.on_case_created(case_id)                              # the background thread's signal
    assert window.stack.currentWidget() is case and case.case_id == case_id
    assert case.funnel.is_playing() and case.funnel.steps() == 14 == len(case.view.steps)
    case.funnel.stop()
    assert case.fit_value.text() == "1 of 5,000"


def test_add_a_leak_takes_pasted_text_with_no_network(window):
    page = window.pages["leaks"]
    dialog = page.open_add_dialog()
    dialog._submit()
    assert "Paste some text or choose an image first" in dialog.message.text() and dialog.leak_id is None
    dialog.text.setPlainText(paper(window))
    dialog._submit()
    assert dialog.leak_id == 1
    row = window.conn.execute("SELECT source, status, raw_text FROM leaks").fetchone()
    assert (row["source"], row["status"]) == ("manual", "queued") and row["raw_text"].startswith("1. ")
    assert page.model.rowCount() == 1
    assert [r[0] for r in db.connect().execute("SELECT action FROM audit_log ORDER BY id DESC LIMIT 1")] == ["leak added by hand"]


def test_add_a_leak_takes_a_chosen_or_dropped_image_and_refuses_other_files(window, tmp_path):
    good, bad = tmp_path / "page1.png", tmp_path / "notes.png"
    good.write_bytes(PNG)
    bad.write_bytes(b"not an image at all")
    dialog = AddLeakDialog(window.conn)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(bad))])
    dialog.dropEvent(QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier))
    assert dialog.image_path == str(bad) and "notes.png" in dialog.image_label.text()
    dialog._submit()
    assert "not a JPEG, PNG or WebP" in dialog.message.text() and dialog.leak_id is None
    dialog.set_image(str(good))
    dialog.text.setPlainText("some text as well")
    dialog._submit()
    assert "not both" in dialog.message.text()
    dialog.text.clear()
    dialog._submit()
    assert dialog.leak_id is not None
    row = window.conn.execute("SELECT image_path, image_sha256, raw_text FROM leaks").fetchone()
    assert row["image_path"].endswith(".png") and len(row["image_sha256"]) == 64 and row["raw_text"] is None


def test_locking_closes_the_add_dialog(window):
    page = window.pages["leaks"]
    dialog = page.open_add_dialog()
    dialog.text.setPlainText("half typed")
    window.lock()
    assert dialog.isHidden() and page._dialog is None
    assert window.conn.execute("SELECT count(*) FROM leaks").fetchone()[0] == 0


def test_verdict_words_never_name_a_copy_without_a_verdict_that_allows_it():
    row = lambda **kw: queries.LeakRow(1, "manual", "c", "s", None, "2026", kw.pop("status", "done"), kw.pop("verdict", None), 1, **kw)
    assert verdict_words(row(verdict="inconclusive")) == ("Not enough to name anyone yet", "muted")
    assert verdict_words(row(verdict="strong_lead", stage="print", copy_no=12)) == ("Strong lead: printed copy 12", "lead")
    assert verdict_words(row(status="unreadable"))[0] == "We couldn't read this clearly"
    assert verdict_words(row(status="failed")) == ("No verdict", "seal")


# ---- the status line

class FakeVault:
    def __init__(self, key=None):
        self.key = key

    def get(self, name):
        return self.key if name == "gemini_api_key" else None


def test_the_status_line_reports_chats_telegram_and_the_photo_reader(app):
    line = StatusLine()
    status = queries.Status([("examleaks_demo", "Exam <b>leaks</b>"), ("neet_demo", "NEET")], {"queued": 1, "done": 3}, 4, True)
    line.show_status(status, lurker.ListenerState(True, "Telegram connected.", 2), FakeVault("k"), reader_reachable=True)
    assert "Watching 2 chats.  Telegram connected.  Photo analysis is ready.  1 leak waiting to be read." in line.text()
    line.show_status(status, lurker.ListenerState(True, "Telegram connected.", 2), FakeVault("k"), reader_reachable=False)
    assert "Photo reader not reachable." in line.text() and "Offline" not in line.text()
    line.show_status(status, lurker.ListenerState(True, "Telegram connected.", 2), FakeVault(None))
    assert "No photo reader key" in line.text()
    assert line.textFormat() == Qt.TextFormat.PlainText and line.font().family() == "Mukta"


def test_offline_it_says_typed_leaks_still_work(app):
    line = StatusLine()
    status = queries.Status([], {}, 0, False)
    line.show_status(status, lurker.ListenerState(False, "Telegram is not reachable. Typed leaks still work."), FakeVault("k"),
                     reader_reachable=False)
    assert "Manual leak entry is available." in line.text() and "python -m canary seed" in line.text()
    line.show_status(status, lurker.ListenerState(False, "Telegram is not logged in. Run: python -m canary tg-login"), FakeVault(None))
    assert "Manual leak entry is available." in line.text() and "tg-login" in line.text()
    line.show_replay()
    assert "Replay" in line.text()


# ---- task 11: issuing the evidence file from the Case screen

def test_issue_evidence_file_then_save_a_copy(window, tmp_path):
    from canary import evidence
    leaks.add_manual_leak(window.conn, text=paper(window))
    work(window)
    window.pages["leaks"].refresh()
    window.pages["leaks"].open_row(0)
    case = window.pages["case"]
    assert not case.response_section.isHidden() and "14 of the 180 real questions" in case.response_summary.text()
    assert "Recommended, for a person to decide" in case.response_advice.text()
    assert not case.issue.isHidden() and case.save_copy.isHidden()
    case.issue.click()
    manifest = evidence.manifest_path(case.case_id)
    assert manifest.exists() and str(manifest) in case.evidence_note.text()
    assert case.issue.isHidden() and not case.save_copy.isHidden()
    assert all(ok for _, ok in evidence.verify_file(manifest))
    saved = case.save_evidence_to(tmp_path / "usb")
    assert all(ok for _, ok in evidence.verify_file(saved / "manifest.json"))
    actions = [r[0] for r in db.connect().execute("SELECT action FROM audit_log ORDER BY id")]
    assert actions[-2:] == ["evidence issued", "evidence copy saved"]
    window.show_page("leaks")
    window.pages["leaks"].open_row(0)                             # opening it again finds the file already issued
    assert case.issue.isHidden() and "Evidence file issued and signed" in case.evidence_note.text()


def test_evidence_cannot_be_issued_while_locked_or_without_a_named_copy(window):
    from canary import evidence
    leaks.add_manual_leak(window.conn, text=paper(window, count=3).replace("(", "").split("A)")[0] + "\n")
    leaks.add_manual_leak(window.conn, text=paper(window))
    work(window)
    window.pages["leaks"].refresh()
    case = window.pages["case"]
    window.pages["leaks"].open_row(0)
    traced = case.case_id
    window.lock()
    case._issue_evidence()
    assert not evidence.manifest_path(traced).exists()


# ---- task 12: the Limits screen

def test_limits_screen_says_when_the_simulation_has_not_been_run(window):
    page = window.pages["limits"]
    window.show_page("limits")
    assert not page.missing.isHidden() and page.loaded.isHidden() and not page.run_button.isHidden()
    assert "has not been run on this laptop yet" in page.message.text()
    assert window.marks.states() == [False] * 7


def test_limits_screen_draws_from_the_saved_file_without_rerunning(window, monkeypatch):
    from canary import sim
    sim.run_sim(trials=1500)

    def must_not_run(*args, **kwargs):
        raise AssertionError("the Limits screen must draw from the saved file")
    monkeypatch.setattr(sim, "run_sim", must_not_run)
    page = window.pages["limits"]
    window.show_page("limits")
    assert page.missing.isHidden() and not page.loaded.isHidden()
    assert len(page._buttons) == 7 and page._buttons[0].isChecked()
    assert page.title.text() == "Translator leak, typed, values kept" and len(page.chart.points()) == 7
    assert "Simulation, not field results" in page.note.text() and "assumed" in page.note.text()
    assert window.marks.states() == [True, True, True, False, True, True, False]
    page._buttons[3].click()
    assert page.title.text().startswith("Translator leak with numbers removed") and "cannot name anyone" in page.sentence.text()
    assert all(p["traced_right"] == 0 for p in page.chart.points())
    window.show_page("leaks")
    window.show_page("limits")
    assert page._buttons[3].isChecked() and len(page._buttons) == 7        # the choice is kept


def test_run_the_simulation_button_fills_the_screen(window):
    page = window.pages["limits"]
    window.show_page("limits")
    page.run_button.click()
    assert not page.loaded.isHidden() and len(page.chart.points()) == 7
    assert [r[0] for r in db.connect().execute("SELECT action FROM audit_log ORDER BY id DESC LIMIT 1")] == ["simulation run"]
    from canary import sim
    sim.limits_path().write_text("{broken")
    page.refresh()
    assert "cannot be read" in page.message.text() and not page.run_button.isHidden()
