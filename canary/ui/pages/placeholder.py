from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..widgets.text import heading, plain

GUTTER = 16          # space around the edge of every screen
GAP = 12             # space between panels


class PageHeader(QWidget):
    """A screen's header: title and one line of context on the left, its actions on the right."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.title = heading(title, 20)
        self.subtitle = plain(subtitle, 13, role="muted")
        self.subtitle.setVisible(bool(subtitle))
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(self.title)
        words.addWidget(self.subtitle)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addLayout(words, 1)
        row.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))


class Page(QWidget):
    """What every screen shares. The window calls these."""

    def __init__(self, window=None):
        super().__init__()
        self.app_window = window

    @property
    def conn(self):
        return self.app_window.conn

    @staticmethod
    def frame(widget: QWidget) -> QVBoxLayout:
        """The screen's outer layout, with the standard gutter."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(GUTTER, GUTTER - 2, GUTTER, GUTTER)
        layout.setSpacing(GAP)
        return layout

    def refresh(self) -> None:
        """Reread the database. Called when the screen is shown and when the background thread reports a change."""

    def on_lock(self) -> None:
        """The window is locking: close dialogs and stop anything that moves."""
