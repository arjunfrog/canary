from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from .. import theme


class StatusLine(QLabel):
    """Watched chats, Telegram and the photo reader at a glance, one fact per line, at the foot of the sidebar."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setTextFormat(Qt.TextFormat.PlainText)          # chat titles come from Telegram: plain text only
        self.setFont(theme.body(12))
        self.setProperty("role", "muted")
        self.setWordWrap(True)

    def show_replay(self) -> None:
        self.setText("Replay. Nothing is being read or watched, and no network is used.")

    def show_status(self, status, telegram, photo: tuple[bool, str] | None = None) -> None:
        """status: queries.Status. telegram: the listener's state, or None. photo: (available, sentence) from the reader."""
        chats = len(status.watched)
        watching = "Not watching any chats yet." if chats == 0 else f"Watching {chats} chat{'s' if chats != 1 else ''}."
        photo_ok, photo_words = photo if photo is not None else (False, "")
        if telegram is not None and telegram.connected:
            parts = [watching, telegram.message or "Telegram connected."]
        else:
            parts = ["Offline. Typed leaks still work." if not photo_ok else "Offline. Typed leaks and photos still work.",
                     watching]
            if telegram and telegram.message and "Typed leaks still work" not in telegram.message:
                parts.append(telegram.message)
        if photo_words and (photo_ok or "Typed leaks still work" not in parts[0]):
            parts.append(photo_words.replace(" Typed leaks still work.", ""))
        waiting = status.counts.get("queued", 0) + status.counts.get("reading", 0)
        if waiting:
            parts.append(f"{waiting} leak{'s' if waiting != 1 else ''} waiting to be read.")
        if not status.seeded:
            parts.append("No copies yet. Run: python -m canary seed")
        self.setText("\n".join(parts))
