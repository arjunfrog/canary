"""Exam papers as PDF, for translators and for print.

Nothing on a paper shows its copy number or stage. The barcode in the header is a decoy: it encodes
a random number that has nothing to do with the copy. The copy is identified by its questions alone.
"""
import os
import secrets
import sqlite3
from pathlib import Path

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import audit, config
from . import fingerprint as fp
from .bank import load_bank
from .samples import LABELS

PAGE_W, PAGE_H = A4
MARGIN_X, TOP, BOTTOM = 52, 40, 40
HEADER_H = 46
PAGE_ONE_QUESTIONS = 14
BODY, BOLD = "Mukta", "Mukta-SemiBold"
HEADER_TEXT = "Mock exam, synthetic data"
STAGES = ("translation", "print")

# Characters the bundled Mukta font lacks, drawn from the PDF's built-in Symbol font or as raised text.
_SYMBOL = {"Ω": "Ω", "Δ": "Δ", "μ": "μ", "µ": "μ", "→": "→", "⇌": "↔"}
_RAISED = {"⁺": "+", "⁻": "−"}


def _fonts() -> None:
    if BODY not in pdfmetrics.getRegisteredFontNames():
        fonts = config.PACKAGE_DIR / "ui" / "fonts"
        pdfmetrics.registerFont(TTFont(BODY, str(fonts / "Mukta-Regular.ttf")))
        pdfmetrics.registerFont(TTFont(BOLD, str(fonts / "Mukta-SemiBold.ttf")))


def _runs(text: str, font: str, size: float) -> list[tuple[str, float, float, str]]:
    """Split text into (font, size, rise, text) runs so every character is drawn in a font that has it."""
    runs: list[list] = []
    for ch in text:
        if ch in _SYMBOL:
            style, out = ("Symbol", size, 0.0), _SYMBOL[ch]
        elif ch in _RAISED:
            style, out = (font, size * 0.66, size * 0.36), _RAISED[ch]
        else:
            style, out = (font, size, 0.0), ch
        if runs and tuple(runs[-1][:3]) == style:
            runs[-1][3] += out
        else:
            runs.append([*style, out])
    return [tuple(r) for r in runs]


def _width(text: str, font: str, size: float) -> float:
    return sum(pdfmetrics.stringWidth(t, f, s) for f, s, _, t in _runs(text, font, size))


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and _width(trial, font, size) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines or [""]


def _draw(c: canvas.Canvas, x: float, y: float, text: str, font: str, size: float) -> None:
    t = c.beginText(x, y)
    for f, s, rise, piece in _runs(text, font, size):
        t.setFont(f, s)
        t.setRise(rise)
        t.textOut(piece)
    c.drawText(t)


class _Layout:
    """Measures and draws questions at one text size."""

    def __init__(self, size: float):
        self.size, self.leading = size, size * 1.34
        self.width = PAGE_W - 2 * MARGIN_X
        self.number_w = _width("188.  ", BOLD, size)
        self.indent = self.number_w
        self.half = (self.width - self.indent) / 2

    def lines(self, q: fp.Rendered) -> tuple[list[str], list[list[str]], bool]:
        stem = _wrap(q.stem, BODY, self.size, self.width - self.number_w)
        labelled = [f"({LABELS[i]}) {o}" for i, o in enumerate(q.options)]
        paired = all(_width(o, BODY, self.size) <= self.half - 10 for o in labelled)
        if paired:
            return stem, [[o] for o in labelled], True
        return stem, [_wrap(o, BODY, self.size, self.width - self.indent) for o in labelled], False

    def height(self, q: fp.Rendered) -> float:
        stem, options, paired = self.lines(q)
        rows = len(stem) + (2 if paired else sum(len(o) for o in options))
        return rows * self.leading

    def draw(self, c: canvas.Canvas, q: fp.Rendered, top: float) -> None:
        stem, options, paired = self.lines(q)
        y = top - self.size
        _draw(c, MARGIN_X, y, f"{q.number}.", BOLD, self.size)
        for line in stem:
            _draw(c, MARGIN_X + self.number_w, y, line, BODY, self.size)
            y -= self.leading
        if paired:
            for row in (0, 2):
                _draw(c, MARGIN_X + self.indent, y, options[row][0], BODY, self.size)
                _draw(c, MARGIN_X + self.indent + self.half, y, options[row + 1][0], BODY, self.size)
                y -= self.leading
        else:
            for option in options:
                for line in option:
                    _draw(c, MARGIN_X + self.indent, y, line, BODY, self.size)
                    y -= self.leading


