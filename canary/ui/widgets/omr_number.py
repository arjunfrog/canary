from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme


class OMRNumber(QWidget):
    """A copy number drawn the way an answer sheet records a roll number: ten bubbles per digit, one filled in."""

    BUBBLE, PITCH, COLUMN, TOP, LEFT = 15, 18, 30, 46, 22

    def __init__(self, value: int, digits: int = 4, parent=None):
        super().__init__(parent)
        self._digits = str(int(value)).zfill(digits)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(f"Copy {self._digits}")

    def sizeHint(self) -> QSize:
        return QSize(self.LEFT + len(self._digits) * self.COLUMN + 2, self.TOP + 10 * self.PITCH + 2)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(theme.body(12))
        painter.setPen(theme.MUTED)
        for n in range(10):                                   # the row labels down the left, as on a real sheet
            painter.drawText(QRectF(0, self.TOP + n * self.PITCH, self.LEFT - 8, self.BUBBLE),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(n))
        for column, digit in enumerate(self._digits):
            x = self.LEFT + column * self.COLUMN
            painter.setPen(theme.CARBON)
            painter.setFont(theme.display(34))
            painter.drawText(QRectF(x - 6, 0, self.BUBBLE + 12, self.TOP - 8),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, digit)
            for n in range(10):
                centre = QPointF(x + self.BUBBLE / 2, self.TOP + n * self.PITCH + self.BUBBLE / 2)
                if str(n) == digit:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(theme.BALLPOINT)
                    painter.drawEllipse(centre, self.BUBBLE / 2, self.BUBBLE / 2)
                else:
                    painter.setPen(QPen(theme.DROPOUT, 1.4))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(centre, self.BUBBLE / 2 - 1, self.BUBBLE / 2 - 1)
