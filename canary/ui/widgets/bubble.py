from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import theme


class Bubble(QWidget):
    """One OMR bubble: empty in dropout ink, or filled in ballpoint."""

    def __init__(self, filled: bool = False, size: int = 20, parent=None):
        super().__init__(parent)
        self._filled, self._size = filled, size
        self.setFixedSize(QSize(size, size))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_filled(self, filled: bool) -> None:
        self._filled = filled
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, self._size - 3, self._size - 3)
        if self._filled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.BALLPOINT)
        else:
            painter.setPen(QPen(theme.DROPOUT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
