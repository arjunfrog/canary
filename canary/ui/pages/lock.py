from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from ...lock import LockGuard
from .. import theme
from ..widgets.text import heading, plain, primary_button


class LockPage(QWidget):
    """Asks for the passphrase: when the app starts, and again after it has sat idle."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.guard = LockGuard()
        card = QFrame()
        card.setObjectName("lockcard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setFixedWidth(400)

        mark = QWidget()
        mark.setFixedSize(18, 18)
        mark.setStyleSheet(f"background: {theme.CANARY.name()}; border-radius: 5px;")
        name = heading("Canary", 22)
        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(mark)
        brand.addWidget(name)
        brand.addStretch(1)
        self.prompt = plain("Type the passphrase to unlock.", 14, role="muted", wrap=True)
        self.field = QLineEdit()
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText("Passphrase")
        self.field.setFont(theme.body(15))
        self.field.returnPressed.connect(self._submit)
        self.button = primary_button("Unlock")
        self.button.setMinimumHeight(34)
        self.button.clicked.connect(self._submit)
        self.message = plain("", 13, role="error", wrap=True)
        self.message.setVisible(False)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(24, 22, 24, 22)
        inner.setSpacing(10)
        inner.addLayout(brand)
        inner.addSpacing(2)
        inner.addWidget(self.prompt)
        inner.addSpacing(4)
        inner.addWidget(self.field)
        inner.addWidget(self.button)
        inner.addWidget(self.message)

        column = QVBoxLayout(self)
        column.setContentsMargins(16, 16, 16, 16)
        column.addStretch(3)
        column.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addStretch(4)

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(bool(text))

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
