from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from .. import theme


class StatusLine(QLabel):
    """Watched chats, Telegram and the photo reader at a glance."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setTextFormat(Qt.TextFormat.PlainText)          # chat titles come from Telegram: plain text only
        self.setFont(theme.body(14))
        self.setProperty("role", "small")

    def show_replay(self) -> None:
        self.setText("Replay. Nothing is being read or watched, and no network is used.")

    def show_status(self, status, telegram, vault, reader_reachable: bool | None = None) -> None:
        """status: queries.Status. telegram: the listener's state, or None. reader_reachable: None if not checked."""
        chats = len(status.watched)
        watching = "Not watching any chats yet." if chats == 0 else f"Watching {chats} chat{'s' if chats != 1 else ''}."
        connected = bool(telegram and telegram.connected)
        has_key = bool(vault and vault.get("gemini_api_key"))
        reader_up = has_key and reader_reachable is not False
        if not connected and not reader_up:
            parts = ["Offline. Typed leaks still work.", watching]
            if telegram and telegram.message and "Typed leaks still work" not in telegram.message:
                parts.append(telegram.message)
            if not has_key:
                parts.append("No photo reader key in the vault.")
        else:
            parts = [watching, (telegram.message or "Telegram connected.") if connected
                     else (telegram.message if telegram else "Telegram is off.")]
            if not has_key:
                parts.append("No photo reader key in the vault, so photos cannot be read.")
            elif reader_reachable is False:
                parts.append("Photo reader not reachable.")
            else:
                parts.append("Photo reader ready.")
        waiting = status.counts.get("queued", 0) + status.counts.get("reading", 0)
        if waiting:
            parts.append(f"{waiting} leak{'s' if waiting != 1 else ''} waiting to be read.")
        if not status.seeded:
            parts.append("No copies yet. Run: python -m canary seed")
        self.setText("  ".join(parts))
