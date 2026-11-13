"""Analysing one leak: read it, match its questions to the bank, collect clues, decide.

Everything read from a leak is untrusted data. It is parsed, compared with the bank and stored as
plain text. Nothing in it is ever run or followed.
"""
import json
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from rapidfuzz import fuzz, process

from . import config, db
from . import fingerprint as fp
from .bank import load_bank
from .fingerprint import Clue

MATCH_THRESHOLD = 70       # at or above: this is that bank question
CLEARLY_DIFFERENT = 40     # below: not a question from the bank. Between the two: a damaged real question, or unsure
MIN_LEGIBLE = 5
MAX_QUESTIONS = 400        # a leak is never longer than this; anything more is dropped
MAX_TEXT = 400_000

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_QUESTION_START = re.compile(r"^[ \t>*-]*(?:Q(?:uestion|ues)?\.?[ \t]*)?(\d{1,3})[ \t]*[.):\]](?:[ \t]+(?=\S)|(?=[^\d\s]))", re.I | re.M)
# Option label styles, tried in this order: (A)  A)  A.  (1)  1)
_LABEL_STYLES = (
    lambda c, n: rf"\(\s*[{c}{c.lower()}]\s*\)",
    lambda c, n: rf"(?<![\w(])[{c}{c.lower()}]\)",
    lambda c, n: rf"(?<![\w(.])[{c}{c.lower()}]\.(?=\s)",
    lambda c, n: rf"\(\s*{n}\s*\)",
    lambda c, n: rf"(?<![\w(.])\b{n}\)",
)


@dataclass
class ReadQuestion:
    """One question as read from a leak."""
    number: int | None
    stem: str
    options: list[str] = field(default_factory=list)
    legible: bool = True
    stem_en: str | None = None
    options_en: list[str] | None = None
    span: tuple[int, int] | None = None        # where it sits in the leak's text

    @property
    def stem_for_matching(self) -> str:
        return self.stem_en or self.stem

    @property
    def options_for_matching(self) -> list[str]:
        return self.options_en if self.options_en and len(self.options_en) == len(self.options) else self.options


@dataclass
class Finding:
    """What one read question tells us."""
    read: ReadQuestion
    question_id: str | None = None             # the bank question it matched, if any
    score: float = 0.0
    kind: str | None = None                    # numeric | fixed | trap
    set_no: int | None = None                  # numeric: 0 real, 1 to 8 decoy, None if the numbers fit no set
    order: tuple[int, ...] | None = None
    clues: list[Clue] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.question_id is not None


# ---- text handling

def ascii_digits(text: str) -> str:
    """Turn every non-ASCII decimal digit (Devanagari and so on) into its ASCII digit. Length is unchanged."""
    return "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() and unicodedata.category(ch) == "Nd"
                   else ch for ch in text)


def numbers_in(text: str) -> list[str]:
    """Every number in the text, in order, in one canonical form: 1,000 -> 1000, 2.50 -> 2.5, x² -> 2."""
    text = unicodedata.normalize("NFKC", ascii_digits(text))
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    out = []
    for n in _NUMBER.findall(text):
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        n = n.lstrip("0") or "0"
        out.append("0" + n if n.startswith(".") else n)
    return out


def _option_key(option: str) -> tuple:
    """A numeric option as (is it negative, its numbers), so "-200 J" and "200 J" stay apart."""
    return bool(re.match(r"\s*[-\u2212\u2013]\s*\d", option)), tuple(numbers_in(option))


def normalise(text: str, numbers: str = "#") -> str:
    """Lower case, ASCII digits, every number replaced by "#", punctuation dropped.

    With every number replaced, all nine value sets of a question read as the same template.
    """
    text = unicodedata.normalize("NFKC", ascii_digits(text)).lower()
    if numbers is not None:
        text = re.sub(r"\d+(?:[.,]\d+)*", numbers, text)
    return " ".join(re.sub(r"[^\w#]+", " ", text).split())


