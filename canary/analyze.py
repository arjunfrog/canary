"""Analysing one leak: read it, match its questions to the bank, collect clues, decide.

To build (task 6 in docs/PROMPTS.md). The worker calls analyze_leak for every queued leak.
"""
import sqlite3


def analyze_leak(conn: sqlite3.Connection, leak: sqlite3.Row) -> None:
    """Write leak_questions and a cases row, and set the leak's final status."""
    raise NotImplementedError("task 6: analysing a leak is not built yet")
