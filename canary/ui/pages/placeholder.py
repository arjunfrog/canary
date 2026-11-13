from PySide6.QtWidgets import QWidget


class Page(QWidget):
    """What every screen shares. The window calls these."""

    def __init__(self, window=None):
        super().__init__()
        self.app_window = window

    @property
    def conn(self):
        return self.app_window.conn

    def refresh(self) -> None:
        """Reread the database. Called when the screen is shown and when the background thread reports a change."""

    def marks(self) -> list[bool]:
        """The timing marks to show on the left edge while this screen is up."""
        return [False] * 14

    def on_lock(self) -> None:
        """The window is locking: close dialogs and stop anything that moves."""