def parse_text(raw: str) -> list[ReadQuestion]:
    """Split typed or pasted text into questions with their options.

    Questions are found by their numbers ("12." or "Q12)"). If the text has none, each paragraph is one question.
    """
    raw = ascii_digits(raw[:MAX_TEXT])
    starts = [(m.start(), m.end(), int(m.group(1))) for m in _QUESTION_START.finditer(raw)]
    blocks = []
    if len(starts) >= 2 or (starts and not raw[:starts[0][0]].strip()):
        for i, (start, body, number) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
            blocks.append((number, body, end, start))
    else:
        for m in re.finditer(r"\S(?:.*\S)?(?:\n[ \t]*\S.*)*", raw):
            blocks.append((None, m.start(), m.end(), m.start()))
    questions = []
    for number, body, end, start in blocks[:MAX_QUESTIONS]:
        stem, options = _split_options(raw[body:end])
        if not stem.strip() and not options:
            continue
        questions.append(ReadQuestion(number, " ".join(stem.split()), options, span=(start, start + len(raw[start:end].rstrip()))))
    return questions


def _split_options(block: str) -> tuple[str, list[str]]:
    """Find the four option labels in a question's text, whatever style they are written in."""
    best: tuple[str, list[str]] = (block, [])
    for style in _LABEL_STYLES:
        found, pos = [], 0
        for letter, digit in zip("ABCD", "1234"):
            m = re.compile(style(letter, digit)).search(block, pos)
            if not m:
                break
            found.append(m)
            pos = m.end()
        if len(found) > len(best[1]) and len(found) >= 2:
            options = [" ".join(block[m.end():(found[i + 1].start() if i + 1 < len(found) else len(block))].split())
                       for i, m in enumerate(found)]
            best = (block[:found[0].start()], options)
        if len(best[1]) == 4:
            break
    return best


def questions_from_reader(data: dict) -> list[ReadQuestion]:
    """Turn the photo reader's validated output into read questions."""
    out = []
    for q in data.get("questions", [])[:MAX_QUESTIONS]:
        out.append(ReadQuestion(q.get("number"), ascii_digits(q.get("stem") or ""), [ascii_digits(o) for o in q.get("options") or []],
                                bool(q.get("legible", True)), ascii_digits(q["stem_en"]) if q.get("stem_en") else None,
                                [ascii_digits(o) for o in q["options_en"]] if q.get("options_en") else None))
    return out


# ---- matching against the bank

