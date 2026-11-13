from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme
from .text import short_when, when


class CustodyTimeline(QWidget):
    """Who held a copy, one line per handover: when, who, what happened.

    The handover in force when the leak was posted is set in bold ink and says so.
    """

    ROW = 40
    HELD = 18                     # the extra line under the handover in force when the leak was posted

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
        extra = self.HELD if any(e.in_force for e in self._events) else 0
        return QSize(320, len(self._events) * self.ROW + extra + 40 if self._events else 36)

    def verdict_text(self) -> str:
        if not self._events:
            return "No handover log for this copy."
        if self._ok:
            return "The handover log checks out. Every entry's hash fits the one before it."
        return "The handover log has been changed since it was written. Do not rely on it."

    def paintEvent(self, event) -> None:
        """Each handover is two lines: when and who, then what happened. Nothing in the record is cut off."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, first = 5.0, 10.0
        tops, y = [], 0.0
        for e in self._events:
            tops.append(y)
            y += self.ROW + (self.HELD if e.in_force else 0)
        if len(self._events) > 1:
            painter.setPen(QPen(theme.BORDER_STRONG, 1.2))
            painter.drawLine(QPointF(x, first), QPointF(x, tops[-1] + first))
        date_font, name_font = theme.body(12), theme.body(13, QFont.Weight.Medium)
        bold = theme.body(13, QFont.Weight.DemiBold)
        date_w = QFontMetrics(date_font).horizontalAdvance("30 Nov, 23:59") + 10
        left = 18.0
        width = self.width() - left
        for i, e in enumerate(self._events):
            y = tops[i]
            centre = QPointF(x, y + first)
            if e.in_force:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.INK)
                painter.drawEllipse(centre, 4.5, 4.5)
            else:
                painter.setPen(QPen(theme.INK_3, 1.2))
                painter.setBrush(theme.SURFACE)
                painter.drawEllipse(centre, 3.5, 3.5)
            painter.setFont(date_font)
            painter.setPen(theme.DANGER if not e.ok else theme.INK_2)
            painter.drawText(QRectF(left, y, date_w, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             short_when(e.at))
            who = e.to_name or "Not recorded"           # the action line says what they did; lines() keeps the role
            painter.setFont(bold if e.in_force else name_font)
            painter.setPen(theme.DANGER if not e.ok else theme.INK)
            name_rect = QRectF(left + date_w, y, width - date_w, 20)
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             painter.fontMetrics().elidedText(who, Qt.TextElideMode.ElideRight, int(name_rect.width())))
            note = e.note if e.ok else f"This entry no longer matches its hash. {e.note}"
            painter.setFont(date_font)
            painter.setPen(theme.DANGER if not e.ok else theme.INK_2)
            painter.drawText(QRectF(left, y + 18, width, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             painter.fontMetrics().elidedText(note, Qt.TextElideMode.ElideRight, int(width)))
            if e.in_force:                              # on its own line, so it is never cut off
                painter.setFont(bold)
                painter.setPen(theme.INK)
                painter.drawText(QRectF(left, y + 36, width, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 "Held the copy when the leak was posted")
        painter.setFont(theme.body(12))
        painter.setPen(theme.INK_2 if self._ok or not self._events else theme.DANGER)
        top = (tops[-1] + self.ROW + (self.HELD if self._events[-1].in_force else 0) + 2) if self._events else 2
        painter.drawText(QRectF(0, top, self.width(), 34), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                         | Qt.TextFlag.TextWordWrap, self.verdict_text())

    def lines(self) -> list[str]:
        """The handovers as plain text, one per line. For tests and for anyone reading the screen aloud."""
        out = []
        for e in self._events:
            who = (e.to_name or "Not recorded") + (f", {e.to_role.lower()}" if e.to_role else "")
            note = ("held it at the leak" if e.in_force else e.note) if e.ok else "no longer matches its hash"
            out.append(f"{when(e.at)} · {who} · {note}")
        return out
