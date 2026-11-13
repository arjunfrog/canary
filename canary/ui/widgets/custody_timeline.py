from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme
from .text import when


class CustodyTimeline(QWidget):
    """Who held a copy, handover by handover. The handover in force when the leak was posted is filled in."""

    ROW = 62

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list = []
        self._ok: bool | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_events(self, events: list, ok: bool | None) -> None:
        self._events, self._ok = list(events), ok
        self.setFixedHeight(self.sizeHint().height())
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(360, len(self._events) * self.ROW + 34 if self._events else 30)

    def verdict_text(self) -> str:
        if not self._events:
            return "No handover log for this copy."
        if self._ok:
            return "The handover log checks out. Every entry's hash fits the one before it."
        return "The handover log has been changed since it was written. Do not rely on it."

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = 9.0
        if len(self._events) > 1:
            painter.setPen(QPen(theme.DROPOUT, 1.5))
            painter.drawLine(QPointF(x, 12), QPointF(x, (len(self._events) - 1) * self.ROW + 12))
        for i, e in enumerate(self._events):
            y = i * self.ROW
            centre = QPointF(x, y + 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.BOND)
            painter.drawEllipse(centre, 9, 9)                  # clears the line behind the bubble
            if e.in_force:
                painter.setBrush(theme.BALLPOINT)
                painter.drawEllipse(centre, 8, 8)
            else:
                painter.setPen(QPen(theme.DROPOUT, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(centre, 7, 7)
            left = 30
            width = self.width() - left
            painter.setPen(theme.SEAL if not e.ok else (theme.BALLPOINT if e.in_force else theme.CARBON))
            painter.setFont(theme.body(16, QFont.Weight.Medium))
            who = e.to_name or "Not recorded"
            if e.to_role:
                who += f", {e.to_role.lower()}"
            title = painter.fontMetrics().elidedText(who, Qt.TextElideMode.ElideRight, width)
            painter.drawText(QRectF(left, y, width, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
            painter.setPen(theme.MUTED)
            painter.setFont(theme.body(14))
            detail = f"{when(e.at)}. {e.note}"
            if e.to_organisation:
                detail += f" ({e.to_organisation})"
            if not e.ok:
                detail = "This entry no longer matches its hash. " + detail
            detail = painter.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight, width)
            painter.drawText(QRectF(left, y + 23, width, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, detail)
            if e.in_force:
                painter.setPen(theme.BALLPOINT)
                painter.drawText(QRectF(left, y + 41, width, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 "Held the copy when the leak was posted")
        painter.setFont(theme.body(14))
        painter.setPen(theme.MUTED if self._ok or not self._events else theme.SEAL)
        top = len(self._events) * self.ROW + 6 if self._events else 4
        painter.drawText(QRectF(0, top, self.width(), 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(self.verdict_text(), Qt.TextElideMode.ElideRight, self.width()))
