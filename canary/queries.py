"""The one place the app reads the database from. Every function returns plain dataclasses, never raw rows.

Text that came from a leak or from Telegram (chat titles, sender names, message text, read questions)
is passed through as plain strings. Screens must show it as plain text only.
"""
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config, seed
from .bank import load_bank

CLUE_WORDS = {"value": "Values", "trap": "Trap question", "order": "Option order"}


@dataclass
class LeakRow:
    id: int
    source: str                    # telegram | manual
    chat: str                      # chat title, or "Added by hand"
    sender: str
    posted_at: str | None
    received_at: str
    status: str                    # queued | reading | done | unreadable | failed
    verdict: str | None
    case_id: int | None
    stage: str | None = None
    copy_no: int | None = None
    error: str | None = None
    has_image: bool = False


@dataclass
class ClueRow:
    number: int | None             # the question's number in the leak
    question_id: str | None        # bank id, None if the question matched nothing
    position: int | None           # its place on the real paper, None for traps
    kind: str | None               # value | trap | order
    read_ok: bool
    matched: bool | None           # did it match the named copy. None when no copy is named
    score: float = 0.0


@dataclass
class ReadQuestion:
    number: int | None
    stem: str
    span: list[int] | None         # where it sits in the leak's text
    exposed: bool                  # a real question from the paper (never a trap)
    question_id: str | None = None
    legible: bool = True


@dataclass
class CustodyEvent:
    at: str
    note: str
    to_name: str | None
    to_role: str | None
    to_organisation: str | None
    from_name: str | None
    prev_hash: str
    event_hash: str
    ok: bool
    in_force: bool = False         # the handover in force when the leak was posted


@dataclass
class CaseView:
    """Everything the Case screen shows for one leak. Also the shape of a replay file."""
    leak_id: int
    case_id: int | None
    status: str
    verdict: str | None
    source: str
    chat: str
    chat_username: str | None
    sender: str
    posted_at: str | None
    message_url: str | None
    raw_text: str | None
    image_path: str | None
    image_sha256: str | None
    error: str | None = None
    stage: str | None = None
    copy_no: int | None = None
    holder_name: str | None = None
    holder_role: str | None = None
    holder_organisation: str | None = None
    clues_read: int = 0
    clues_matched: int = 0
    expected_false_matches: float | None = None
    candidates: int = 0
    steps: list[dict] = field(default_factory=list)
    reader: str | None = None
    elapsed_ms: int | None = None
    created_at: str | None = None
    clues: list[ClueRow] = field(default_factory=list)
    questions: list[ReadQuestion] = field(default_factory=list)
    custody: list[CustodyEvent] = field(default_factory=list)
    custody_ok: bool | None = None
    response: dict | None = None
    evidence_path: str | None = None
    replay_label: str | None = None
    is_synthetic: bool = True

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "CaseView":
        data = dict(data)
        data["clues"] = [ClueRow(**c) for c in data.get("clues", [])]
        data["questions"] = [ReadQuestion(**q) for q in data.get("questions", [])]
        data["custody"] = [CustodyEvent(**e) for e in data.get("custody", [])]
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def holder_at_leak(self) -> CustodyEvent | None:
        return next((e for e in self.custody if e.in_force), None)

    @property
    def exposed(self) -> list[ReadQuestion]:
        return [q for q in self.questions if q.exposed]


@dataclass
class Status:
    watched: list[tuple[str, str]]          # (username, title)
    counts: dict[str, int]                  # leaks by status
    total: int = 0
    seeded: bool = False


def _sender(row) -> str:
    if row["source"] == "manual":
        return "Added by hand"
    name, username = row["sender_name"], row["sender_username"]
    if name and username:
        return f"{name} (@{username})"
    return name or (f"@{username}" if username else "Not shown")


def _chat(row) -> str:
    if row["source"] == "manual":
        return "Added by hand"
    return row["chat_title"] or (f"@{row['chat_username']}" if row["chat_username"] else "Unknown chat")


def list_leaks(conn: sqlite3.Connection, limit: int = 200) -> list[LeakRow]:
    """The newest leaks first: chat, sender, time posted, status and verdict."""
    rows = conn.execute(
        """SELECT l.*, c.id AS case_id, c.verdict, c.stage, p.copy_no
           FROM leaks l LEFT JOIN cases c ON c.leak_id = l.id LEFT JOIN copies p ON p.id = c.copy_id
           ORDER BY l.id DESC LIMIT ?""", (limit,)).fetchall()
    return [LeakRow(r["id"], r["source"], _chat(r), _sender(r), r["posted_at"], r["received_at"], r["status"],
                    r["verdict"], r["case_id"], r["stage"], r["copy_no"], r["error"], bool(r["image_path"]))
            for r in rows]


def _parse_time(text: str | None) -> datetime | None:
    try:
        when = datetime.fromisoformat(text) if text else None
    except ValueError:
        return None
    return when if when is None or when.tzinfo else when.replace(tzinfo=timezone.utc)