class Matcher:
    """Finds which bank question a read question is, and what it shows about the copy."""

    def __init__(self, bank):
        self.bank = bank
        self.pool = bank.paper + bank.traps                 # reserves are never handed out, so never in a leak
        self.templates, self.owner = [], []
        for q in self.pool:
            stems = {normalise(v.stem) for v in q.value_sets} if q.kind == "numeric" else {normalise(q.stem)}
            for template in sorted(stems):
                self.templates.append(template)
                self.owner.append(q)
        self.set_numbers = {q.id: [numbers_in(v.stem) for v in q.value_sets] for q in self.pool if q.kind == "numeric"}
        # Each value set's numbers, as a signature that does not depend on the wording: the numbers in the stem
        # (in any order) plus the four options. A signature shared by two questions identifies neither.
        self.signatures: dict = {}
        for q in self.pool:
            if q.kind != "numeric":
                continue
            for set_no, value_set in enumerate(q.value_sets):
                options = tuple(sorted(_option_key(o) for o in value_set.options))
                if not all(k[1] for k in options):
                    continue
                signature = (tuple(sorted(numbers_in(value_set.stem))), options)
                self.signatures[signature] = None if signature in self.signatures else (q, set_no)
        # Letter triples seen in the bank's own words. Words the bank has never seen are still mostly built
        # from these, while the debris of a ruined scan is not.
        self.triples = frozenset(t for q in bank.questions for text in (q.stem, *q.options)
                                 for w in _words(text) for t in _triples(w)) | frozenset(
            t for w in _COMMON for t in _triples(w))
        vocabulary = set(_COMMON)
        for q in bank.questions:
            for text in (q.stem, *q.options, *(o for v in q.value_sets for o in v.options)):
                vocabulary.update(_words(text))
        self.vocabulary = frozenset(vocabulary)
        # In how many bank stems each word appears. A word in one or two stems is what that question is about.
        self.stem_count: dict = {}
        for q in self.pool:
            for word in set(_words(q.value_sets[0].stem if q.kind == "numeric" else q.stem)):
                self.stem_count[word] = self.stem_count.get(word, 0) + 1

    def different_subject(self, question, read: ReadQuestion) -> bool:
        """Same sentence, different subject: "Quinine is obtained from" beside the bank's "Morphine is obtained from".

        True when a word the bank question is about has been swapped for an unrelated one. Everyday words
        swapped in a retelling (called/known, find/determine) do not count, and neither does a typing slip.
        Never true when the numbers fit one of the question's value sets, or its options are this question's.
        """
        if question.kind == "numeric":
            if self.value_set(question, read) is not None:
                return False
        elif len(read.options_for_matching) == 4 and not self.options_clearly_differ(question, read):
            return False
        ours = normalise(question.value_sets[0].stem if question.kind == "numeric" else question.stem).split()
        theirs = normalise(read.stem_for_matching).split()
        for tag, a0, a1, b0, b1 in SequenceMatcher(None, ours, theirs, autojunk=False).get_opcodes():
            if tag != "replace":
                continue
            for mine in ours[a0:a1]:
                if len(mine) < 4 or mine in _COMMON:
                    continue
                for other in theirs[b0:b1]:
                    if len(other) < 4 or other in _COMMON or fuzz.ratio(mine, other) >= 60:
                        continue
                    if self.stem_count.get(mine, 0) <= 2 or other in self.vocabulary:
                        return True
        return False

    def reads_like_words(self, text: str) -> bool:
        """Is this made of word-like strings in Latin letters? False for a ruined scan or an unreadable script.

        Judged by letter triples, not by a word list, so ordinary words the bank never uses still pass.
        """
        triples = [t for w in _words(text) for t in _triples(w)]
        if len(triples) < 8:
            return False
        return sum(t in self.triples for t in triples) >= 0.6 * len(triples)

    def cleanly_written(self, text: str) -> bool:
        """Is this ordinary, undamaged writing? Most of its words are real words, and it has no stray symbols.

        A bad scan turns words into strings that are in no vocabulary, so damaged text fails this.
        """
        words = _words(text)
        if len(words) < 3 or re.search(r"[#@~|]", text):
            return False
        return sum(w in self.vocabulary for w in words) >= 0.6 * len(words)

    def options_clearly_differ(self, question, read: ReadQuestion) -> bool:
        """The leak shows four options, and they are plainly not this bank question's options.

        For a numeric question: the numbers fit none of its nine value sets. For any other: fewer than three
        of the four options resemble any option of the bank question.
        """
        shown = read.options_for_matching
        if len(shown) != 4:
            return False
        if question.kind == "numeric":
            seen = sorted(_option_key(o) for o in shown)
            if not all(k[1] for k in seen):
                return False                                   # numbers missing or unreadable: no evidence either way
            return all(sorted(_option_key(o) for o in v.options) != seen for v in question.value_sets)
        want = [normalise(o, numbers=None) for o in question.options]
        alike = sum(1 for o in shown if max(fuzz.ratio(normalise(o, numbers=None), w) for w in want) >= 70)
        return alike < 3

    def best(self, stem: str):
        """(bank question, score from 0 to 100) for the closest stem. Unrelated text scores under 40."""
        query = normalise(stem)
        if not query:
            return None, 0.0
        _, raw, index = process.extractOne(query, self.templates, scorer=fuzz.ratio)
        return self.owner[index], max(0.0, (raw - 50.0) * 2.0)

    def by_numbers(self, read: ReadQuestion):
        """(bank question, set number) if the numbers alone identify this question, else None.

        The numbers in the stem and all four options must equal exactly one value set of exactly one question.
        This is how a paper typed in a language nothing here can read is still recognised: its numbers are
        printed as they were.
        """
        if len(read.options) != 4:
            return None
        options = tuple(sorted(_option_key(o) for o in read.options))
        if not all(k[1] for k in options):
            return None
        for stem in (read.stem, read.stem_en):
            if stem:
                found = self.signatures.get((tuple(sorted(numbers_in(stem))), options))
                if found:
                    return found
        return None

    def find(self, read: ReadQuestion) -> Finding:
        question, score = self.best(read.stem_for_matching)
        if (question is not None and CLEARLY_DIFFERENT <= score < MATCH_THRESHOLD
                and self.cleanly_written(read.stem_for_matching) and self.options_clearly_differ(question, read)):
            # Wording that resembles a bank stem, cleanly written, with someone else's options: a different
            # question on the same subject, not a damaged copy of ours.
            score = CLEARLY_DIFFERENT - 1.0
        if (question is not None and score >= CLEARLY_DIFFERENT and self.reads_like_words(read.stem_for_matching)
                and self.different_subject(question, read)):
            score = CLEARLY_DIFFERENT - 1.0                    # the same sentence about something else
        known_set = None
        if question is None or score < MATCH_THRESHOLD:
            numbered = self.by_numbers(read)
            if numbered is not None:                           # the words did not match, but the numbers do
                question, known_set = numbered
                score = max(score, 90.0)
        finding = Finding(read, score=round(score, 1))
        if question is None or score < MATCH_THRESHOLD:
            return finding
        finding.question_id, finding.kind = question.id, question.kind
        if question.kind == "trap":
            finding.clues.append(Clue(question.id, "trap"))
        if question.kind == "numeric":
            finding.set_no = known_set if known_set is not None else self.value_set(question, read)
            if finding.set_no is not None:
                finding.clues.append(Clue(question.id, "value", finding.set_no))
        if question.kind != "numeric" or finding.set_no is not None:
            finding.order = self.option_order(question, finding.set_no, read.options_for_matching)
            if finding.order is not None and fp.order_chance(question) is not None:
                finding.clues.append(Clue(question.id, "order", finding.order))
        return finding

    def value_set(self, question, read: ReadQuestion) -> int | None:
        """Which value set the leaked stem shows: its numbers must equal one set's numbers exactly."""
        for text in (read.stem, read.stem_en):
            if not text:
                continue
            seen = numbers_in(text)
            for set_no, numbers in enumerate(self.set_numbers[question.id]):
                if seen == numbers:
                    return set_no
        return None

    def option_order(self, question, set_no: int | None, shown: list[str]) -> tuple[int, ...] | None:
        """The order the options were shown in, as bank indexes. None unless all four pair off one-to-one."""
        expected = fp.canonical_options(question, set_no)
        if len(shown) != 4:
            return None
        # The last option is often followed by stray text (a page footer, a channel's signature), so it is
        # also compared after trimming it to the length of the option it is being compared with.
        if question.kind == "numeric":
            want, got = [_option_key(o) for o in expected], [_option_key(o) for o in shown]
            if len(set(want)) == 4 and all(k[1] for k in want):
                if got[3] not in want:
                    got[3] = (got[3][0], got[3][1][:len(want[0][1])])
                return tuple(want.index(g) for g in got) if sorted(got) == sorted(want) else None
        want = [normalise(o, numbers=None) for o in expected]
        order = []
        for slot, option in enumerate(shown):
            text = normalise(option, numbers=None)
            scores = [fuzz.ratio(text, w) for w in want]
            if slot == 3 and max(scores) < 85:
                words = text.split()
                scores = [fuzz.ratio(" ".join(words[:len(w.split())]), w) for w in want]
            top = max(scores)
            if top < 85 or scores.count(top) > 1:
                return None
            order.append(scores.index(top))
        return tuple(order) if len(set(order)) == 4 else None


