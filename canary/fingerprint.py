"""The fingerprint engine: makes every copy from the key, and decodes a leak back to a copy.

Every per-copy choice comes from pick(), an HMAC-SHA256 of the exam, stage, copy number, question and
purpose under the secret key. Decoding recomputes those choices for every candidate copy, counts how
many clues each one matches, and works out exactly how likely that many matches would be by luck.

The tables of per-copy choices are derived from the key, so they are kept in memory only.
"""
import hashlib
import hmac
import itertools
import re
from dataclasses import dataclass, field

import numpy as np

TRACED_BAR = 1e-6          # expected false matches at or below this: traced
STRONG_LEAD_BAR = 1e-3     # at or below this: strong lead

CHANCE_VALUE = 1 / 8       # a decoy value set matching by luck
CHANCE_ORDER = 1 / 24      # an option order matching by luck
CHANCE_ORDER_FIXED_LAST = 1 / 6

N_DECOYS = 8
TRAPS_PER_TRANSLATOR = 6
FUNNEL_MISS_SHARE = 0.25   # a copy stays plausible in the funnel while it has missed at most this share of clues
ALIVE_LIST_LIMIT = 600     # funnel steps list the surviving copies only while there are this few

PERMS4 = tuple(itertools.permutations(range(4)))
PERMS3 = tuple(itertools.permutations(range(3)))
_LAST_OPTION = re.compile(r"^(all|none|both|neither)\b.*\b(above|these|them)\b|^(all|none) of the", re.I)


def pick(key: bytes, exam_id: int, stage: str, copy_no: int, question_id: str, purpose: str, n: int) -> int:
    """The one source of every per-copy choice: a keyed number from 0 to n-1.

    The same inputs always give the same number, and without the key nobody can predict it.
    """
    message = f"{exam_id}|{stage}|{copy_no}|{question_id}|{purpose}".encode()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return int.from_bytes(digest, "big") % n


def tail(chances: list[float], m: int) -> float:
    """Exact probability that at least m of these clues match by luck (Poisson-binomial)."""
    dist = [1.0] + [0.0] * len(chances)
    for p in chances:
        for j in range(len(chances), 0, -1):
            dist[j] = dist[j] * (1 - p) + dist[j - 1] * p
        dist[0] *= 1 - p
    return sum(dist[m:])


def expected_false_matches(n_candidates: int, chances: list[float], matched: int) -> float:
    return n_candidates * tail(chances, matched)


def verdict_for(expected: float) -> str:
    if expected <= TRACED_BAR:
        return "traced"
    if expected <= STRONG_LEAD_BAR:
        return "strong_lead"
    return "inconclusive"


# ---- the choices a copy is made from

def canonical_options(question, set_no: int | None = None) -> tuple[str, ...]:
    """A question's four options in bank order. Copies show them reordered."""
    if question.kind == "numeric":
        return question.value_sets[set_no or 0].options
    return question.options


def fixed_last_index(question) -> int | None:
    """Bank index of an option such as "all of the above", which must stay last. None for most questions."""
    for i, option in enumerate(canonical_options(question)):
        if _LAST_OPTION.search(option.strip()):
            return i
    return None


def order_chance(question) -> float | None:
    """How often an option order matches by luck. None when the order is pinned and so carries no clue."""
    if question.pinned_order:
        return None
    return CHANCE_ORDER_FIXED_LAST if fixed_last_index(question) is not None else CHANCE_ORDER


def _orders(question) -> tuple[tuple[int, ...], ...]:
    """Every order this question can be shown in. order[slot] is the bank index of the option shown there."""
    if question.pinned_order:
        return ((0, 1, 2, 3),)
    last = fixed_last_index(question)
    if last is None:
        return PERMS4
    rest = [i for i in range(4) if i != last]
    return tuple(tuple(rest[i] for i in perm) + (last,) for perm in PERMS3)


def order_for(key: bytes, exam_id: int, stage: str, copy_no: int, question) -> tuple[int, ...]:
    orders = _orders(question)
    if len(orders) == 1:
        return orders[0]
    return orders[pick(key, exam_id, stage, copy_no, question.id, "order", len(orders))]


