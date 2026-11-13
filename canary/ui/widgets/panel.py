from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .text import heading, plain


def divider(vertical: bool = False) -> QFrame:
    """A 1px line in the border colour."""
    line = QFrame()
    line.setObjectName("divider")
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


class Panel(QFrame):
    """A white bordered panel: a title row with optional actions on the right, a divider, then its body.

    `body` takes the content. `actions` takes buttons or small widgets for the title row. Panels are never
    nested inside each other.
    """

    PAD = 12

    def __init__(self, title: str = "", parent=None, subtitle: str = "", flush: bool = False, scroll: bool = False):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.title = heading(title, 14)
        self.subtitle = plain(subtitle, 12, role="muted")
        self.subtitle.setVisible(bool(subtitle))
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        self.header = QWidget()
        row = QHBoxLayout(self.header)
        row.setContentsMargins(self.PAD, 8, self.PAD, 8)
        row.setSpacing(10)
        row.addWidget(self.title)
        row.addWidget(self.subtitle)
        row.addStretch(1)
        row.addLayout(self.actions)
        self.header.setVisible(bool(title))
        outer.addWidget(self.header)
        self.rule = divider()
        self.rule.setVisible(bool(title))
        outer.addWidget(self.rule)
        holder = QWidget()
        self.body = QVBoxLayout(holder)
        pad = 0 if flush else self.PAD
        self.body.setContentsMargins(pad, 0 if flush else 10, pad, 0 if flush else self.PAD)
        self.body.setSpacing(8)
        if scroll:                                  # long content scrolls inside the panel, not the whole screen
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(holder)
            area.viewport().setAutoFillBackground(False)
            holder.setAutoFillBackground(False)
            outer.addWidget(area, 1)
        else:
            outer.addWidget(holder, 1)

    def set_title(self, text: str) -> None:
        self.title.setText(text)
        self.header.setVisible(bool(text))
        self.rule.setVisible(bool(text))
