from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget

from .. import theme
from .text import plain

MAX_IMAGE_SIDE = 12000
IMAGE_FORMATS = {b"jpeg", b"jpg", b"png", b"webp"}


class LeakView(QWidget):
    """The leak itself: its image if it has one, and its text, with exposed questions in highlighter.

    Leaked text is untrusted. It is shown in a plain-text box and never as rich text, and the image is
    decoded only if it is a JPEG, PNG or WebP of a sane size.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QLabel()
        self.image.setTextFormat(Qt.TextFormat.PlainText)
        self.image.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.image.setVisible(False)
        self.note = plain("", 14, role="muted", wrap=True)
        self.note.setVisible(False)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(theme.body(15))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.text.setMinimumHeight(140)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.image)
        layout.addWidget(self.note)
        layout.addWidget(self.text, 1)
        self._pixmap: QPixmap | None = None
        self.highlighted = 0

    def show_leak(self, view) -> None:
        self._pixmap = None
        self.image.setVisible(False)
        self.note.setVisible(False)
        self.highlighted = 0
        if view.image_path:
            self._load_image(view.image_path)
            lines, spans, at = [], [], 0
            for q in view.questions:
                label = f"{q.number}. " if q.number is not None else ""
                line = f"{label}{q.stem}" + ("" if q.legible else "   (hard to read)")
                if q.exposed:
                    spans.append((at, at + len(line)))
                lines.append(line)
                at += len(line) + 2
            body = "\n\n".join(lines) if lines else (view.raw_text or "")
            self.text.setPlainText(body or "No text has been read from this image yet.")
            self._highlight(spans)
        else:
            self.text.setPlainText(view.raw_text or "This leak has no text.")
            text = view.raw_text or ""
            spans = []
            for q in view.questions:
                if q.exposed and q.span:                       # the question itself, not its options
                    start, end = q.span
                    labels = [i for i in (text.find(mark, start, end) for mark in ("\n(A)", "\n(a)", "\nA)", "\nA.", "\n(1)"))
                              if i > start]
                    spans.append((start, min(labels) if labels else end))
            self._highlight(spans)

    def _highlight(self, spans: list[tuple[int, int]]) -> None:
        """Mark exposed questions in highlighter, always with black text."""
        fmt = QTextCharFormat()
        fmt.setBackground(theme.HIGHLIGHTER)
        fmt.setForeground(theme.TIMING)
        length = len(self.text.toPlainText())
        selections = []
        for start, end in spans:
            if not 0 <= start < end <= length:
                continue
            cursor = QTextCursor(self.text.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor, selection.format = cursor, fmt
            selections.append(selection)
        self.text.setExtraSelections(selections)
        self.highlighted = len(selections)
        top = QTextCursor(self.text.document())
        self.text.setTextCursor(top)

    def _load_image(self, path: str) -> None:
        reader = QImageReader(path)
        reader.setDecideFormatFromContent(True)
        reader.setAutoTransform(True)
        size = reader.size()
        ok = (Path(path).is_file() and bytes(reader.format()).lower() in IMAGE_FORMATS and size.isValid()
              and 0 < size.width() <= MAX_IMAGE_SIDE and 0 < size.height() <= MAX_IMAGE_SIDE)
        if ok:
            if max(size.width(), size.height()) > 1600:        # decode at screen size, not at full size
                reader.setScaledSize(size.scaled(QSize(1600, 1600), Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            ok = not image.isNull()
        if not ok:
            self.note.setText("The image is saved, but it cannot be shown here.")
            self.note.setVisible(True)
            return
        self._pixmap = QPixmap.fromImage(image)
        self.image.setVisible(True)
        self._fit()

    def _fit(self) -> None:
        if self._pixmap is not None:
            box = QSize(max(120, self.width()), 240)
            self.image.setPixmap(self._pixmap.scaled(box, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()
