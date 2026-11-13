from PySide6.QtWidgets import QLabel


class StatusLine(QLabel):
    """Telegram, photo reader and watched chats at a glance. Filled in by task 10."""

    def __init__(self, parent=None):
        super().__init__("Worker: on.  Telegram listener: not built yet.  Photo reader: not built yet.", parent)
        self.setProperty("role", "small")
