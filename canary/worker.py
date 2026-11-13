"""The analysis worker: takes queued leaks one at a time and hands each to a handler."""
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import db

Handler = Callable[[sqlite3.Connection, sqlite3.Row], None]


def claim_next(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Take the oldest queued leak and mark it as being read, in one statement so no two workers take the same one."""
    row = conn.execute(
        "UPDATE leaks SET status = 'reading' WHERE status = 'queued' AND id = "
        "(SELECT id FROM leaks WHERE status = 'queued' ORDER BY id LIMIT 1) RETURNING *").fetchone()
    conn.commit()
    return row


def process_one(conn: sqlite3.Connection, handler: Handler) -> int | None:
    """Process one leak and return its id. Returns None when the queue is empty.

    The handler sets the final status itself. If it raises, the leak is marked failed with the reason.
    """
    leak = claim_next(conn)
    if leak is None:
        return None
    try:
        handler(conn, leak)
    except Exception as exc:                       # one bad leak must not stop the worker
        conn.rollback()
        conn.execute("UPDATE leaks SET status = 'failed', error = ? WHERE id = ?", (str(exc)[:500], leak["id"]))
        conn.commit()
    return leak["id"]


def process_next(conn: sqlite3.Connection, handler: Handler) -> bool:
    """Process one leak. Returns False when the queue is empty."""
    return process_one(conn, handler) is not None


def requeue_interrupted(conn: sqlite3.Connection) -> int:
    """Leaks left in "reading" by a run that was stopped part-way go back in the queue."""
    count = conn.execute("UPDATE leaks SET status = 'queued' WHERE status = 'reading'").rowcount
    conn.commit()
    return count


async def run_worker(handler: Handler, stop: asyncio.Event, on_done: Callable[[int], None] | None = None,
                     interval: float = 1.0) -> None:
    """Take queued leaks one at a time until `stop` is set.

    Each leak is processed on one side thread with its own database connection, so a slow photo read
    never holds up the event loop the Telegram listener runs on. `on_done(leak_id)` is called after each.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="canary-worker")
    local: dict = {}

    def step() -> int | None:
        if "conn" not in local:
            local["conn"] = db.connect()
            requeue_interrupted(local["conn"])
        return process_one(local["conn"], handler)

    def close() -> None:
        if "conn" in local:
            local.pop("conn").close()

    loop = asyncio.get_running_loop()
    try:
        while not stop.is_set():
            leak_id = await loop.run_in_executor(executor, step)
            if leak_id is not None:
                if on_done:
                    on_done(leak_id)
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await loop.run_in_executor(executor, close)
        executor.shutdown(wait=True)
