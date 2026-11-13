from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from .ruled_table import BubbleRole, RuledTable, ToneRole

KIND_WORDS = {"value": "Values", "trap": "Trap question", "order": "Option order"}


class ClueModel(QAbstractTableModel):
    HEADERS = ("Question", "Clue", "Result")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list = []
        self._named = False

    def set_clues(self, clues: list, named: bool) -> None:
        self.beginResetModel()
        self._rows, self._named = [c for c in clues if c.kind], named
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def result(self, clue) -> tuple[str, bool | None, str | None]:
        """(words, bubble, tone) for one clue."""
        if not clue.read_ok:
            return "Could not be read", None, "muted"
        if clue.kind == "value" and clue.matched is None and self._named:
            return "Real values: shows it was printed", None, "muted"
        if not self._named or clue.matched is None:
            return "Read", None, None
        return ("Matches this copy", True, None) if clue.matched else ("Does not match", False, "muted")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        clue = self._rows[index.row()]
        words, bubble, tone = self.result(clue)
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return f"Question {clue.number}" if clue.number is not None else "Question"
            if index.column() == 1:
                return KIND_WORDS.get(clue.kind, "")
            return words
        if role == BubbleRole and index.column() == 2:
            return bubble
        if role == ToneRole and index.column() == 2:
            return tone
        return None


class ClueTable(RuledTable):
    """Each clue read from the leak: which question, what kind of clue, and whether it matched the named copy."""

    def __init__(self, parent=None):
        super().__init__(parent, row_height=36)
        self._model = ClueModel(self)
        self.setModel(self._model)
        self.setSelectionMode(RuledTable.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setColumnWidth(0, 130)
        self.setColumnWidth(1, 130)

    def set_clues(self, clues: list, named: bool) -> None:
        self._model.set_clues(clues, named)
        rows = self._model.rowCount()
        self.setFixedHeight(min(rows, 9) * 36 + 38 if rows else 38)

    def row_count(self) -> int:
        return self._model.rowCount()
