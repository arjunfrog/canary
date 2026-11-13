"""The health check, reset and replay export.

To build (task 13 in docs/PROMPTS.md).
"""
import sqlite3


def check(conn: sqlite3.Connection, vault) -> bool:
    """Run known leaks end to end and print PASS or FAIL."""
    raise NotImplementedError("task 13: check")


def reset(conn: sqlite3.Connection) -> None:
    """Delete leaks, cases and evidence files. Keep the exam, copies and audit log."""
    raise NotImplementedError("task 13: reset")


def export_case(conn: sqlite3.Connection, case_id: int) -> None:
    raise NotImplementedError("task 13: export_case")
