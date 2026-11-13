"""Labels, buttons and small helpers shared by the screens.

Text that came from a leak or from Telegram is untrusted. plain() makes a label that shows its text
exactly as written and never interprets it as rich text or a link.
"""
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton

from .. import theme


def plain(text: str = "", px: int = 14, role: str | None = None, weight: QFont.Weight = QFont.Weight.Normal,
          wrap: bool = False, selectable: bool = False) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)          # never rich text, whatever the string contains
    label.setOpenExternalLinks(False)
    label.setText(text)
    label.setFont(theme.body(px, weight))
    label.setWordWrap(wrap)
    if role:
        label.setProperty("role", role)
    if selectable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def heading(text: str, px: int = 15) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    label.setFont(theme.heading(px))
    return label


def caption(text: str) -> QLabel:
    """A small secondary label over a value."""
    return plain(text, 12, role="muted")


def _button(text: str, kind: str | None) -> QPushButton:
    button = QPushButton(text)
    if kind:
        button.setProperty(kind, True)
    button.setFont(theme.body(14, QFont.Weight.Medium))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def button(text: str) -> QPushButton:
    """A secondary action: white, bordered."""
    return _button(text, None)


def primary_button(text: str) -> QPushButton:
    """The one main action of a screen."""
    return _button(text, "primary")


def link_button(text: str) -> QPushButton:
    """A quiet action that reads as a link."""
    return _button(text, "link")


def when(iso: str | None) -> str:
    """An ISO time as "13 Nov 2026, 09:30" in the laptop's own time zone."""
    if not iso:
        return "Time not known"
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return "Time not known"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone()
    return f"{local.day} {local.strftime('%b %Y, %H:%M')}"


def short_when(iso: str | None) -> str:
    """An ISO time as "13 Nov, 09:30", for rows where the year is the same throughout."""
    full = when(iso)
    if full == "Time not known":
        return full
    day_month_year, clock = full.split(", ")
    return f"{day_month_year.rsplit(' ', 1)[0]}, {clock}"


def one_in(expected: float | None) -> str:
    """Expected false matches in plain words: "1 in 2,700,000", or how many copies fit by luck."""
    if expected is None:
        return "Not worked out"
    if expected >= 1:
        return f"about {expected:,.0f} copies" if expected >= 1.5 else "about 1 copy"
    odds = 1 / expected if expected > 0 else float("inf")
    if odds >= 1e12:
        return "under 1 in a trillion"
    if odds >= 1e6:
        return f"1 in {odds / 1e6:,.1f} million" if odds < 1e7 else f"1 in {odds / 1e6:,.0f} million"
    return f"1 in {odds:,.0f}"


def read_time(elapsed_ms: int | None) -> str:
    if elapsed_ms is None:
        return ""
    seconds = elapsed_ms / 1000
    if seconds < 1:
        return "Read in under 1 s"
    return f"Read in {seconds:.0f} s" if seconds >= 10 else f"Read in {seconds:.1f} s"


STAGE_WORDS = {"translation": "Leaked before printing", "print": "Leaked after printing"}
COPY_WORDS = {"translation": "Translator copy", "print": "Printed copy"}
