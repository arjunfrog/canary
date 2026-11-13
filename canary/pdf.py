"""Exam papers as PDF, for translators and for print.

To build (task 3 in docs/PROMPTS.md), with ReportLab.
"""
from pathlib import Path


def export_copy(stage: str, copy_no: int) -> Path:
    """Write one copy's PDF into CANARY_HOME/copies and record it in the audit log."""
    raise NotImplementedError("task 3: export_copy")


def print_copies(translator: list[int], printed: list[int], out: Path) -> list[Path]:
    """Write the chosen copies, plus a sealed slip for each showing its stage and number."""
    raise NotImplementedError("task 3: print_copies")
