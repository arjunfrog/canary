from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme

SERIES = (
    # key, legend words, colour, line width, dashed, point radius
    ("traced_right", "Right copy traced", theme.BALLPOINT, 2.6, False, 5.5),
    ("lead_right", "Right copy named, strong lead or better", theme.BALLPOINT, 1.4, True, 3.0),
    ("lead_wrong", "A wrong copy named", theme.SEAL, 1.6, False, 3.0),
)


class LimitsChart(QWidget):
    """How often the right copy is named, and a wrong one, against the number of questions leaked.

    Drawn with QPainter. The numbers come from the saved simulation; this widget never runs it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[dict] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(520, 320))

    def set_points(self, points: list[dict]) -> None:
        self._points = list(points)
        self.update()

    def points(self) -> list[dict]:
        return list(self._points)

    def _plot(self) -> QRectF:
        return QRectF(56, 44, self.width() - 56 - 24, self.height() - 44 - 58)

    def _at(self, index: int, share: float) -> QPointF:
        plot = self._plot()
        step = plot.width() / max(1, len(self._points) - 1)
        return QPointF(plot.left() + index * step, plot.bottom() - max(0.0, min(1.0, share)) * plot.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        small = theme.body(13)
        painter.setFont(small)

        # legend, left-aligned above the plot
        x = plot.left()
        for key, words, colour, width, dashed, radius in SERIES:
            pen = QPen(colour, width)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, 16), QPointF(x + 30, 16))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(QPointF(x + 15, 16), radius, radius)
            painter.setPen(theme.CARBON)
            painter.setFont(theme.body(14))
            advance = painter.fontMetrics().horizontalAdvance(words)
            painter.drawText(QRectF(x + 38, 4, advance + 4, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, words)
            x += 38 + advance + 34

        # ruled lines and the percentage scale
        painter.setFont(small)
        for share in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - share * plot.height()
            painter.setPen(QPen(theme.DROPOUT if share == 0 else theme.RULE, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(theme.MUTED)
            painter.drawText(QRectF(0, y - 10, plot.left() - 10, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{share * 100:.0f}%")
        if not self._points:
            return
        for i, point in enumerate(self._points):
            at = self._at(i, 0)
            painter.setPen(QPen(theme.DROPOUT, 1))
            painter.drawLine(QPointF(at.x(), plot.bottom()), QPointF(at.x(), plot.bottom() + 5))
            painter.setPen(theme.CARBON)
            painter.drawText(QRectF(at.x() - 30, plot.bottom() + 8, 60, 20), Qt.AlignmentFlag.AlignHCenter, str(point["k"]))
        painter.setPen(theme.MUTED)
        painter.drawText(QRectF(plot.left(), plot.bottom() + 30, plot.width(), 22),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Questions in the leak")

        # the lines, least important first so the traced line sits on top
        for key, words, colour, width, dashed, radius in reversed(SERIES):
            path = QPainterPath()
            for i, point in enumerate(self._points):
                at = self._at(i, point[key])
                path.moveTo(at) if i == 0 else path.lineTo(at)
            pen = QPen(colour, width)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            for i, point in enumerate(self._points):
                painter.drawEllipse(self._at(i, point[key]), radius, radius)

        # the traced line carries its numbers
        painter.setFont(theme.body(14))
        painter.setPen(theme.BALLPOINT)
        for i, point in enumerate(self._points):
            share = point["traced_right"]
            at = self._at(i, share)
            words = f"{share * 100:.0f}%" if share in (0.0, 1.0) or abs(share * 100 - round(share * 100)) < 0.05 else f"{share * 100:.1f}%"
            below = share > 0.9
            advance = painter.fontMetrics().horizontalAdvance(words)
            box = QRectF(at.x() - advance / 2 - 3, at.y() + (10 if below else -30), advance + 6, 20)
            painter.fillRect(box, theme.BOND)                  # keeps the number readable where another line passes
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, words)
