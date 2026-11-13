"""The audit log: every operator action, chained so an edit to any row shows."""
import json
import sqlite3

from .chain import GENESIS, link_hash
from .db import now


def record(conn: sqlite3.Connection, action: str, detail: dict | None = None) -> str:
    """Append one action and return its hash.

    The last hash is read and the new row written inside one write transaction. The window, the
    background thread and the command line each have their own connection, and without this two of
    them could chain onto the same row and make the log look tampered with.
    """
    if conn.in_transaction:
        conn.commit()
    at, detail = now(), detail or {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        last = conn.execute("SELECT event_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev = last["event_hash"] if last else GENESIS
        event_hash = link_hash(prev, {"at": at, "action": action, "detail": detail})
        conn.execute("INSERT INTO audit_log (at, action, detail, prev_hash, event_hash) VALUES (?, ?, ?, ?, ?)",
                     (at, action, json.dumps(detail, sort_keys=True), prev, event_hash))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return event_hash


def head(conn: sqlite3.Connection) -> tuple[int, str]:
    """(number of rows, hash of the newest row). Written down somewhere else, this shows if the end is ever cut off."""
    row = conn.execute("SELECT count(*) AS n, (SELECT event_hash FROM audit_log ORDER BY id DESC LIMIT 1) AS h FROM audit_log").fetchone()
    return row["n"], row["h"] or GENESIS


def verify(conn: sqlite3.Connection) -> tuple[bool, int | None]:
    """Recompute the whole chain. Returns (True, None), or (False, id of the first bad row)."""
    prev = GENESIS
    for row in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        body = {"at": row["at"], "action": row["action"], "detail": json.loads(row["detail"])}
        if row["prev_hash"] != prev or row["event_hash"] != link_hash(prev, body):
            return False, row["id"]
        prev = row["event_hash"]
    return True, None
