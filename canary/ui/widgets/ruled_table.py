from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyle, QStyledItemDelegate, QTableView

from .. import theme

# Extra roles a model can answer to style one cell.
BubbleRole = Qt.ItemDataRole.UserRole + 1        # True: filled bubble, False: empty bubble, None: no bubble
ToneRole = Qt.ItemDataRole.UserRole + 2          # "traced" | "lead" | "muted" | "seal" | None


class _RuledDelegate(QStyledItemDelegate):
    """Draws a cell as plain text on a ruled line. Never rich text, so leaked text is shown exactly as written."""

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setPen(QPen(theme.RULE, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        if index.column() == 0 and (selected or hovered):
            painter.fillRect(rect.left(), rect.top() + 6, 3, rect.height() - 12, theme.BALLPOINT)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        tone = index.data(ToneRole)
        bubble = index.data(BubbleRole)
        left = rect.left() + (12 if index.column() == 0 else 0)
        font = index.data(Qt.ItemDataRole.FontRole) or option.font
        painter.setFont(font)
        if bubble is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            circle = QRectF(left + 1, rect.center().y() - 6, 13, 13)
            if bubble:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.BALLPOINT)
            else:
                painter.setPen(QPen(theme.DROPOUT, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle)
            left += 24
        text_rect = rect.adjusted(left - rect.left(), 0, -12, 0)
        metrics = painter.fontMetrics()
        shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        if tone == "traced":                               # highlighter is for the Traced verdict, always with black text
            width = min(metrics.horizontalAdvance(shown) + 16, text_rect.width())
            painter.fillRect(text_rect.left() - 8, rect.center().y() - 13, width, 27, theme.HIGHLIGHTER)
            painter.setPen(theme.TIMING)
        elif tone == "lead":
            painter.setPen(theme.BALLPOINT)
        elif tone == "muted":
            painter.setPen(theme.MUTED)
        elif tone == "seal":
            painter.setPen(theme.SEAL)
        else:
            painter.setPen(theme.CARBON)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, shown)
        painter.restore()


class RuledTable(QTableView):
    """A table that looks like the sheet: ruled rows, no grid, a plain left-aligned header."""

    def __init__(self, parent=None, row_height: int = 44):
        super().__init__(parent)
        self.setItemDelegate(_RuledDelegate(self))
        self.setShowGrid(False)
        self.setFrameShape(QTableView.Shape.NoFrame)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setMouseTracking(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setFont(theme.body(16))
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header = self.horizontalHeader()
        header.setFont(theme.body(14))
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setStretchLastSection(True)
        header.setMinimumHeight(34)
        self.viewport().setAutoFillBackground(False)
