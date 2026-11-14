"""Getting ready for a live demonstration: a clean slate, a few leaks already traced, and a Hindi paper to leak.

`prepare` deletes every leak, case and evidence file, then puts a handful of typed leaks through the real
analysis path, so the Leaks screen opens with verdicts of every kind. It then writes one fresh translator
copy as a Hindi question paper for someone to copy out by hand, photograph and post in a watched channel,
plus the English copy and a sealed slip saying which copy it is.

Everything here is made from the vault's own key, so the leaks and the paper trace exactly as a real one would.
"""
import os
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import analyze, audit, check, config, db
from . import fingerprint as fp
from .bank import load_bank
from .samples import fake_paper_text, leak_text

PAPER_QUESTIONS = 6                 # enough to trace from four or five copied by hand, short enough to copy

# The first-page physics questions in Hindi. Numbers and units stay as they are on the paper, so a copy made
# by hand still carries every value. Option labels stay A to D.
HINDI = {
    "P001": "एक कार विराम से चलना शुरू करती है और {t} s तक {a} m/s² के एकसमान त्वरण से चलती है। "
            "उसके द्वारा तय की गई दूरी है",
    "P002": "एक पत्थर {h} m की ऊँचाई से मुक्त रूप से गिरता है। g = 10 m/s² लेने पर, वह ज़मीन तक पहुँचने में लेता है",
    "P003": "एक गेंद को {u} m/s के वेग से ऊर्ध्वाधर ऊपर फेंका जाता है। g = 10 m/s² लेने पर, "
            "वह जिस अधिकतम ऊँचाई तक पहुँचती है, वह है",
    "P004": "विराम में रखे {m} kg द्रव्यमान के एक पिंड पर {F} N का बल लगता है। {t} s बाद उसकी चाल है",
    "P005": "{m} kg द्रव्यमान का एक पिंड {v} m/s की चाल से चल रहा है। उसकी गतिज ऊर्जा है",
    "P006": "{k} N/m बल नियतांक वाली एक स्प्रिंग को {x} cm खींचा जाता है। उसमें संचित स्थितिज ऊर्जा है",
    "P007": "{f} Hz आवृत्ति की एक तरंग {v} m/s की चाल से चलती है। उसकी तरंगदैर्ध्य है",
    "P008": "{R1} Ω और {R2} Ω के प्रतिरोध समांतर क्रम में जुड़े हैं। उनका तुल्य प्रतिरोध है",
    "P009": "{P} W का एक बिजली का हीटर {V} V पर चलता है। वह जो धारा लेता है, वह है",
    "P010": "{I} A धारा वाला {L} m लंबा एक तार {B} T के चुंबकीय क्षेत्र के लंबवत रखा है। उस पर लगने वाला बल है",
    "P011": "{f} cm फोकस दूरी वाले एक उत्तल लेंस के सामने {u} cm पर एक वस्तु रखी है। प्रतिबिंब की दूरी है",
    "P012": "{E} eV ऊर्जा के फोटॉन वाला प्रकाश {W} eV कार्य फलन वाली धातु पर पड़ता है। "
            "फोटोइलेक्ट्रॉनों की अधिकतम गतिज ऊर्जा है",
    "P013": "{u} m/s से चलती एक कार को {a} m/s² के एकसमान मंदन से रोका जाता है। उसकी रुकने की दूरी है",
    "P014": "{C} μF का एक संधारित्र {V} V तक आवेशित किया जाता है। उसमें संचित ऊर्जा है",
}


@dataclass
class DemoLeak:
    name: str
    stage: str | None               # the stage and copy it was made from; None for the fake paper
    copy_no: int | None
    verdict: str | None = None
    found_copy: int | None = None


def hindi_questions(rendered: list[fp.Rendered], bank=None) -> list[tuple[int, str, tuple[str, ...]]]:
    """(number, Hindi stem, options in this copy's order) for each first-page physics question given.

    The stem carries the same values the copy shows, so a translator's decoy set survives the translation.
    """
    bank = bank or load_bank()
    by_id = {q.id: q for q in bank.paper}
    out = []
    for r in rendered:
        if r.question_id not in HINDI or r.set_no is None:
            raise ValueError(f"No Hindi wording for {r.question_id}.")
        params = by_id[r.question_id].value_sets[r.set_no].params
        out.append((r.number, HINDI[r.question_id].format(**params), r.options))
    return out


