from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from .. import theme


class TimingMarks(QWidget):
    """The black marks down the edge of an answer sheet. Each mark is one item, black when it is done.

    The screen being shown decides what the marks stand for. On the Case screen it is one mark per clue,
    black when the clue was read.
    """

    MARK_W, MARK_H, GAP = 32, 8, 18
    MAX_HEIGHT = 700

    def __init__(self, total: int, done: int = 0, parent=None):
        super().__init__(parent)
        self._states: list[bool] = []
        self.set_progress(total, done)

    def set_progress(self, total: int, done: int) -> None:
        self.set_states([i < done for i in range(total)])

    def set_states(self, states: list[bool]) -> None:
        self._states = list(states)
        self.setFixedSize(QSize(self.MARK_W, max(1, int(self._pitch() * len(self._states)))))
        self.update()

    def states(self) -> list[bool]:
        return list(self._states)

    def _pitch(self) -> float:
        """Marks keep their usual spacing until there are too many, then move closer to stay on the sheet."""
        full = self.MARK_H + self.GAP
        return min(full, self.MAX_HEIGHT / len(self._states)) if self._states else full

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        pitch = self._pitch()
        height = max(2, min(self.MARK_H, int(pitch * 0.45)))
        for i, done in enumerate(self._states):
            painter.fillRect(0, int(i * pitch), self.MARK_W, height, theme.TIMING if done else theme.RULE)
