"""The local SQLite database: one file, WAL mode, readable only by its owner."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database, creating it and its tables on first use."""
    config.ensure_home()
    path = path or config.db_path()
    if not path.exists():
        os.close(os.open(path, os.O_CREAT | os.O_RDWR, 0o600))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(config.SCHEMA_SQL.read_text())
    return conn