def value_set_for(key: bytes, exam_id: int, copy_no: int, question) -> int:
    """The decoy value set (1 to 8) a translator sees for a numeric question. Never 0, the real one."""
    return 1 + pick(key, exam_id, "translation", copy_no, question.id, "values", N_DECOYS)


def traps_for(key: bytes, exam_id: int, copy_no: int, bank) -> list:
    """The 6 trap questions mixed into one translator's copy: the 6 lowest keyed ranks among the pool."""
    ranked = sorted(bank.traps, key=lambda q: (pick(key, exam_id, "translation", copy_no, q.id, "trap", 2**64), q.id))
    return ranked[:TRAPS_PER_TRANSLATOR]


@dataclass(frozen=True)
class Rendered:
    """One question as a copy shows it."""
    number: int                      # the number printed on this copy
    question_id: str
    subject: str
    stem: str
    options: tuple[str, ...]         # in the order shown
    order: tuple[int, ...]           # order[slot] = bank index of the option shown in that slot
    set_no: int | None = None        # numeric only: 0 is the real set, 1 to 8 are decoys
    is_trap: bool = False
    pinned: bool = False             # the option order is the same on every copy, so it is no clue


def _render(key: bytes, exam_id: int, stage: str, copy_no: int, questions: list, set_of) -> list[Rendered]:
    out = []
    for number, q in enumerate(questions, start=1):
        set_no = set_of(q) if q.kind == "numeric" else None
        options = canonical_options(q, set_no)
        order = order_for(key, exam_id, stage, copy_no, q)
        stem = q.value_sets[set_no].stem if q.kind == "numeric" else q.stem
        out.append(Rendered(number, q.id, q.subject, stem, tuple(options[i] for i in order), order, set_no,
                            q.kind == "trap", len(_orders(q)) == 1))
    return out


def render_translator_copy(key: bytes, exam_id: int, copy_no: int, bank) -> list[Rendered]:
    """A translator's copy: decoy values, 6 traps mixed into biology, options in a keyed order."""
    paper = bank.paper
    biology = [i for i, q in enumerate(paper) if q.subject == "biology"]
    start = biology[0] if biology else len(paper)
    slots: dict[int, list] = {}
    for trap in traps_for(key, exam_id, copy_no, bank):
        slot = pick(key, exam_id, "translation", copy_no, trap.id, "position", len(biology) + 1)
        slots.setdefault(start + slot, []).append(trap)
    questions = []
    for i, q in enumerate(paper):
        questions += sorted(slots.get(i, []), key=lambda t: t.id)
        questions.append(q)
    questions += sorted(slots.get(len(paper), []), key=lambda t: t.id)
    return _render(key, exam_id, "translation", copy_no, questions, lambda q: value_set_for(key, exam_id, copy_no, q))


def render_print_copy(key: bytes, exam_id: int, copy_no: int, bank) -> list[Rendered]:
    """A printed copy: real values, no traps, options in a keyed order."""
    return _render(key, exam_id, "print", copy_no, bank.paper, lambda q: 0)


# ---- clues and decoding

@dataclass(frozen=True)
class Clue:
    """One thing read from a leak about one question.

    kind "value": value is the set number the leak shows (0 means the real values).
    kind "trap":  this trap question appears in the leak.
    kind "order": value is the option order read, as bank indexes in the order shown.
    """
    question_id: str
    kind: str
    value: object = None


def clues_from_rendered(rendered: list[Rendered], values: bool = True, order: bool = True, traps: bool = True) -> list[Clue]:
    """The clues a perfect read of these questions would give. Used by tests, the health check and the simulation."""
    out = []
    for r in rendered:
        if r.is_trap and traps:
            out.append(Clue(r.question_id, "trap"))
        if r.set_no is not None and values:
            out.append(Clue(r.question_id, "value", r.set_no))
        if order and not r.pinned:
            out.append(Clue(r.question_id, "order", r.order))
    return out


def _code(order) -> int:
    return sum(int(p) << (2 * i) for i, p in enumerate(order))


