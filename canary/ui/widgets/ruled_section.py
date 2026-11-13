from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from .. import theme


def rule(colour=theme.DROPOUT) -> QFrame:
    """A thin horizontal rule. Regions are separated by rules, never by cards."""
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {colour.name()};")
    return line


class RuledSection(QWidget):
    """A region of the sheet: a heading over a dropout rule, then its content."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 12, 0, 0)
        heading = QLabel()
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setText(title)
        heading.setFont(theme.display(30, semibold=False))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 28)
        outer.setSpacing(2)
        outer.addWidget(heading)
        outer.addWidget(rule())
        outer.addLayout(self.body)
