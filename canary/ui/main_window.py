import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import audit, config, db, queries
from ..vault import Vault, WrongPassphrase
from . import theme
from .background import Background
from .pages import CasePage, LeaksPage, LimitsPage, LockPage
from .widgets import StatusLine, SyntheticLabel, TimingMarks
from .widgets.ruled_section import rule

ACTIVITY = {QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel}


class MainWindow(QMainWindow):
    """The sheet every screen sits on: timing marks down the left, navigation on top, one screen at a time.

    It opens locked. The passphrase opens the vault, starts the background thread and shows the Leaks screen.
    After 10 minutes with no key or mouse activity it locks again. Nothing can be opened while it is locked.

    With `replay`, the window shows one saved case from a file. It still asks for the passphrase, but starts
    no background thread and makes no network connection.
    """

    def __init__(self, replay: queries.CaseView | None = None):
        super().__init__()
        self.setWindowTitle("Canary")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.vault: Vault | None = None
        self.background: Background | None = None
        self.replay = replay
        self._unlocked = False                           # true only between a right passphrase and the next lock
        self.conn = db.connect()
        self._last_activity = time.monotonic()

        # left rail: timing marks and the margin rule
        self.marks = TimingMarks(total=14, done=0)      # the screen being shown sets these
        rail = QWidget()
        rail.setFixedWidth(64)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(16, 118, 16, 0)
        rail_layout.addWidget(self.marks)
        rail_layout.addStretch(1)
        margin = QFrame()
        margin.setFixedWidth(1)
        margin.setStyleSheet(f"background: {theme.DROPOUT.name()};")

        # header: name, navigation, synthetic label
        self.name = QLabel("Canary")
        self.name.setFont(theme.display(40))
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        self.nav_bar = QWidget()
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(32, 0, 0, 2)
        nav_layout.setSpacing(24)
        header = QHBoxLayout()
        header.addWidget(self.name, 0, Qt.AlignmentFlag.AlignBottom)
        header.addWidget(self.nav_bar, 0, Qt.AlignmentFlag.AlignBottom)
        header.addStretch(1)
        header.addWidget(SyntheticLabel(), 0, Qt.AlignmentFlag.AlignVCenter)

        # screens
        self.stack = QStackedWidget()
        self.lock_page = LockPage()
        self.lock_page.submitted.connect(self.try_unlock)
        self.pages = {"leaks": LeaksPage(self), "case": CasePage(self), "limits": LimitsPage(self)}
        self.stack.addWidget(self.lock_page)
        for page in self.pages.values():
            self.stack.addWidget(page)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in (("leaks", "Leaks"), ("limits", "Limits")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("nav", True)
            button.setFont(theme.body(20))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav.addButton(button)
            nav_layout.addWidget(button)
            self._buttons[key] = button
        if replay is not None:
            self.nav_bar.setEnabled(False)               # a replay shows one case and nothing else

        self.status = StatusLine()
        sheet = QVBoxLayout()
        sheet.setContentsMargins(40, 28, 40, 16)
        sheet.setSpacing(10)
        sheet.addLayout(header)
        sheet.addWidget(rule())
        sheet.addSpacing(18)
        sheet.addWidget(self.stack, 1)
        sheet.addWidget(rule(theme.RULE))
        sheet.addWidget(self.status)

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(rail)
        row.addWidget(margin)
        row.addLayout(sheet, 1)
        self.setCentralWidget(root)

        self._idle = QTimer(self)
        self._idle.setInterval(5000)
        self._idle.timeout.connect(self._check_idle)
        self._idle.start()
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(3000)
        self._status_timer.timeout.connect(self.refresh_status)
        self._status_timer.start()
        self.lock(first=True)

    # ---- locking

    @property
    def locked(self) -> bool:
        return self.stack.currentWidget() is self.lock_page

    def lock(self, first: bool = False) -> None:
        self._unlocked = False
        self.name.setVisible(False)              # the lock screen shows the name itself, large
        self.nav_bar.setVisible(False)
        self.status.setVisible(False)
        self.marks.set_progress(14, 0)
        for page in self.pages.values():
            page.on_lock()                       # close dialogs and stop animations, so nothing shows behind the lock
        self.stack.setCurrentWidget(self.lock_page)
        self.lock_page.field.setFocus()
        if not config.vault_path().exists():
            self.lock_page.prompt.setText("No vault yet. Close this window and run: python -m canary init")
            self.lock_page.field.setDisabled(True)
            self.lock_page.button.setDisabled(True)
        elif not first:
            self.lock_page.prompt.setText("Locked after 10 minutes idle. Type the passphrase to continue.")
            audit.record(self.conn, "locked")

    def try_unlock(self, passphrase: str) -> None:
        if self.lock_page.guard.blocked_for() > 0:
            return
        try:
            if self.vault is None:
                self.vault = Vault.open(config.vault_path(), passphrase)
            elif not self.vault.check(passphrase):
                raise WrongPassphrase()
        except WrongPassphrase:
            audit.record(self.conn, "failed unlock")
            self.lock_page.wrong()
            return
        self.lock_page.right()
        self._unlocked = True
        audit.record(self.conn, "unlocked")
        self._last_activity = time.monotonic()
        self.name.setVisible(True)
        self.nav_bar.setVisible(True)
        self.status.setVisible(True)
        if self.replay is not None:
            audit.record(self.conn, "replay opened", {"leak_id": self.replay.leak_id})
            self.status.show_replay()
            self._show_case_view(self.replay, play=True)
            return
        if self.background is None:
            self.background = Background(self.vault, self)
            self.background.leak_changed.connect(self.on_leak_changed)
            self.background.case_created.connect(self.on_case_created)
            self.background.start()
        self.refresh_status()
        self.show_page("leaks")

    def _check_idle(self) -> None:
        if not self.locked and time.monotonic() - self._last_activity > config.IDLE_LOCK_SECONDS:
            self.lock()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in ACTIVITY:
            self._last_activity = time.monotonic()
        return super().eventFilter(watched, event)

    # ---- screens

    def show_page(self, key: str) -> None:
        if not self._unlocked or self.replay is not None:
            return
        self.stack.setCurrentWidget(self.pages[key])
        for name, button in self._buttons.items():
            self.nav.setExclusive(False)
            button.setChecked(name == key)
            self.nav.setExclusive(True)
        self.pages[key].refresh()
        self.marks.set_states(self.pages[key].marks())

    def open_case(self, case_id: int, play: bool = True) -> bool:
        """Show the Case screen for one case, and record that it was viewed. Does nothing while locked."""
        if not self._unlocked or self.replay is not None:
            return False
        view = queries.get_case(self.conn, case_id)
        if view is None:
            return False
        audit.record(self.conn, "case viewed", {"case_id": case_id})
        self._show_case_view(view, play)
        return True

    def open_leak(self, leak_id: int) -> bool:
        """Show a leak that has no case yet, or never will: one that is waiting, unreadable or failed."""
        if not self._unlocked or self.replay is not None:
            return False
        view = queries.get_leak(self.conn, leak_id)
        if view is None:
            return False
        if view.case_id is not None:
            return self.open_case(view.case_id)
        audit.record(self.conn, "leak viewed", {"leak_id": leak_id})
        self._show_case_view(view, play=False)
        return True

    def _show_case_view(self, view: queries.CaseView, play: bool) -> None:
        if not self._unlocked:
            return
        page = self.pages["case"]
        page.show_case(view, play=play)
        self.stack.setCurrentWidget(page)
        self.nav.setExclusive(False)
        for button in self._buttons.values():
            button.setChecked(False)
        self.nav.setExclusive(True)
        self.marks.set_states(page.marks())

    def on_leak_changed(self, leak_id: int) -> None:
        if not self._unlocked:
            return
        current = self.stack.currentWidget()
        if current is self.pages["leaks"]:
            current.refresh()
        elif current is self.pages["case"] and current.leak_id == leak_id and current.case_id is None:
            self.open_leak(leak_id)                      # the leak on screen has just been analysed
        self.refresh_status()

    def on_case_created(self, case_id: int) -> None:
        """With "Follow new leaks" on, each new case opens by itself and plays its funnel."""
        if self._unlocked and self.pages["leaks"].follow:
            self.open_case(case_id, play=True)

    def refresh(self) -> None:
        if self._unlocked:
            self.stack.currentWidget().refresh()

    def refresh_status(self) -> None:
        if not self._unlocked or self.replay is not None:
            return
        from ..reader import available
        self.status.show_status(queries.status(self.conn), self.background.telegram if self.background else None,
                                available())

    def closeEvent(self, event) -> None:
        self._idle.stop()
        self._status_timer.stop()
        if self.background is not None:
            self.background.stop()
        if self.vault is not None:
            audit.record(self.conn, "stopped")
        self.conn.close()
        super().closeEvent(event)