def _page_furniture(c: canvas.Canvas, page: int, barcode_value: str) -> None:
    """Header, decoy barcode and page number. Drawn before the questions so they never trail an option in the text."""
    top = PAGE_H - TOP
    _draw(c, MARGIN_X, top - 20, HEADER_TEXT, BOLD, 15)
    _draw(c, MARGIN_X, top - 34, "Each question has one correct option. Mark your answers on the answer sheet.", BODY, 8.5)
    bars = code128.Code128(barcode_value, barHeight=22, barWidth=0.82, humanReadable=False, quiet=False)
    bars.drawOn(c, PAGE_W - MARGIN_X - bars.width, top - 30)
    c.setLineWidth(0.8)
    c.line(MARGIN_X, top - HEADER_H + 4, PAGE_W - MARGIN_X, top - HEADER_H + 4)
    _draw(c, PAGE_W / 2 - 14, BOTTOM - 18, f"Page {page}", BODY, 8.5)


def write_paper(questions: list[fp.Rendered], path: Path) -> Path:
    """Lay out one copy. Page 1 holds exactly the first 14 questions, at the largest size that fits."""
    _fonts()
    barcode_value = str(secrets.randbelow(9 * 10**11) + 10**11)       # random, unrelated to the copy
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        c = canvas.Canvas(handle, pagesize=A4)
        c.setTitle(HEADER_TEXT)
        c.setAuthor("Canary")
        usable_top, usable = PAGE_H - TOP - HEADER_H, PAGE_H - TOP - HEADER_H - BOTTOM
        first, rest = questions[:PAGE_ONE_QUESTIONS], questions[PAGE_ONE_QUESTIONS:]
        min_gap = 5.0

        size = 12.0
        while size > 7.0:
            layout = _Layout(size)
            if sum(layout.height(q) for q in first) + min_gap * (len(first) - 1) <= usable:
                break
            size -= 0.25
        layout = _Layout(size)
        page = 1
        _page_furniture(c, page, barcode_value)
        spare = usable - sum(layout.height(q) for q in first)
        gap = min(spare / max(1, len(first) - 1), layout.leading * 1.2) if len(first) > 1 else 0
        y = usable_top
        for q in first:
            layout.draw(c, q, y)
            y -= layout.height(q) + gap

        layout = _Layout(min(size, 10.5))
        gap = layout.leading * 0.55
        if rest:
            c.showPage()
            page += 1
            _page_furniture(c, page, barcode_value)
            y = usable_top
        for q in rest:
            height = layout.height(q)
            if y - height < BOTTOM:
                c.showPage()
                page += 1
                _page_furniture(c, page, barcode_value)
                y = usable_top
            layout.draw(c, q, y)
            y -= height + gap
        c.save()
    return path


def write_slip(stage: str, copy_no: int, path: Path) -> Path:
    """A one-page slip with only the stage and copy number, to seal in the envelope with the paper."""
    _fonts()
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        c = canvas.Canvas(handle, pagesize=A4)
        c.setTitle("Sealed slip")
        _draw(c, MARGIN_X, PAGE_H - 120, "Sealed slip. Open only to check a result.", BODY, 14)
        _draw(c, MARGIN_X, PAGE_H - 330, "Translator copy" if stage == "translation" else "Printed copy", BOLD, 64)
        _draw(c, MARGIN_X, PAGE_H - 540, f"{copy_no}", BOLD, 190)
        _draw(c, MARGIN_X, 90, HEADER_TEXT, BODY, 12)
        c.save()
    return path


def render(key: bytes, stage: str, copy_no: int, bank=None) -> list[fp.Rendered]:
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}, not {stage!r}")
    limit = config.N_TRANSLATORS if stage == "translation" else config.N_PRINT_COPIES
    if not 1 <= copy_no <= limit:
        raise ValueError(f"{stage} copy numbers run from 1 to {limit}")
    make = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    return make(key, config.EXAM_ID, copy_no, bank or load_bank())


def export_copy(conn: sqlite3.Connection, key: bytes, stage: str, copy_no: int) -> Path:
    """Write one copy's PDF into CANARY_HOME/copies and record it in the audit log."""
    config.ensure_home()
    path = write_paper(render(key, stage, copy_no), config.home() / "copies" / f"{stage}-{copy_no:04d}.pdf")
    audit.record(conn, "copy exported", {"stage": stage, "copy_no": copy_no})
    return path


def print_copies(conn: sqlite3.Connection, key: bytes, translator: list[int], printed: list[int], out: Path) -> list[Path]:
    """Write the chosen copies, plus a sealed slip for each showing its stage and number."""
    if not out.exists():
        out.mkdir(parents=True)
        os.chmod(out, 0o700)                                   # these papers and slips say which copy is which
    written = []
    for stage, numbers in (("translation", translator), ("print", printed)):
        for copy_no in numbers:
            written.append(write_paper(render(key, stage, copy_no), out / f"{stage}-{copy_no:04d}.pdf"))
            written.append(write_slip(stage, copy_no, out / f"{stage}-{copy_no:04d}-slip.pdf"))
            audit.record(conn, "copy exported", {"stage": stage, "copy_no": copy_no, "with_slip": True})
    return written
