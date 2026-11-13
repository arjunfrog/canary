from ..widgets import RuledSection
from ..widgets.text import plain
from .placeholder import Page


class LimitsPage(Page):
    """Where tracing works and where it fails. Built in task 12."""

    def __init__(self, window=None):
        super().__init__(window)
        from PySide6.QtWidgets import QVBoxLayout
        section = RuledSection("Limits")
        section.body.addWidget(plain("The chart of where tracing works and where it fails goes here.", 18, role="muted"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section)
        layout.addStretch(1)
