import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import audit, config, db
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
    After 10 minutes with no key or mouse activity it locks again.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Canary")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.vault: Vault | None = None
        self.background: Background | None = None
        self.conn = db.connect()
        self._last_activity = time.monotonic()

        # left rail: timing marks and the margin rule
        self.marks = TimingMarks(total=14, done=0)      # the Case screen sets these: one mark per clue read
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
        self.pages = {"leaks": LeaksPage(), "case": CasePage(), "limits": LimitsPage()}
        self.stack.addWidget(self.lock_page)
        for page in self.pages.values():
            self.stack.addWidget(page)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in (("leaks", "Leaks"), ("limits", "Limits")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("nav", True)
            button.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav.addButton(button)
            nav_layout.addWidget(button)
            self._buttons[key] = button

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
        self.lock(first=True)

    # ---- locking

    @property
    def locked(self) -> bool:
        return self.stack.currentWidget() is self.lock_page

    def lock(self, first: bool = False) -> None:
        self.name.setVisible(False)              # the lock screen shows the name itself, large
        self.nav_bar.setVisible(False)
        self.status.setVisible(False)
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
        audit.record(self.conn, "unlocked")
        if self.background is None:
            self.background = Background(self.vault, self)
            self.background.changed.connect(self.refresh)
            self.background.start()
        self._last_activity = time.monotonic()
        self.name.setVisible(True)
        self.nav_bar.setVisible(True)
        self.status.setVisible(True)
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
        if self.vault is None:
            return
        self.stack.setCurrentWidget(self.pages[key])
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        self.pages[key].refresh()

    def refresh(self) -> None:
        if not self.locked:
            self.stack.currentWidget().refresh()

    def closeEvent(self, event) -> None:
        if self.background is not None:
            self.background.stop()
        if self.vault is not None:
            audit.record(self.conn, "stopped")
        self.conn.close()
        super().closeEvent(event)
