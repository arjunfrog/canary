"""The analysis worker: takes queued leaks one at a time and hands each to a handler."""
import asyncio
import sqlite3
from typing import Callable

Handler = Callable[[sqlite3.Connection, sqlite3.Row], None]


def claim_next(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Take the oldest queued leak and mark it as being read."""
    row = conn.execute("SELECT * FROM leaks WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
    if row is None:
        return None
    conn.execute("UPDATE leaks SET status = 'reading' WHERE id = ?", (row["id"],))
    conn.commit()
    return row


def process_next(conn: sqlite3.Connection, handler: Handler) -> bool:
    """Process one leak. Returns False when the queue is empty.

    The handler sets the final status itself. If it raises, the leak is marked failed with the reason.
    """
    leak = claim_next(conn)
    if leak is None:
        return False
    try:
        handler(conn, leak)
    except Exception as exc:                       # one bad leak must not stop the worker
        conn.rollback()
        conn.execute("UPDATE leaks SET status = 'failed', error = ? WHERE id = ?", (str(exc)[:500], leak["id"]))
        conn.commit()
    return True


async def run_worker(conn: sqlite3.Connection, handler: Handler, stop: asyncio.Event, interval: float = 1.0) -> None:
    while not stop.is_set():
        if not process_next(conn, handler):
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