class Codebook:
    """Every candidate copy's choices for one exam, computed on demand and kept in memory.

    Copy numbers run from 1. Arrays are indexed by copy_no - 1.
    """

    def __init__(self, key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int):
        self.exam_id, self.bank = exam_id, bank
        self.n = {"translation": n_translators, "print": n_print_copies}
        self._mac = hmac.new(key, digestmod=hashlib.sha256)
        self._cache: dict = {}
        self._traps: np.ndarray | None = None

    def _picks(self, stage: str, question_id: str, purpose: str, n: int) -> np.ndarray:
        tail_part = f"|{question_id}|{purpose}".encode()
        head = f"{self.exam_id}|{stage}|".encode()
        out = np.empty(self.n[stage], dtype=np.int64)
        for i in range(self.n[stage]):
            mac = self._mac.copy()
            mac.update(head + str(i + 1).encode() + tail_part)
            out[i] = int.from_bytes(mac.digest(), "big") % n
        return out

    def value_sets(self, question_id: str) -> np.ndarray:
        """The decoy set each translator holds for this numeric question."""
        got = self._cache.get(("values", question_id))
        if got is None:
            got = self._cache[("values", question_id)] = 1 + self._picks("translation", question_id, "values", N_DECOYS)
        return got

    def orders(self, stage: str, question_id: str) -> np.ndarray | None:
        """The option order each copy of this stage shows, as a code. None for pinned questions."""
        cache_key = ("order", stage, question_id)
        if cache_key not in self._cache:
            orders = _orders(self.bank.by_id[question_id])
            if len(orders) == 1:
                self._cache[cache_key] = None
            else:
                codes = np.array([_code(o) for o in orders], dtype=np.int64)
                self._cache[cache_key] = codes[self._picks(stage, question_id, "order", len(orders))]
        return self._cache[cache_key]

    def trap_table(self) -> tuple[list[str], np.ndarray]:
        """(trap ids, a translators x traps table of who holds which)."""
        if self._traps is None:
            traps = sorted(q.id for q in self.bank.traps)
            ranks = np.empty((self.n["translation"], len(traps)), dtype=object)
            for j, trap_id in enumerate(traps):
                head = f"{self.exam_id}|translation|".encode()
                rest = f"|{trap_id}|trap".encode()
                for i in range(self.n["translation"]):
                    mac = self._mac.copy()
                    mac.update(head + str(i + 1).encode() + rest)
                    ranks[i, j] = (int.from_bytes(mac.digest(), "big") % 2**64, trap_id)
            holds = np.zeros(ranks.shape, dtype=bool)
            for i in range(ranks.shape[0]):
                lowest = sorted(range(len(traps)), key=lambda j: ranks[i, j])[:TRAPS_PER_TRANSLATOR]
                holds[i, lowest] = True
            self._traps = (traps, holds)
        return self._traps

    def holds_trap(self, question_id: str) -> np.ndarray:
        traps, holds = self.trap_table()
        return holds[:, traps.index(question_id)]

    def trap_share(self, question_id: str) -> float:
        """The share of translators holding this trap: how often it matches a translator by luck."""
        return float(self.holds_trap(question_id).mean())


_books: dict = {}


def codebook(key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int) -> Codebook:
    cache_key = (hashlib.sha256(key).hexdigest(), exam_id, id(bank), n_translators, n_print_copies)
    if cache_key not in _books:
        if len(_books) >= 4:
            _books.clear()
        _books[cache_key] = Codebook(key, exam_id, bank, n_translators, n_print_copies)
    return _books[cache_key]


@dataclass
class Decoded:
    stage: str | None                 # "translation", "print", or None when the clues fit either
    verdict: str                      # traced | strong_lead | inconclusive
    copy_no: int | None               # None unless traced or strong_lead
    score: int                        # clues matched by the best candidate
    clues: int                        # clues that could be scored
    expected_false_matches: float
    candidates: int
    tie: bool = False
    matched: list[bool] = field(default_factory=list)      # per scored clue, for the named copy only
    scored: list[Clue] = field(default_factory=list)       # the clues that were scored, in order
    chances: list[float] = field(default_factory=list)


def decide_stage(clues: list[Clue]) -> str | None:
    """Decoy values or traps mean a translator copy. Real values and neither of those mean a printed copy."""
    if any(c.kind == "trap" or (c.kind == "value" and c.value) for c in clues):
        return "translation"
    if any(c.kind == "value" and c.value == 0 for c in clues):
        return "print"
    return None