def hindi_text(questions: list[tuple[int, str, tuple[str, ...]]]) -> str:
    """The Hindi questions typed out the way a leak would be pasted."""
    return leak_text([(stem, options) for _, stem, options in questions], start=questions[0][0])


def _run(conn: sqlite3.Connection, key: bytes, bank, text: str) -> tuple[str | None, int | None]:
    """Put one typed leak through the real analysis path. Returns (verdict, copy named)."""
    found: list[int] = []
    got = check._run_leak(conn, key, bank, text, found)
    return got["verdict"], got["copy_no"]


def _private_dir(out: Path) -> Path:
    if not out.exists():
        out.mkdir(parents=True)
    os.chmod(out, 0o700)                         # the slip says which copy the paper is
    return out


def prepare(conn: sqlite3.Connection, key: bytes, out: Path, paper_copy: int | None = None) -> dict:
    """Clear the leaks, add the demonstration leaks, and write the Hindi paper. Returns what was made."""
    from . import pdf, seed
    pool = list(range(1, config.N_TRANSLATORS + 1))
    if paper_copy is not None:                   # refused before anything is cleared
        if paper_copy not in pool:
            raise ValueError(f"Translator copies run from 1 to {config.N_TRANSLATORS}.")
        pool.remove(paper_copy)
    bank = load_bank()
    seed.seed(conn)
    cleared = check.reset(conn)

    picked = []
    for _ in range(4):                           # four different translators for the leaks, none the paper's
        picked.append(pool.pop(secrets.randbelow(len(pool))))
    paper_copy = paper_copy or pool[secrets.randbelow(len(pool))]
    printed = 1 + secrets.randbelow(config.N_PRINT_COPIES)
    english, hindi, biology, lead = picked

    def translator(copy_no: int) -> list[fp.Rendered]:
        return fp.render_translator_copy(key, config.EXAM_ID, copy_no, bank)

    bio = [q for q in translator(biology) if q.subject == "biology"]
    first_trap = next((i for i, q in enumerate(bio) if q.is_trap), 0)
    start = max(0, min(first_trap - 3, len(bio) - 12))
    made = [                                     # oldest first, so the newest traced leak sits at the top
        (DemoLeak("Fake paper, questions not from this exam", None, None), fake_paper_text(12)),
        (DemoLeak("Seven physics questions typed without options", "translation", lead),
         leak_text(translator(lead)[:7], options=False)),
        (DemoLeak("Printed copy, first page", "print", printed),
         leak_text(fp.render_print_copy(key, config.EXAM_ID, printed, bank)[:14])),
        (DemoLeak("Biology section from a translator copy", "translation", biology), leak_text(bio[start:start + 12])),
        (DemoLeak("Translator copy, first page", "translation", english), leak_text(translator(english)[:14])),
        (DemoLeak("Translator copy, first page in Hindi", "translation", hindi),
         hindi_text(hindi_questions(translator(hindi)[:PAPER_QUESTIONS], bank))),
    ]
    leaks = []
    for leak, text in made:
        leak.verdict, leak.found_copy = _run(conn, key, bank, text)
        leaks.append(leak)

    folder = _private_dir(out)
    rendered = translator(paper_copy)
    files = [write_hindi_paper(hindi_questions(rendered[:PAPER_QUESTIONS], bank),
                               folder / f"hindi-paper-translator-{paper_copy:02d}.pdf"),
             pdf.write_paper(rendered, folder / f"english-paper-translator-{paper_copy:02d}.pdf"),
             pdf.write_slip("translation", paper_copy, folder / f"sealed-slip-translator-{paper_copy:02d}.pdf")]
    audit.record(conn, "demo prepared", {"cleared": cleared, "leaks": len(leaks), "paper": "translation",
                                         "files": len(files)})
    return {"cleared": cleared, "leaks": leaks, "paper_copy": paper_copy, "files": files}


