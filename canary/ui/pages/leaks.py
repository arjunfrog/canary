from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from ... import leaks, queries
from .. import theme
from ..widgets import Panel, RuledTable, Switch, divider
from ..widgets.ruled_table import PillRole, ToneRole
from ..widgets.text import COPY_WORDS, button, caption, heading, plain, primary_button, when
from .placeholder import Page, PageHeader

STATUS_WORDS = {"queued": "Waiting to be read", "reading": "Being read", "done": "Read", "unreadable": "Couldn't read it",
                "failed": "Could not be analysed"}


def verdict_words(row) -> tuple[str, str]:
    """(words, tone) for a leak's verdict cell. The tone names one of theme.TONES."""
    if row.verdict == "traced":
        return f"Traced: {COPY_WORDS.get(row.stage, 'copy').lower()} {row.copy_no}", "traced"
    if row.verdict == "strong_lead":
        return f"Strong lead: {COPY_WORDS.get(row.stage, 'copy').lower()} {row.copy_no}", "strong_lead"
    if row.verdict == "inconclusive":
        return "Not enough to name anyone yet", "inconclusive"
    if row.verdict == "not_our_paper":
        return "Not our paper", "not_our_paper"
    if row.status == "unreadable":
        return "We couldn't read this clearly", "unreadable"
    if row.status == "failed":
        return "No verdict", "failed"
    return "No verdict yet", "waiting"


class LeaksModel(QAbstractTableModel):
    HEADERS = ("Posted", "Chat", "Sender", "Status", "Verdict")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[queries.LeakRow] = []

    def set_rows(self, rows: list[queries.LeakRow]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (when(row.posted_at or row.received_at), row.chat, row.sender, STATUS_WORDS.get(row.status, row.status),
                    verdict_words(row)[0])[index.column()]
        if role == PillRole and index.column() == 4:
            return verdict_words(row)[1]
        if role == ToneRole:
            if index.column() == 3 and row.status == "failed":
                return "error"
            if index.column() in (0, 3) and row.status != "failed":
                return "muted"
        return None


class AddLeakDialog(QDialog):
    """Paste the text of a leak, or choose or drop one image. Works with no network."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn, self.leak_id = conn, None
        self.image_path: str | None = None
        self.setWindowTitle("Add a leak")
        self.setModal(True)
        self.setAcceptDrops(True)
        self.resize(640, 480)
        self.text = QPlainTextEdit()
        self.text.setProperty("editable", True)
        self.text.setFont(theme.body(14))
        self.text.setPlaceholderText("Paste the text of the leak here.")
        self.text.setAcceptDrops(False)                      # dropped files go to the dialog, not into the text
        self.choose = button("Choose an image")
        self.choose.clicked.connect(self._choose)
        self.image_label = plain("Or drop a photo or screenshot of the paper here.", 13, role="muted")
        self.message = plain("", 13, role="error", wrap=True)
        self.message.setVisible(False)
        self.add = primary_button("Add this leak")
        self.add.clicked.connect(self._submit)
        self.cancel = button("Cancel")
        self.cancel.clicked.connect(self.reject)
        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        image_row.addWidget(self.choose)
        image_row.addWidget(self.image_label, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.add)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(heading("Add a leak", 18))
        layout.addWidget(plain("Typed leaks and photos are both read on this laptop. Nothing is sent anywhere.", 13,
                               role="muted", wrap=True))
        layout.addWidget(self.text, 1)
        layout.addLayout(image_row)
        layout.addWidget(self.message)
        layout.addLayout(buttons)

    def _say(self, text: str) -> None:
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def set_image(self, path: str) -> None:
        self.image_path = path
        self.image_label.setText(f"Image chosen: {Path(path).name}")
        self._say("")

    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose an image of the leak", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if path and not self.isHidden():                       # the window may have locked while the dialog was open
            self.set_image(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        local = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if local:
            self.set_image(local[0])
            event.acceptProposedAction()

    def _submit(self) -> None:
        if self.isHidden() and self.parent() is not None and getattr(self.parent().app_window, "locked", False):
            return
        text = self.text.toPlainText()
        if self.image_path and text.strip():
            self._say("Add the text or the image, not both. Clear one of them.")
            return
        if not self.image_path and not text.strip():
            self._say("Paste some text or choose an image first.")
            return
        try:
            self.leak_id = leaks.add_manual_leak(self.conn, text=None if self.image_path else text,
                                                 image_path=self.image_path)
        except leaks.LeakRefused as exc:
            self._say(str(exc))
            return
        self.accept()


class Figure(QWidget):
    """One key figure in a strip: a small label over a number."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = caption(label)
        self.value = plain("0", 20, weight=QFont.Weight.DemiBold)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 9)
        layout.setSpacing(0)
        layout.addWidget(self.label)
        layout.addWidget(self.value)


