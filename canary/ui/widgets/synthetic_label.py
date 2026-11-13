from PySide6.QtWidgets import QLabel, QSizePolicy

from .. import theme


class SyntheticLabel(QLabel):
    """Shown wherever demo data appears, so it is never mistaken for a real exam or real people."""

    def __init__(self, parent=None):
        super().__init__("Mock exam, synthetic people", parent)
        self.setStyleSheet(f"border: 1px solid {theme.CARBON.name()}; padding: 3px 10px; font-size: 14px;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