def write_hindi_paper(questions: list[tuple[int, str, tuple[str, ...]]], path: Path) -> Path:
    """Lay the Hindi questions out on one A4 page, large enough to copy by hand.

    Drawn with Qt, which shapes Devanagari properly, in the bundled Mukta.
    """
    from PySide6.QtCore import QMarginsF, QRectF, Qt
    from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication, QPageLayout, QPageSize, QPainter, QPdfWriter

    from .ui import theme
    if QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        write_hindi_paper._app = QGuiApplication([])          # kept alive for the painter's fonts
    theme.load_fonts()

    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.close(fd)                                              # created private; Qt then writes into it
    writer = QPdfWriter(str(path))
    writer.setResolution(72)                                  # one unit is one point
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                     QMarginsF(0, 0, 0, 0)))
    writer.setTitle("Mock exam, synthetic data")
    writer.setCreator("Canary")
    page_w, page_h, margin = 595.0, 842.0, 48.0
    width = page_w - 2 * margin
    wrap = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap

    def font(px: float, weight=QFont.Weight.Normal) -> QFont:
        f = theme.body(14, weight)
        f.setPixelSize(round(px))
        return f

    def height(painter: QPainter, text: str, f: QFont, w: float) -> float:
        painter.setFont(f)
        return painter.boundingRect(QRectF(0, 0, w, 10_000), wrap, text).height()

    painter = QPainter(writer)
    try:
        ink, muted = theme.INK, theme.INK_2
        y = margin
        painter.setPen(ink)
        painter.setFont(font(22, QFont.Weight.DemiBold))
        painter.drawText(QRectF(margin, y, width, 32), Qt.AlignmentFlag.AlignLeft, "मॉक परीक्षा · भौतिकी")
        painter.setPen(muted)
        painter.setFont(font(12))
        painter.drawText(QRectF(margin, y + 4, width, 20), Qt.AlignmentFlag.AlignRight, "Mock exam, synthetic data")
        y += 34
        painter.setFont(font(14))
        painter.drawText(QRectF(margin, y, width, 22), Qt.AlignmentFlag.AlignLeft,
                         "प्रत्येक प्रश्न का केवल एक विकल्प सही है।")
        y += 28
        painter.setPen(theme.BORDER_STRONG)
        painter.drawLine(int(margin), int(y), int(page_w - margin), int(y))
        y += 18

        foot_h = 60.0
        number_w = 30.0
        for size in (19, 18, 17, 16, 15, 14, 13):               # the largest size at which all of it fits
            stem_f, option_f = font(size), font(size)
            gap = size * 1.1
            total = sum(height(painter, stem, stem_f, width - number_w) + 2 * QFontMetricsF(option_f).lineSpacing() * 1.25
                        for _, stem, _ in questions) + gap * (len(questions) - 1)
            if y + total <= page_h - margin - foot_h:
                break
        line = QFontMetricsF(option_f).lineSpacing() * 1.25
        column = (width - number_w) / 2
        for number, stem, options in questions:
            painter.setPen(ink)
            painter.setFont(font(size, QFont.Weight.DemiBold))
            painter.drawText(QRectF(margin, y, number_w, 40), Qt.AlignmentFlag.AlignLeft, f"{number}.")
            stem_h = height(painter, stem, stem_f, width - number_w)
            painter.setFont(stem_f)
            painter.drawText(QRectF(margin + number_w, y, width - number_w, stem_h + 4), wrap, stem)
            y += stem_h + line * 0.2
            painter.setFont(option_f)
            for row in range(2):
                for col in range(2):
                    slot = row * 2 + col
                    painter.drawText(QRectF(margin + number_w + col * column, y, column, line),
                                     Qt.AlignmentFlag.AlignLeft, f"({'ABCD'[slot]})  {options[slot]}")
                y += line
            y += gap - line * 0.2

        painter.setPen(theme.BORDER_STRONG)
        top = page_h - margin - foot_h + 14
        painter.drawLine(int(margin), int(top), int(page_w - margin), int(top))
        painter.setPen(muted)
        painter.setFont(font(11))
        painter.drawText(QRectF(margin, top + 8, width, foot_h - 14), wrap,
                         "For the demonstration: copy at least four questions by hand, with every number and all four "
                         "options in the same order, then post a photo of the page in the watched Telegram channel.")
    finally:
        painter.end()
    os.chmod(path, 0o600)
    return path