def _score_table(clues: list[Clue], book: Codebook, stage: str | None):
    """For the candidates of this stage: which clues can be scored, their chance rates, and a
    clues x candidates table of matches. Candidates are translators first, then printed copies."""
    stages = [stage] if stage else ["translation", "print"]
    scored, chances, rows = [], [], []
    for clue in clues:
        question = book.bank.by_id.get(clue.question_id)
        if question is None:
            continue
        parts = []
        if clue.kind == "value":
            if not clue.value or stage != "translation" or question.kind != "numeric":
                continue                                   # real values name no copy: every printed copy has them
            chance = CHANCE_VALUE
            parts.append(book.value_sets(question.id) == int(clue.value))
        elif clue.kind == "trap":
            if stage != "translation" or question.kind != "trap":
                continue
            chance = book.trap_share(question.id)
            parts.append(book.holds_trap(question.id))
        elif clue.kind == "order":
            chance = order_chance(question)
            if chance is None or clue.value is None or (question.kind == "trap" and stage == "print"):
                continue
            code = _code(clue.value)
            for s in stages:
                if question.kind == "trap" and s == "print":
                    parts.append(np.zeros(book.n[s], dtype=bool))
                else:
                    parts.append(book.orders(s, question.id) == code)
        else:
            continue
        scored.append(clue)
        chances.append(chance)
        rows.append(np.concatenate(parts))
    n = sum(book.n[s] for s in stages)
    table = np.array(rows, dtype=bool) if rows else np.zeros((0, n), dtype=bool)
    return stages, scored, chances, table, n


def _candidate(index: int, stages: list[str], book: Codebook) -> tuple[str, int]:
    """Turn a table column back into (stage, copy_no)."""
    for s in stages:
        if index < book.n[s]:
            return s, index + 1
        index -= book.n[s]
    raise IndexError(index)


def decode(clues: list[Clue], key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int) -> Decoded:
    """Score every candidate copy against the clues and return stage, verdict, copy and the maths."""
    book = codebook(key, exam_id, bank, n_translators, n_print_copies)
    stage = decide_stage(clues)
    stages, scored, chances, table, n = _score_table(clues, book, stage)
    if not scored:
        return Decoded(stage, "inconclusive", None, 0, 0, float(n), n)
    scores = table.sum(axis=0)
    best = int(scores.max())
    winners = np.flatnonzero(scores == best)
    expected = expected_false_matches(n, chances, best)
    tie = len(winners) > 1
    verdict = "inconclusive" if tie or best == 0 else verdict_for(expected)
    out = Decoded(stage, verdict, None, best, len(scored), expected, n, tie=tie, scored=scored, chances=chances)
    if verdict != "inconclusive":                          # a copy is named only at or under a bar
        out.stage, out.copy_no = _candidate(int(winners[0]), stages, book)
        out.matched = [bool(x) for x in table[:, winners[0]]]
    return out


def funnel(clues: list[Clue], key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int) -> list[dict]:
    """After each clue: how many copies still fit, and the expected false matches so far.

    A copy still fits after i clues if it has missed at most floor(0.25 x i) of them, so one misread
    clue does not throw the right copy out. `alive` lists the surviving candidates (translators first,
    then printed copies, counted from 0) once there are few enough to list.
    """
    book = codebook(key, exam_id, bank, n_translators, n_print_copies)
    stage = decide_stage(clues)
    stages, scored, chances, table, n = _score_table(clues, book, stage)
    steps = []
    running = np.zeros(n, dtype=np.int64)
    for i, (clue, chance) in enumerate(zip(scored, chances), start=1):
        running = running + table[i - 1]
        alive = np.flatnonzero(running >= i - int(FUNNEL_MISS_SHARE * i))
        steps.append({
            "clue": i,
            "question_id": clue.question_id,
            "kind": clue.kind,
            "chance": chance,
            "candidates": n,
            "remaining": int(len(alive)),
            "best": int(running.max()),
            "expected_false_matches": expected_false_matches(n, chances[:i], int(running.max())),
            "alive": [int(a) for a in alive] if len(alive) <= ALIVE_LIST_LIMIT else None,
        })
    return steps