# Everyday words, so a cleanly written question is recognised as clean even when its subject is not in the bank.
_COMMON = frozenset("""
about above after again all also among and any are around because been before being below between both but can
could does down during each every few find first for from given has have how into its just known large largest
least less long made make many may more most much must name near not number off once one only other out over own
same shows small smallest some such take taken than that the their then there these they this those through time
two under until upon used using very was what when where which while who whose why will with within without would
you your called commonly following found mainly marked known example
""".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", unicodedata.normalize("NFKC", text).lower())


def _triples(word: str) -> list[str]:
    padded = f" {word} "
    return [padded[i:i + 3] for i in range(len(padded) - 2)]


_matchers: dict = {}


def matcher_for(bank) -> Matcher:
    if id(bank) not in _matchers:
        _matchers.clear()
        _matchers[id(bank)] = Matcher(bank)
    return _matchers[id(bank)]


def collect(questions: list[ReadQuestion], bank) -> list[Finding]:
    matcher = matcher_for(bank)
    findings, seen = [], set()
    for read in questions:
        finding = matcher.find(read)
        if not finding.matched and read.legible and not matcher.reads_like_words(read.stem_for_matching):
            # Typed text has no reader to flag what is hard to read. Text that is not made of word-like
            # strings (a ruined scan, or a script nothing here can read) is treated as hard to read, so it
            # can make a leak "unreadable" but never "not our paper".
            read.legible = False
        if finding.question_id in seen:                      # the same question twice: keep the first reading only
            finding.clues = []
        elif finding.question_id:
            seen.add(finding.question_id)
        findings.append(finding)
    return findings


# ---- deciding

def assess(findings: list[Finding]) -> str:
    """Before any decoding: "unreadable", "not_our_paper" or "decode".

    A paper is called not ours only when enough of it was legible and what did not match is clearly
    different. Damaged real questions land between the two scores, and those make a leak unreadable instead.
    """
    legible = sum(1 for f in findings if f.read.legible)
    matched = sum(1 for f in findings if f.matched)
    unmatched = [f for f in findings if not f.matched]
    damaged = sum(1 for f in unmatched if f.score >= CLEARLY_DIFFERENT or not f.read.legible)
    if legible < MIN_LEGIBLE and matched < 3:
        return "unreadable"
    if unmatched and damaged > len(unmatched) / 2 and matched < len(findings) / 2:
        return "unreadable"
    if legible >= MIN_LEGIBLE and matched < 0.2 * len(findings) and damaged == 0:
        return "not_our_paper"
    if matched == 0:
        return "unreadable"
    return "decode"


@dataclass
class Analysis:
    status: str                                # done | unreadable
    verdict: str | None = None                 # None when unreadable
    stage: str | None = None
    copy_no: int | None = None
    findings: list[Finding] = field(default_factory=list)
    decoded: fp.Decoded | None = None
    steps: list[dict] = field(default_factory=list)


def analyse_questions(questions: list[ReadQuestion], key: bytes, bank=None, exam_id: int = config.EXAM_ID,
                      n_translators: int = config.N_TRANSLATORS, n_print_copies: int = config.N_PRINT_COPIES) -> Analysis:
    """The whole decision for one leak's questions, with no database involved."""
    bank = bank or load_bank()
    findings = collect(questions, bank)
    decision = assess(findings)
    if decision == "unreadable":
        return Analysis("unreadable", findings=findings)
    if decision == "not_our_paper":
        return Analysis("done", "not_our_paper", findings=findings)
    clues = [c for f in findings for c in f.clues]
    decoded = fp.decode(clues, key, exam_id, bank, n_translators, n_print_copies)
    steps = fp.funnel(clues, key, exam_id, bank, n_translators, n_print_copies)
    return Analysis("done", decoded.verdict, decoded.stage, decoded.copy_no, findings, decoded, steps)


def analyse_text(raw: str, key: bytes, **kwargs) -> Analysis:
    return analyse_questions(parse_text(raw), key, **kwargs)


# ---- the worker's handler

def _store(conn: sqlite3.Connection, leak_id: int, result: Analysis, reader: str, elapsed_ms: int) -> int | None:
    conn.execute("DELETE FROM leak_questions WHERE leak_id = ?", (leak_id,))
    known = {r["id"] for r in conn.execute("SELECT id FROM questions")}
    matched_by_clue = {}
    if result.decoded and result.decoded.matched:
        matched_by_clue = {(c.question_id, c.kind): m for c, m in zip(result.decoded.scored, result.decoded.matched)}
    for f in result.findings:
        base = {"number": f.read.number, "stem": f.read.stem[:600], "legible": f.read.legible,
                "span": list(f.read.span) if f.read.span else None, "kind": f.kind}
        question_id = f.question_id if f.question_id in known else None
        base["bank_id"] = f.question_id
        rows = []
        if not f.matched:
            rows.append((None, {**base}, 0 if not f.read.legible else 1))
        elif f.kind == "numeric" and f.set_no is None:
            rows.append(("value", {**base, "set": None}, 0))
        for c in f.clues:
            detail = {**base, "matched": matched_by_clue.get((c.question_id, c.kind))}
            if c.kind == "value":
                detail["set"] = c.value
            if c.kind == "order":
                detail["order"] = list(c.value)
            rows.append((c.kind, detail, 1))
        if f.matched and not rows:
            rows.append((None, {**base}, 1))
        for clue_type, detail, read_ok in rows:
            conn.execute("INSERT INTO leak_questions (leak_id, question_id, clue_type, clue, match_score, read_ok) "
                         "VALUES (?, ?, ?, ?, ?, ?)",
                         (leak_id, question_id, clue_type, json.dumps(detail, ensure_ascii=False), f.score, read_ok))
    case_id = None
    conn.execute("DELETE FROM cases WHERE leak_id = ?", (leak_id,))
    if result.status == "done":
        copy_id = None
        if result.copy_no is not None:
            row = conn.execute("SELECT id FROM copies WHERE exam_id = ? AND stage = ? AND copy_no = ?",
                               (config.EXAM_ID, result.stage, result.copy_no)).fetchone()
            copy_id = row["id"] if row else None
        d = result.decoded
        # The stored funnel keeps counts only. Which copies were still in the running is never written down,
        # so an inconclusive case names nobody, even in the database.
        steps = {"copy_no": result.copy_no, "candidates": d.candidates if d else 0,
                 "steps": [{k: v for k, v in step.items() if k != "alive"} for step in result.steps]}
        cur = conn.execute(
            "INSERT INTO cases (leak_id, verdict, stage, copy_id, clues_read, clues_matched, expected_false_matches, "
            "steps, reader, elapsed_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (leak_id, result.verdict, result.stage, copy_id, d.clues if d else 0, d.score if d else 0,
             d.expected_false_matches if d else None, json.dumps(steps), reader, elapsed_ms, db.now()))
        case_id = cur.lastrowid
    has_exam = conn.execute("SELECT 1 FROM exams WHERE id = ?", (config.EXAM_ID,)).fetchone()
    conn.execute("UPDATE leaks SET status = ?, error = NULL, exam_id = ? WHERE id = ?",
                 (result.status, config.EXAM_ID if has_exam and result.verdict != "not_our_paper" and result.status == "done"
                  else None, leak_id))
    conn.commit()
    return case_id


