from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from .. import theme


class TimingMarks(QWidget):
    """The black marks down the edge of an answer sheet. Each mark is one item, and `done` of them are black."""

    MARK_W, MARK_H, GAP = 32, 8, 18

    def __init__(self, total: int, done: int = 0, parent=None):
        super().__init__(parent)
        self._total, self._done = total, done
        self.setFixedSize(QSize(self.MARK_W, total * (self.MARK_H + self.GAP)))

    def set_progress(self, total: int, done: int) -> None:
        self._total, self._done = total, done
        self.setFixedSize(QSize(self.MARK_W, total * (self.MARK_H + self.GAP)))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        for i in range(self._total):
            colour = theme.TIMING if i < self._done else theme.RULE
            painter.fillRect(0, i * (self.MARK_H + self.GAP), self.MARK_W, self.MARK_H, colour)
