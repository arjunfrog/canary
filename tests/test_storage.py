import stat
import sys

import pytest

from canary import config, db

TABLES = {"exams", "questions", "people", "copies", "custody_events", "watched_chats",
          "leaks", "leak_questions", "cases", "audit_log"}


def test_database_has_every_table(conn):
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert TABLES <= names


@pytest.mark.skipif(sys.platform == "win32", reason="Windows ignores file modes")
def test_home_and_database_are_private(conn, canary_home):
    assert stat.S_IMODE(canary_home.stat().st_mode) == 0o700
    for sub in config.SUBDIRS:
        assert stat.S_IMODE((canary_home / sub).stat().st_mode) == 0o700
    assert stat.S_IMODE(config.db_path().stat().st_mode) == 0o600


def test_database_uses_wal(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_connecting_twice_keeps_data(conn):
    conn.execute("INSERT INTO exams (title, created_at) VALUES ('Mock', ?)", (db.now(),))
    conn.commit()
    again = db.connect()
    assert again.execute("SELECT count(*) FROM exams").fetchone()[0] == 1
    again.close()