def analyze_leak(conn: sqlite3.Connection, leak: sqlite3.Row, key: bytes, read_image=None, bank=None) -> int | None:
    """Analyse one queued leak: write leak_questions and a cases row, and set the leak's final status.

    `read_image(bytes) -> (questions dict, reader name)` reads a photo. It is only called for leaks with an image.
    Returns the new case id, or None when the leak was unreadable. A reader error is raised, and the
    worker then marks the leak failed with the reason.
    """
    started = time.monotonic()
    if leak["image_path"]:
        if read_image is None:
            raise RuntimeError("The photo reader is not set up. Add a Gemini key with: python -m canary vault set gemini_api_key")
        data, reader = read_image(Path(leak["image_path"]).read_bytes())
        questions = questions_from_reader(data)
    else:
        questions, reader = parse_text(leak["raw_text"] or ""), "typed text"
    result = analyse_questions(questions, key, bank=bank)
    return _store(conn, leak["id"], result, reader, int((time.monotonic() - started) * 1000))


def make_handler(vault, on_case=None):
    """The worker's handler, holding the vault's keys in memory. `on_case(leak_id, case_id)` is told about results."""
    from . import reader as photo_reader

    key = bytes.fromhex(vault.get("fingerprint_key"))

    def read_image(image: bytes):
        api_key = vault.get("gemini_api_key")
        if not api_key:
            raise photo_reader.ReaderError("No Gemini key in the vault, so photos cannot be read. Typed leaks still work.")
        data = photo_reader.read_image(image, api_key)
        return data, data.get("model") or photo_reader.model_name()

    def handler(conn: sqlite3.Connection, leak: sqlite3.Row) -> None:
        case_id = analyze_leak(conn, leak, key, read_image)
        if on_case:
            on_case(leak["id"], case_id)

    return handler
