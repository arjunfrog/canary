"""The fingerprint engine: makes every copy from the key, and decodes a leak back to a copy.

Built so far: the keyed choice every copy is made from, the exact chance maths and the verdict bars.
Still to build (task 2 in docs/PROMPTS.md): rendering copies, decoding and the funnel.
"""
import hashlib
import hmac

TRACED_BAR = 1e-6          # expected false matches at or below this: traced
STRONG_LEAD_BAR = 1e-3     # at or below this: strong lead

CHANCE_VALUE = 1 / 8       # a decoy value set matching by luck
CHANCE_ORDER = 1 / 24      # an option order matching by luck
CHANCE_ORDER_FIXED_LAST = 1 / 6


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


def render_translator_copy(key: bytes, exam_id: int, copy_no: int, bank):
    """A translator's copy: decoy values, 6 traps mixed into biology, options in a keyed order."""
    raise NotImplementedError("task 2: render_translator_copy")


def render_print_copy(key: bytes, exam_id: int, copy_no: int, bank):
    """A printed copy: real values, no traps, options in a keyed order."""
    raise NotImplementedError("task 2: render_print_copy")


def decode(clues: list, key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int):
    """Score every candidate copy against the clues and return stage, verdict, copy and the maths."""
    raise NotImplementedError("task 2: decode")


def funnel(clues: list, key: bytes, exam_id: int, bank, n_translators: int, n_print_copies: int) -> list[dict]:
    """After each clue: how many copies still fit, and the expected false matches so far."""
    raise NotImplementedError("task 2: funnel")
