from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyle, QStyledItemDelegate, QTableView

from .. import theme

# Extra roles a model can answer to style one cell.
MarkRole = Qt.ItemDataRole.UserRole + 1          # True: filled mark, False: hollow mark, None: no mark
ToneRole = Qt.ItemDataRole.UserRole + 2          # "muted" | "error" | None
PillRole = Qt.ItemDataRole.UserRole + 3          # a tone name from theme.TONES: draw the text as a pill
BubbleRole = MarkRole                            # the name used before the redesign


class _RowDelegate(QStyledItemDelegate):
    """Draws a cell as plain text on a row with one hairline under it. Never rich text, so leaked text is
    shown exactly as written."""

    PAD = 10

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, theme.ACCENT_SOFT)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, theme.SUNKEN)
        painter.setPen(QPen(theme.BORDER, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        font = index.data(Qt.ItemDataRole.FontRole) or option.font
        painter.setFont(font)
        left = rect.left() + self.PAD
        mark = index.data(MarkRole)
        if mark is not None:
            box = QRectF(left, rect.center().y() - 4.5, 9, 9)
            if mark:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.ACCENT)
            else:
                painter.setPen(QPen(theme.INK_3, 1.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 2, 2)
            left += 17
        text_rect = rect.adjusted(left - rect.left(), 0, -self.PAD, 0)
        pill = index.data(PillRole)
        if pill:
            ink, fill = theme.TONES.get(pill, theme.TONES["inconclusive"])
            pill_font = theme.body(12, QFont.Weight.DemiBold)
            painter.setFont(pill_font)
            metrics = painter.fontMetrics()
            shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width() - 16)
            box = QRectF(text_rect.left(), rect.center().y() - 10, metrics.horizontalAdvance(shown) + 16, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(box, 10, 10)
            painter.setPen(ink)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, shown)
            painter.restore()
            return
        tone = index.data(ToneRole)
        painter.setPen(theme.INK_2 if tone == "muted" else theme.DANGER if tone == "error" else theme.INK)
        shown = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, shown)
        painter.restore()


class RuledTable(QTableView):
    """A console table: compact rows, one hairline between them, a quiet header, no grid."""

    def __init__(self, parent=None, row_height: int = 36):
        super().__init__(parent)
        self.setItemDelegate(_RowDelegate(self))
        self.setShowGrid(False)
        self.setFrameShape(QTableView.Shape.NoFrame)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setMouseTracking(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setFont(theme.body(14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self.horizontalHeader()
        header.setFont(theme.body(12, QFont.Weight.Medium))
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setStretchLastSection(True)
        header.setFixedHeight(30)
        self.viewport().setAutoFillBackground(False)
