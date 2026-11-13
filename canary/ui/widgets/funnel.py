import random

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme

EMPTY = theme.CELL                   # a copy that no longer fits: a quiet grey cell


class Funnel(QWidget):
    """One bubble per candidate copy, emptying clue by clue until the copies that still fit are left.

    The bubbles are drawn into cached pixmaps, and a frame only blends two of them, so 5,000 bubbles stay
    smooth. Which bubble stands for which copy is shuffled, and only counts are shown: the picture never
    says which copies were still in the running.
    """

    PAD = 10                           # room for the ring drawn round a single small cell
    progress = Signal(float)           # how many steps have played, with the fraction of the one in progress
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(320, 200))
        self._n = 0
        self._counts: list[int] = []           # copies still fitting before any clue, then after each one
        self._order: list[int] = []
        self._named = False
        self._position = 0.0
        self._cache: dict = {}
        self._animation = QVariantAnimation(self)
        self._animation.valueChanged.connect(self._on_value)
        self._animation.finished.connect(self.finished.emit)

    # ---- data

    def set_steps(self, candidates: int, steps: list[dict], named: bool, seed: int = 0) -> None:
        """Load a case's funnel. `named` marks the last bubble standing as the copy that was named."""
        self._animation.stop()
        self._n = max(0, int(candidates))
        self._counts = [self._n] + [max(0, min(self._n, int(s.get("remaining", 0)))) for s in steps]
        if named and self._n:
            self._counts[-1] = 1
        self._order = list(range(self._n))
        random.Random(f"funnel-{seed}-{self._n}").shuffle(self._order)
        self._named = named
        self._cache.clear()
        self._position = float(len(self._counts) - 1)
        self.update()

    def steps(self) -> int:
        return max(0, len(self._counts) - 1)

    def position(self) -> float:
        return self._position

    def count_at(self, position: float) -> int:
        if not self._counts:
            return 0
        return self._counts[min(len(self._counts) - 1, max(0, int(round(position))))]

    # ---- playing

    def play(self) -> None:
        """Play once from every copy to the end. With reduced motion, or nothing to play, show the final state."""
        self._animation.stop()
        if theme.reduce_motion() or self.steps() == 0 or self._n == 0:
            self.show_final()
            return
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(float(self.steps()))
        self._animation.setDuration(int(min(9000, max(2600, 420 * self.steps()))))
        self._animation.start()

    def show_final(self) -> None:
        self._animation.stop()
        self._position = float(self.steps())
        self.update()
        self.progress.emit(self._position)
        self.finished.emit()

    def stop(self) -> None:
        if self._animation.state() == QVariantAnimation.State.Running:
            self.show_final()

    def is_playing(self) -> bool:
        return self._animation.state() == QVariantAnimation.State.Running

    def _on_value(self, value) -> None:
        self._position = float(value)
        self.update()
        self.progress.emit(self._position)

    # ---- drawing

    def _grid(self) -> tuple[int, int, float, float, float]:
        """(columns, rows, cell size, left, top) for the bubbles in the current size."""
        pad = self.PAD
        width, height = max(1, self.width() - 2 * pad), max(1, self.height() - 2 * pad)
        best = (1, max(1, self._n), 1.0)
        for cols in range(1, self._n + 1):
            rows = -(-self._n // cols)
            cell = min(width / cols, height / rows)
            if cell > best[2]:
                best = (cols, rows, cell)
            if width / cols < best[2]:
                break
        cols, rows, cell = best
        if cell > 30.0:                                  # cells stay small; spread them across the width instead
            cell = 30.0
            cols = min(self._n, max(1, int(width // cell)))
            rows = -(-self._n // cols)
            cell = min(30.0, height / rows)
        return cols, rows, cell, float(pad if cell < 14 else 0), float(pad if cell < 14 else 0)

    def _centre(self, slot: int, grid) -> QPointF:
        cols, rows, cell, left, top = grid
        return QPointF(left + (slot % cols + 0.5) * cell, top + (slot // cols + 0.5) * cell)

    def _layer(self, kind: str, count: int = 0) -> QPixmap:
        """A cached picture: every bubble empty, or the first `count` bubbles filled."""
        ratio = self.devicePixelRatioF()
        key = (kind, count, self.width(), self.height(), ratio)
        if key in self._cache:
            return self._cache[key]
        if len(self._cache) > 6:
            for old in [k for k in self._cache if k[0] != "empty"][:-3]:
                del self._cache[old]
        pixmap = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grid = self._grid()
        cell = grid[2]
        side = max(1.0, cell * (0.78 if cell >= 8 else 0.86))     # a square with a gap, like a cell in a grid
        corner = min(3.0, side * 0.2)
        painter.setPen(Qt.PenStyle.NoPen)
        if kind == "empty":
            painter.setBrush(EMPTY)
            slots = range(self._n)
        else:
            painter.setBrush(theme.ACCENT)
            slots = self._order[:count]
        for slot in slots:
            c = self._centre(slot, grid)
            painter.drawRoundedRect(QRectF(c.x() - side / 2, c.y() - side / 2, side, side), corner, corner)
        painter.end()
        self._cache[key] = pixmap
        return pixmap

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._n == 0 or not self._counts:
            return
        painter.drawPixmap(0, 0, self._layer("empty"))
        last = len(self._counts) - 1
        index = min(last, int(self._position))
        t = self._position - index if index < last else 0.0
        before, after = self._counts[index], self._counts[min(last, index + 1)]
        if t <= 0.0 or before == after:
            painter.drawPixmap(0, 0, self._layer("filled", before if t <= 0.0 else after))
        else:
            low, high = min(before, after), max(before, after)
            painter.drawPixmap(0, 0, self._layer("filled", low))
            painter.setOpacity(1.0 - t if after < before else t)
            painter.drawPixmap(0, 0, self._layer("filled", high))
            painter.setOpacity(1.0)
        if self._named and self._position >= last and self._order:
            grid = self._grid()
            if grid[2] < 14:                               # a single small cell needs a ring to be found
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(QPen(theme.ACCENT, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                centre = self._centre(self._order[0], grid)
                painter.drawEllipse(centre, 9, 9)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.ACCENT)
                painter.drawEllipse(centre, 3.5, 3.5)

    def resizeEvent(self, event) -> None:
        self._cache.clear()
        super().resizeEvent(event)
