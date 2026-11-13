"""Read-only access to the question bank (canary/data/bank.db).

The bank is built by bank/build_bank.py. Numeric questions come with nine ready-made
value sets: set 0 holds the real values, sets 1 to 8 are decoys.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import config


@dataclass(frozen=True)
class ValueSet:
    set_no: int
    is_real: bool
    params: dict
    stem: str
    answer: str
    distractors: tuple[str, ...]

    @property
    def options(self) -> tuple[str, ...]:
        """Answer first, then the three wrong options. Copies reorder these."""
        return (self.answer, *self.distractors)


@dataclass(frozen=True)
class Question:
    id: str
    position: int | None
    subject: str
    topic: str
    difficulty: str
    kind: str                       # numeric | fixed | trap
    is_reserve: bool
    stem: str
    options: tuple[str, ...] = ()   # fixed and trap only
    correct_index: int | None = None
    pinned_order: bool = False
    value_sets: tuple[ValueSet, ...] = ()   # numeric only

    @property
    def real(self) -> ValueSet:
        return self.value_sets[0]

    @property
    def decoys(self) -> tuple[ValueSet, ...]:
        return self.value_sets[1:]


@dataclass(frozen=True)
class Bank:
    questions: tuple[Question, ...]
    by_id: dict = field(default_factory=dict, compare=False)

    @property
    def paper(self) -> list[Question]:
        """The real exam, in order."""
        return sorted((q for q in self.questions if q.position), key=lambda q: q.position)

    @property
    def traps(self) -> list[Question]:
        return [q for q in self.questions if q.kind == "trap"]

    @property
    def reserves(self) -> list[Question]:
        return [q for q in self.questions if q.is_reserve]


def load_bank(path: Path | None = None) -> Bank:
    path = path or config.BANK_DB
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    sets: dict[str, list[ValueSet]] = {}
    for r in conn.execute("SELECT * FROM value_sets ORDER BY question_id, set_no"):
        sets.setdefault(r["question_id"], []).append(ValueSet(
            r["set_no"], bool(r["is_real"]), json.loads(r["params"]), r["stem"], r["answer"],
            tuple(json.loads(r["distractors"]))))
    questions = tuple(Question(
        id=r["id"], position=r["position"], subject=r["subject"], topic=r["topic"], difficulty=r["difficulty"],
        kind=r["kind"], is_reserve=bool(r["is_reserve"]), stem=r["stem"],
        options=tuple(json.loads(r["options"])) if r["options"] else (),
        correct_index=r["correct_index"], pinned_order=bool(r["pinned_order"]),
        value_sets=tuple(sets.get(r["id"], ())),
    ) for r in conn.execute("SELECT * FROM questions ORDER BY position IS NULL, position, id"))
    conn.close()
    return Bank(questions, {q.id: q for q in questions})
