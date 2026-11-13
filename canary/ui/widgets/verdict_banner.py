from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout

from .. import theme
from .text import heading, plain

# verdict -> (title, note, text colour, box style)
WORDS = {
    "traced": ("Traced", "A wrong match is under 1 in 1,000,000.",
               theme.TIMING, f"background: {theme.HIGHLIGHTER.name()};"),
    "strong_lead": ("Strong lead", "A person should investigate this copy before any action.",
                    theme.BALLPOINT, f"border: 2px solid {theme.BALLPOINT.name()};"),
    "inconclusive": ("Not enough to name anyone yet", "Too few clues to reach the bar. No copy is named.",
                     theme.MUTED, f"border: 1px solid {theme.RULE.name()};"),
    "not_our_paper": ("Not our paper", "These questions are not in the bank. Likely a fake leak.",
                      theme.SEAL, f"border: 2px solid {theme.SEAL.name()};"),
    # leak states that have no verdict
    "unreadable": ("We couldn't read this clearly.", "Too poor to tell whose paper it is. Try a sharper photo, or type the questions in.",
                   theme.MUTED, f"border: 1px solid {theme.RULE.name()};"),
    "queued": ("Waiting to be read", "This leak is in the queue.",
               theme.MUTED, f"border: 1px solid {theme.RULE.name()};"),
    "reading": ("Being read now", "The verdict appears here when it is done.",
                theme.MUTED, f"border: 1px solid {theme.RULE.name()};"),
    "failed": ("This leak could not be analysed", "",
               theme.SEAL, f"border: 2px solid {theme.SEAL.name()};"),
}


class VerdictBanner(QFrame):
    """The verdict in words. Highlighter yellow is used for Traced only, always with black text."""

    def __init__(self, verdict: str, parent=None, note: str | None = None):
        super().__init__(parent)
        self.setObjectName("verdict")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.title = heading("", 34, semibold=True)
        self.note = plain("", 16, wrap=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 14)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.note)
        self.verdict = verdict
        self.set_verdict(verdict, note)

    def set_verdict(self, verdict: str, note: str | None = None) -> None:
        title_text, note_text, colour, box = WORDS[verdict]
        self.verdict = verdict
        self.setStyleSheet(f"#verdict {{ {box} }} #verdict QLabel {{ color: {colour.name()}; background: transparent; border: none; }}")
        self.title.setText(title_text)
        self.note.setText(note if note is not None else note_text)
        self.note.setVisible(bool(self.note.text()))
