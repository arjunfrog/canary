from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ...lock import LockGuard
from .. import theme


class LockPage(QWidget):
    """Asks for the passphrase: when the app starts, and again after it has sat idle."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.guard = LockGuard()
        name = QLabel("Canary")
        name.setFont(theme.display(120))
        self.prompt = QLabel("Type the passphrase to unlock.")
        self.field = QLineEdit()
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText("Passphrase")
        self.field.setFixedWidth(420)
        self.field.returnPressed.connect(self._submit)
        self.button = QPushButton("Unlock")
        self.button.setProperty("primary", True)
        self.button.clicked.connect(self._submit)
        self.message = QLabel("")
        self.message.setProperty("role", "error")

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.field)
        row.addWidget(self.button)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(name)
        layout.addWidget(self.prompt)
        layout.addLayout(row)
        layout.addWidget(self.message)
        layout.addStretch(1)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

    def show_message(self, text: str) -> None:
        self.message.setText(text)

    def _submit(self) -> None:
        if self.guard.blocked_for() > 0:
            return
        text = self.field.text()
        self.field.clear()
        if text:
            self.submitted.emit(text)

    def wrong(self) -> None:
        """The owner calls this when the passphrase was wrong."""
        self.guard.failed()
        if self.guard.blocked_for() > 0:
            self._tick()
            self._countdown.start()
        else:
            self.show_message("That passphrase is not right.")

    def right(self) -> None:
        self.guard.succeeded()
        self.show_message("")

    def _tick(self) -> None:
        left = self.guard.blocked_for()
        blocked = left > 0
        self.field.setDisabled(blocked)
        self.button.setDisabled(blocked)
        if blocked:
            self.show_message(f"Too many wrong tries. Try again in {int(left) + 1} seconds.")
        else:
            self._countdown.stop()
            self.show_message("")
