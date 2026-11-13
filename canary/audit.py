"""The audit log: every operator action, chained so an edit to any row shows."""
import json
import sqlite3

from .chain import GENESIS, link_hash
from .db import now


def record(conn: sqlite3.Connection, action: str, detail: dict | None = None) -> str:
    """Append one action and return its hash."""
    last = conn.execute("SELECT event_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev = last["event_hash"] if last else GENESIS
    at, detail = now(), detail or {}
    event_hash = link_hash(prev, {"at": at, "action": action, "detail": detail})
    conn.execute("INSERT INTO audit_log (at, action, detail, prev_hash, event_hash) VALUES (?, ?, ?, ?, ?)",
                 (at, action, json.dumps(detail, sort_keys=True), prev, event_hash))
    conn.commit()
    return event_hash


def verify(conn: sqlite3.Connection) -> tuple[bool, int | None]:
    """Recompute the whole chain. Returns (True, None), or (False, id of the first bad row)."""
    prev = GENESIS
    for row in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        body = {"at": row["at"], "action": row["action"], "detail": json.loads(row["detail"])}
        if row["prev_hash"] != prev or row["event_hash"] != link_hash(prev, body):
            return False, row["id"]
        prev = row["event_hash"]
    return True, None
