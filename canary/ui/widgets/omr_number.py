from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme
from .bubble import Bubble


class OMRNumber(QWidget):
    """A copy number drawn the way an answer sheet records a roll number: ten bubbles per digit."""

    def __init__(self, value: int, digits: int = 4, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for digit in str(value).zfill(digits):
            column = QVBoxLayout()
            column.setSpacing(2)
            label = QLabel(digit)
            label.setFont(theme.display(18))
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(label)
            for n in range(10):
                column.addWidget(Bubble(filled=str(n) == digit, size=12))
            row.addLayout(column)
        self.setAccessibleName(f"Copy {str(value).zfill(digits)}")
