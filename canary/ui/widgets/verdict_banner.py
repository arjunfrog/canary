from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from .. import theme

# verdict -> (title, note, text colour, box style)
WORDS = {
    "traced": ("Traced", "A wrong match is under 1 in 1,000,000.",
               theme.TIMING, f"background: {theme.HIGHLIGHTER.name()};"),
    "strong_lead": ("Strong lead", "A person should investigate this copy.",
                    theme.BALLPOINT, f"border: 2px solid {theme.BALLPOINT.name()};"),
    "inconclusive": ("Not enough to name anyone yet", "Too few clues to reach the bar.",
                     theme.MUTED, f"border: 1px solid {theme.RULE.name()};"),
    "not_our_paper": ("Not our paper", "These questions are not in the bank. Likely a fake leak.",
                      theme.SEAL, f"border: 2px solid {theme.SEAL.name()};"),
}


class VerdictBanner(QFrame):
    """The verdict in words. Highlighter yellow is used for Traced only, always with black text."""

    def __init__(self, verdict: str, parent=None):
        super().__init__(parent)
        title_text, note_text, colour, box = WORDS[verdict]
        self.verdict = verdict
        self.setObjectName("verdict")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"#verdict {{ {box} }} #verdict QLabel {{ color: {colour.name()}; background: transparent; border: none; }}")
        title = QLabel(title_text)
        title.setFont(theme.display(34))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 14)
        layout.setSpacing(0)
        layout.addWidget(title)
        layout.addWidget(QLabel(note_text))
