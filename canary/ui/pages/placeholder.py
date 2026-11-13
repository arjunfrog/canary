from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..widgets import RuledSection


class PlaceholderPage(QWidget):
    """A screen whose task has not been done yet. It says what will go here and which task builds it."""

    title = ""
    what = ""
    task = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        section = RuledSection(self.title)
        note = QLabel(f"{self.what} This screen is task {self.task} in docs/PROMPTS.md.")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        section.body.addWidget(note)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section)
        layout.addStretch(1)

    def refresh(self) -> None:
        """Called when the background thread reports new or changed leaks."""
