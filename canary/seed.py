"""Seed data: the exam, 50 translator copies, 5,000 print copies, synthetic people and custody chains.

To build (task 4 in docs/PROMPTS.md). Every person is invented.
"""
import sqlite3


def seed(conn: sqlite3.Connection) -> dict:
    """Fill the database from the bank. Safe to run twice. Returns row counts."""
    raise NotImplementedError("task 4: seed")


def verify_chain(conn: sqlite3.Connection, stage: str, copy_no: int) -> bool:
    """Check one copy's custody chain with canary.chain.link_hash."""
    raise NotImplementedError("task 4: verify_chain")
