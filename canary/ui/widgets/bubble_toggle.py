from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

from .. import theme


class BubbleToggle(QAbstractButton):
    """A choice marked the way an answer sheet is: an empty bubble, or one filled in with ballpoint."""

    BUBBLE = 18

    def __init__(self, text: str, parent=None, px: int = 16):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(text)
        self.setFont(theme.body(px))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(self.BUBBLE + 10 + metrics.horizontalAdvance(self.text()) + 4, max(self.BUBBLE, metrics.height()) + 8)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - self.BUBBLE) / 2
        rect = QRectF(1.5, top + 1.5, self.BUBBLE - 3, self.BUBBLE - 3)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.BALLPOINT)
        else:
            painter.setPen(QPen(theme.DROPOUT, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        painter.setPen(theme.BALLPOINT if self.isChecked() else theme.CARBON)
        painter.setFont(self.font())
        text_rect = self.rect().adjusted(self.BUBBLE + 10, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.hasFocus():
            painter.setPen(QPen(theme.BALLPOINT, 2))
            painter.drawLine(self.BUBBLE + 10, self.height() - 2, self.width() - 2, self.height() - 2)