def _custody(conn: sqlite3.Connection, copy_id: int, posted_at: str | None) -> tuple[list[CustodyEvent], bool]:
    events, ok = seed.custody_chain(conn, copy_id)
    out = [CustodyEvent(e["at"], e["note"] or "", e["to_name"], e["to_role"], e["to_organisation"], e["from_name"],
                        e["prev_hash"], e["event_hash"], e["ok"]) for e in events]
    posted = _parse_time(posted_at)
    if posted is not None:
        earlier = [e for e in out if (_parse_time(e.at) or posted) <= posted]
        if earlier:
            earlier[-1].in_force = True
    return out, ok


def _view(conn: sqlite3.Connection, leak: sqlite3.Row, case: sqlite3.Row | None) -> CaseView:
    view = CaseView(
        leak_id=leak["id"], case_id=case["id"] if case else None, status=leak["status"],
        verdict=case["verdict"] if case else None, source=leak["source"], chat=_chat(leak),
        chat_username=leak["chat_username"], sender=_sender(leak), posted_at=leak["posted_at"],
        message_url=leak["message_url"], raw_text=leak["raw_text"], image_path=leak["image_path"],
        image_sha256=leak["image_sha256"], error=leak["error"])
    exam = conn.execute("SELECT is_synthetic FROM exams WHERE id = ?", (config.EXAM_ID,)).fetchone()
    view.is_synthetic = bool(exam["is_synthetic"]) if exam else True
    bank = load_bank()
    seen: dict = {}
    for r in conn.execute("SELECT * FROM leak_questions WHERE leak_id = ? ORDER BY id", (leak["id"],)):
        detail = json.loads(r["clue"] or "{}")
        bank_id = detail.get("bank_id")
        question = bank.by_id.get(bank_id) if bank_id else None
        key = (detail.get("number"), detail.get("stem"))
        if key not in seen:
            seen[key] = True
            view.questions.append(ReadQuestion(detail.get("number"), detail.get("stem") or "", detail.get("span"),
                                               bool(question and question.kind != "trap"), bank_id,
                                               bool(detail.get("legible", True))))
        if r["clue_type"] or question:
            view.clues.append(ClueRow(detail.get("number"), bank_id, question.position if question else None,
                                      r["clue_type"], bool(r["read_ok"]), detail.get("matched"), r["match_score"] or 0.0))
    if case:
        stored = json.loads(case["steps"] or "{}")
        view.stage, view.clues_read, view.clues_matched = case["stage"], case["clues_read"], case["clues_matched"]
        view.expected_false_matches, view.reader = case["expected_false_matches"], case["reader"]
        view.elapsed_ms, view.created_at = case["elapsed_ms"], case["created_at"]
        view.steps, view.candidates = stored.get("steps", []), stored.get("candidates", 0)
        if case["copy_id"] is not None:
            copy = conn.execute(
                """SELECT c.copy_no, p.display_name, p.role, p.organisation FROM copies c
                   LEFT JOIN people p ON p.id = c.holder_id WHERE c.id = ?""", (case["copy_id"],)).fetchone()
            view.copy_no, view.holder_name = copy["copy_no"], copy["display_name"]
            view.holder_role, view.holder_organisation = copy["role"], copy["organisation"]
            view.custody, view.custody_ok = _custody(conn, case["copy_id"], leak["posted_at"])
        elif stored.get("copy_no") is not None:
            view.copy_no = stored["copy_no"]                     # named, but the copies table is not seeded
    return view


def get_case(conn: sqlite3.Connection, case_id: int) -> CaseView | None:
    """The case, its leak, its clues, the funnel steps, who held the copy when the leak was posted,
    and the full custody chain with whether it verifies."""
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None:
        return None
    leak = conn.execute("SELECT * FROM leaks WHERE id = ?", (case["leak_id"],)).fetchone()
    return _attach(conn, _view(conn, leak, case))


def get_leak(conn: sqlite3.Connection, leak_id: int) -> CaseView | None:
    """The same view for a leak that may have no case: one that is queued, unreadable or failed."""
    leak = conn.execute("SELECT * FROM leaks WHERE id = ?", (leak_id,)).fetchone()
    if leak is None:
        return None
    case = conn.execute("SELECT * FROM cases WHERE leak_id = ?", (leak_id,)).fetchone()
    return _attach(conn, _view(conn, leak, case))


def _attach(conn: sqlite3.Connection, view: CaseView) -> CaseView:
    """Add the recommended response and any evidence file already issued."""
    from . import evidence
    if view.case_id is not None and view.verdict in ("traced", "strong_lead", "inconclusive"):
        view.response = evidence.response_for(conn, view.case_id)
    path = evidence.manifest_path(view.case_id) if view.case_id is not None else None
    view.evidence_path = str(path) if path is not None and path.exists() else None
    return view


def status(conn: sqlite3.Connection) -> Status:
    """Watched chats and leak counts by status."""
    watched = [(r["username"], r["title"] or r["username"])
               for r in conn.execute("SELECT username, title FROM watched_chats ORDER BY username")]
    counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, count(*) AS n FROM leaks GROUP BY status")}
    seeded = conn.execute("SELECT 1 FROM copies LIMIT 1").fetchone() is not None
    return Status(watched, counts, sum(counts.values()), seeded)
