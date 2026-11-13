from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QVBoxLayout, QWidget

from .. import theme
from .text import plain

# verdict or leak state -> (words on the pill, the note under it, tone)
VERDICTS = {
    "traced": ("Traced", "A wrong match is under 1 in 1,000,000.", "traced"),
    "strong_lead": ("Strong lead", "A person should investigate this copy before any action.", "strong_lead"),
    "inconclusive": ("Not enough to name anyone yet", "Too few clues to reach the bar. No copy is named.", "inconclusive"),
    "not_our_paper": ("Not our paper", "These questions are not in the bank. Likely a fake leak.", "not_our_paper"),
    "unreadable": ("We couldn't read this clearly", "Too poor to tell whose paper it is. Try a sharper photo.",
                   "unreadable"),
    "queued": ("Waiting to be read", "This leak is in the queue.", "waiting"),
    "reading": ("Being read now", "The verdict appears here when it is done.", "waiting"),
    "failed": ("This leak could not be analysed", "", "failed"),
}


class Pill(QWidget):
    """A status pill: rounded, tinted with its tone, text in the tone's ink. The words carry the meaning too."""

    def __init__(self, text: str = "", tone: str = "inconclusive", px: int = 13, parent=None):
        super().__init__(parent)
        self._text, self._tone, self._px = text, tone, px
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set(self, text: str, tone: str) -> None:
        self._text, self._tone = text, tone
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def tone(self) -> str:
        return self._tone

    def _font(self) -> QFont:
        return theme.body(self._px, QFont.Weight.DemiBold)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self._font())
        return QSize(metrics.horizontalAdvance(self._text) + 2 * round(self._px * 0.7), round(self._px * 1.75))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        ink, fill = theme.TONES.get(self._tone, theme.TONES["inconclusive"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(ink)
        painter.setFont(self._font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)


class VerdictBadge(QWidget):
    """The verdict as a pill with one plain sentence under it. Used wherever a verdict is the headline."""

    def __init__(self, verdict: str = "inconclusive", parent=None, note: str | None = None, px: int = 14):
        super().__init__(parent)
        self.pill = Pill(px=px)
        self.note = plain("", 13, role="muted", wrap=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.note)
        self.verdict = verdict
        self.set_verdict(verdict, note)

    @property
    def title(self):
        """The pill, which has text() like a label."""
        return self.pill

    def set_verdict(self, verdict: str, note: str | None = None) -> None:
        words, default_note, tone = VERDICTS[verdict]
        self.verdict = verdict
        self.pill.set(words, tone)
        self.note.setText(note if note is not None else default_note)
        self.note.setVisible(bool(self.note.text()))


class Switch(QAbstractButton):
    """An on/off switch with its label to the right. Checkable, keyboard-operable, drawn in the theme."""

    TRACK_W, TRACK_H = 30, 18

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setText(text)
        self.setFont(theme.body(14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(self.TRACK_W + 8 + metrics.horizontalAdvance(self.text()) + 2, max(self.TRACK_H, metrics.height()) + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - self.TRACK_H) / 2
        track = QRectF(0.5, top + 0.5, self.TRACK_W - 1, self.TRACK_H - 1)
        painter.setPen(theme.ACCENT_HOVER if self.hasFocus() else Qt.PenStyle.NoPen)
        painter.setBrush(theme.ACCENT if self.isChecked() else theme.BORDER_STRONG)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        knob = self.TRACK_H - 4
        x = self.TRACK_W - knob - 2 if self.isChecked() else 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.SURFACE)
        painter.drawEllipse(QRectF(x, top + 2, knob, knob))
        painter.setPen(theme.INK)
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(self.TRACK_W + 8, 0, 0, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
