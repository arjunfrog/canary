"""The signed evidence file for a traced or strong-lead case, and the recommended response.

To build (task 11 in docs/PROMPTS.md). Signed with the vault's Ed25519 key.
"""
import sqlite3
from pathlib import Path


def build_evidence(conn: sqlite3.Connection, vault, case_id: int) -> Path:
    raise NotImplementedError("task 11: build_evidence")


def verify_file(manifest: Path) -> list[tuple[str, bool]]:
    """Check signature, hashes and custody chain. Needs no passphrase."""
    raise NotImplementedError("task 11: verify_file")


def response_for(conn: sqlite3.Connection, case_id: int) -> dict:
    """Exposed questions, suggested reserves, and a recommendation for a person to decide."""
    raise NotImplementedError("task 11: response_for")