class LeaksPage(Page):
    """Every leak seen so far, newest first. It updates by itself when the background thread reports a change."""

    def __init__(self, window=None):
        super().__init__(window)
        self._dialog: AddLeakDialog | None = None
        self.header = PageHeader("Leaks", "Every paper posted in a watched chat or added by hand, newest first.")
        self.follow_toggle = Switch("Follow new leaks")
        self.follow_toggle.setToolTip("Open each new case by itself and play its funnel")
        self.add_button = primary_button("Add a leak")
        self.add_button.clicked.connect(self.open_add_dialog)
        self.header.actions.addWidget(self.follow_toggle)
        self.header.actions.addSpacing(6)
        self.header.actions.addWidget(self.add_button)

        self.figures_panel = Panel()
        strip = QHBoxLayout()
        strip.setContentsMargins(0, 0, 0, 0)
        strip.setSpacing(0)
        self.figures = {key: Figure(label) for key, label in (("total", "Leaks"), ("traced", "Traced"),
                                                              ("lead", "Strong leads"), ("fake", "Not our paper"),
                                                              ("waiting", "Waiting to be read"))}
        for i, figure in enumerate(self.figures.values()):
            if i:
                strip.addWidget(divider(vertical=True))
            strip.addWidget(figure, 1)
        self.figures_panel.body.setContentsMargins(0, 0, 0, 0)
        self.figures_panel.body.addLayout(strip)

        self.table_panel = Panel("All leaks", flush=True)
        self.summary = plain("", 12, role="muted")
        self.table_panel.actions.addWidget(self.summary)
        self.message = plain("", 14, role="muted", wrap=True)
        self.message.setContentsMargins(12, 14, 12, 14)
        self.table = RuledTable()
        self.model = LeaksModel(self)
        self.table.setModel(self.model)
        for column, width in enumerate((156, 230, 250, 170)):
            self.table.setColumnWidth(column, width)
        self.table.activated.connect(self._open_index)
        self.table.clicked.connect(self._open_index)
        self.table_panel.body.addWidget(self.message)
        self.table_panel.body.addWidget(self.table, 1)

        layout = self.frame(self)
        layout.addWidget(self.header)
        layout.addWidget(self.figures_panel)
        layout.addWidget(self.table_panel, 1)
        self.show_loading()

    @property
    def follow(self) -> bool:
        return self.follow_toggle.isChecked()

    def on_lock(self) -> None:
        if self._dialog is not None:
            self._dialog.reject()
            self._dialog = None

    def show_loading(self) -> None:
        self.message.setText("Loading the leaks.")
        self.message.setVisible(True)
        self.table.setVisible(False)

    def refresh(self) -> None:
        try:
            rows = queries.list_leaks(self.conn)
        except Exception as exc:                              # the list could not be read: say so in plain words
            self.model.set_rows([])
            self.message.setProperty("role", "error")
            self.message.style().unpolish(self.message)
            self.message.style().polish(self.message)
            self.message.setText(f"The list of leaks could not be read from this laptop's database. ({type(exc).__name__})")
            self.message.setVisible(True)
            self.table.setVisible(False)
            self.summary.setText("")
            return
        self.model.set_rows(rows)
        self.table.setVisible(bool(rows))
        self.message.setVisible(not rows)
        if not rows:
            self.message.setText("No leaks yet. When a watched chat posts a paper it appears here. "
                                 "You can also add one by hand with \"Add a leak\".")
        waiting = sum(1 for r in rows if r.status in ("queued", "reading"))
        counts = {"total": len(rows), "traced": sum(r.verdict == "traced" for r in rows),
                  "lead": sum(r.verdict == "strong_lead" for r in rows), "fake": sum(r.verdict == "not_our_paper" for r in rows),
                  "waiting": waiting}
        for key, figure in self.figures.items():
            figure.value.setText(f"{counts[key]:,}")
        self.summary.setText(f"{len(rows)} leak{'s' if len(rows) != 1 else ''}" + (f", {waiting} waiting to be read" if waiting else ""))

    def _open_index(self, index) -> None:
        if index.isValid():
            self.open_row(index.row())

    def open_row(self, row: int) -> None:
        leak = self.model.rows[row]
        if leak.case_id is not None:
            self.app_window.open_case(leak.case_id)
        else:
            self.app_window.open_leak(leak.id)

    def open_add_dialog(self) -> AddLeakDialog:
        self._dialog = AddLeakDialog(self.conn, self)
        self._dialog.finished.connect(lambda _code: self.refresh())
        self._dialog.open()
        return self._dialog
