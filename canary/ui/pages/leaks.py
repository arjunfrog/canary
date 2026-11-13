from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout

from ... import leaks, queries
from .. import theme
from ..widgets import BubbleToggle, RuledSection, RuledTable
from ..widgets.ruled_table import ToneRole
from ..widgets.text import COPY_WORDS, heading, link_button, plain, primary_button, when
from .placeholder import Page

STATUS_WORDS = {"queued": "Waiting to be read", "reading": "Being read", "done": "Read", "unreadable": "Couldn't read it",
                "failed": "Could not be analysed"}


def verdict_words(row) -> tuple[str, str | None]:
    """(words, tone) for a leak's verdict cell."""
    if row.verdict == "traced":
        return f"Traced: {COPY_WORDS.get(row.stage, 'copy').lower()} {row.copy_no}", "traced"
    if row.verdict == "strong_lead":
        return f"Strong lead: {COPY_WORDS.get(row.stage, 'copy').lower()} {row.copy_no}", "lead"
    if row.verdict == "inconclusive":
        return "Not enough to name anyone yet", "muted"
    if row.verdict == "not_our_paper":
        return "Not our paper", "seal"
    if row.status == "unreadable":
        return "We couldn't read this clearly", "muted"
    if row.status == "failed":
        return "No verdict", "seal"
    return "No verdict yet", "muted"


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
        if role == ToneRole:
            if index.column() == 4:
                return verdict_words(row)[1]
            if index.column() == 3 and row.status in ("failed",):
                return "seal"
            if index.column() == 3 and row.status in ("queued", "reading", "unreadable"):
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
        self.resize(720, 560)
        self.text = QPlainTextEdit()
        self.text.setProperty("editable", True)
        self.text.setFont(theme.body(15))
        self.text.setPlaceholderText("Paste the text of the leak here.")
        self.text.setAcceptDrops(False)                      # dropped files go to the dialog, not into the text
        self.choose = link_button("Choose an image")
        self.choose.clicked.connect(self._choose)
        self.image_label = plain("Or drop an image here: a photo or screenshot of the paper.", 15, role="muted")
        self.message = plain("", 15, role="error", wrap=True)
        self.add = primary_button("Add this leak")
        self.add.clicked.connect(self._submit)
        self.cancel = link_button("Cancel")
        self.cancel.clicked.connect(self.reject)
        image_row = QHBoxLayout()
        image_row.setSpacing(16)
        image_row.addWidget(self.choose)
        image_row.addWidget(self.image_label, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(20)
        buttons.addWidget(self.add)
        buttons.addWidget(self.cancel)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)
        layout.addWidget(heading("Add a leak", 34))
        layout.addWidget(plain("Typed leaks are read on this laptop, with no network. Images go to the photo reader.", 15,
                               role="muted", wrap=True))
        layout.addWidget(self.text, 1)
        layout.addLayout(image_row)
        layout.addWidget(self.message)
        layout.addLayout(buttons)

    def set_image(self, path: str) -> None:
        self.image_path = path
        self.image_label.setText(f"Image chosen: {Path(path).name}")
        self.message.setText("")

    def _choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose an image of the leak", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if path:
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
        text = self.text.toPlainText()
        if self.image_path and text.strip():
            self.message.setText("Add the text or the image, not both. Clear one of them.")
            return
        if not self.image_path and not text.strip():
            self.message.setText("Paste some text or choose an image first.")
            return
        try:
            self.leak_id = leaks.add_manual_leak(self.conn, text=None if self.image_path else text,
                                                 image_path=self.image_path)
        except leaks.LeakRefused as exc:
            self.message.setText(str(exc))
            return
        self.accept()


class LeaksPage(Page):
    """Every leak seen so far, newest first. It updates by itself when the background thread reports a change."""

    def __init__(self, window=None):
        super().__init__(window)
        self._dialog: AddLeakDialog | None = None
        section = RuledSection("Leaks")
        self.follow_toggle = BubbleToggle("Follow new leaks")
        self.follow_toggle.setToolTip("Open each new case by itself and play its funnel")
        self.add_button = primary_button("Add a leak")
        self.add_button.clicked.connect(self.open_add_dialog)
        self.summary = plain("", 15, role="muted")
        bar = QHBoxLayout()
        bar.setSpacing(24)
        bar.addWidget(self.add_button)
        bar.addWidget(self.follow_toggle)
        bar.addStretch(1)
        bar.addWidget(self.summary)
        self.message = plain("", 18, role="muted", wrap=True)
        self.table = RuledTable()
        self.model = LeaksModel(self)
        self.table.setModel(self.model)
        for column, width in enumerate((190, 250, 250, 190)):
            self.table.setColumnWidth(column, width)
        self.table.activated.connect(self._open_index)
        self.table.clicked.connect(self._open_index)
        section.body.addLayout(bar)
        section.body.addSpacing(10)
        section.body.addWidget(self.message)
        section.body.addWidget(self.table, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section, 1)
        self.show_loading()

    @property
    def follow(self) -> bool:
        return self.follow_toggle.isChecked()

    def marks(self) -> list[bool]:
        """One mark per leak on the list, black once it has been read."""
        rows = self.model.rows[:26]
        return [r.status in ("done", "unreadable") for r in rows] or [False] * 14

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
        self.summary.setText(f"{len(rows)} leak{'s' if len(rows) != 1 else ''}" + (f", {waiting} waiting to be read" if waiting else ""))
        if self.app_window is not None and self.app_window.stack.currentWidget() is self:
            self.app_window.marks.set_states(self.marks())

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
