"""The limits simulation behind the Limits chart.

A Monte Carlo run using the real bars and chance rates from fingerprint.py: for each scenario and each
number of questions leaked, how often the right copy is named and how often a wrong one is, at both bars.

The best score among the innocent copies is drawn exactly, from the Poisson-binomial distribution of one
innocent copy's score raised to the number of such copies. Misreads are independent of each other, which
a real photo reader's may not be. Misread rates are assumptions unless CANARY_HOME/measured.json exists.
docs/research/fingerprint_sim.py is the research version this grew from.
"""
import json
import os
from pathlib import Path

import numpy as np

from . import config, db
from . import fingerprint as fp

KS = (3, 5, 8, 10, 14, 20, 30)
TRAP_CHANCE = fp.TRAPS_PER_TRANSLATOR / 24
DEFAULT_RATES = {"typed_value": 0.02, "retold_value": 0.05, "photo_value": 0.05, "photo_order": 0.10}


def limits_path() -> Path:
    return config.home() / "limits.json"


def load_rates() -> tuple[dict, str]:
    """Misread rates: measured ones if CANARY_HOME/measured.json has them, otherwise the assumed defaults."""
    rates, source = dict(DEFAULT_RATES), "assumed"
    path = config.home() / "measured.json"
    if path.exists():
        try:
            measured = json.loads(path.read_text(encoding="utf-8"))
            found = {k: float(measured[k]) for k in DEFAULT_RATES if k in measured and 0 <= float(measured[k]) <= 1}
        except (ValueError, TypeError, OSError):
            found = {}
        if found:
            rates.update(found)
            source = "measured" if len(found) == len(DEFAULT_RATES) else "partly measured"
    return rates, source


def score_pmf(chances: list[float]) -> np.ndarray:
    """pmf[m] = probability that an innocent copy matches exactly m of these clues by luck."""
    dist = np.zeros(len(chances) + 1)
    dist[0] = 1.0
    for p in chances:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    return dist


def threshold(chances: list[float], n: int, bar: float) -> int | None:
    """The fewest matches that put the expected false matches at or under the bar. None if no score can."""
    for m in range(1, len(chances) + 1):
        if fp.expected_false_matches(n, chances, m) <= bar:
            return m
    return None


def best_of_others(rng, chances: list[float], others: int, trials: int) -> np.ndarray:
    """The highest score among `others` innocent copies, drawn exactly for each trial."""
    cdf = np.clip(np.cumsum(score_pmf(chances)), 0.0, 1.0) ** others
    return np.searchsorted(cdf, rng.random(trials), side="left").clip(0, len(chances))


def _outcome(true: np.ndarray, best: np.ndarray, chances: list[float], n: int) -> dict:
    """Shares of trials in which the right copy, or a wrong one, is named at each bar."""
    out = {}
    for name, bar in (("lead", fp.STRONG_LEAD_BAR), ("traced", fp.TRACED_BAR)):
        t = threshold(chances, n, bar)
        if t is None:
            out[f"{name}_right"], out[f"{name}_wrong"], out[f"{name}_needs"] = 0.0, 0.0, None
            continue
        out[f"{name}_right"] = float(np.mean((true >= t) & (true > best)))      # a tie names nobody
        out[f"{name}_wrong"] = float(np.mean((best >= t) & (best > true)))
        out[f"{name}_needs"] = t
    out["clues"] = len(chances)
    return out


def simulate_single(rng, groups: list[tuple[int, float, float]], n: int, trials: int) -> dict:
    """One leaker. groups: (clue count, chance rate, misread rate). A misread clue matches only by luck."""
    chances = [p for k, p, _ in groups for _ in range(k)]
    if not chances:
        return {"lead_right": 0.0, "lead_wrong": 0.0, "traced_right": 0.0, "traced_wrong": 0.0,
                "lead_needs": None, "traced_needs": None, "clues": 0}
    true = np.zeros(trials, dtype=int)
    for k, p, err in groups:
        true += rng.binomial(k, (1 - err) + err * p, trials)
    return _outcome(true, best_of_others(rng, chances, n - 1, trials), chances, n)


def simulate_merged(rng, k: int, p: float, err: float, n: int, trials: int, leakers: int = 2) -> dict:
    """Leakers merge their copies: each question comes from one of them. Right means one of them is named."""
    owner = rng.integers(0, leakers, (trials, k))
    scores = np.zeros((trials, leakers), dtype=int)
    for j in range(leakers):
        chance = np.where(owner == j, (1 - err) + err * p, p)
        scores[:, j] = (rng.random((trials, k)) < chance).sum(axis=1)
    top = scores.max(axis=1)
    unique = (scores == top[:, None]).sum(axis=1) == 1                   # two leakers tying names nobody
    chances = [p] * k
    best = best_of_others(rng, chances, n - leakers, trials)
    out = _outcome(np.where(unique, top, -1), best, chances, n)
    for name in ("lead", "traced"):
        t = out[f"{name}_needs"]
        if t is not None:
            out[f"{name}_wrong"] = float(np.mean((best >= t) & (best > top)))
    return out


def scenarios(rates: dict) -> list[dict]:
    nt, npc = config.N_TRANSLATORS, config.N_PRINT_COPIES
    value, order = fp.CHANCE_VALUE, fp.CHANCE_ORDER
    return [
        {"key": "translator_typed", "title": "Translator leak, typed, values kept", "candidates": nt,
         "groups": lambda k: [(k, value, rates["typed_value"])]},
        {"key": "translator_retold", "title": "Translator leak, retold or translated", "candidates": nt,
         "groups": lambda k: [(k, value, rates["retold_value"])]},
        {"key": "translator_photo", "title": "Translator leak, phone photo with options visible", "candidates": nt,
         "groups": lambda k: [(k, value, rates["photo_value"]), (k, order, rates["photo_order"])]},
        {"key": "translator_no_numbers", "title": "Translator leak with numbers removed (traps only)", "candidates": nt,
         "groups": lambda k: [(min(k, fp.TRAPS_PER_TRANSLATOR), TRAP_CHANCE, 0.0)]},
        {"key": "translators_merged", "title": "Two translators merging their copies", "candidates": nt, "merged": True},
        {"key": "print_photo", "title": "Printed copy, photo with options visible", "candidates": npc,
         "groups": lambda k: [(k, order, rates["photo_order"])]},
        {"key": "print_reshuffled", "title": "Printed copy, options reshuffled or left out", "candidates": npc,
         "groups": lambda k: []},
    ]


def _runs(share: float) -> str:
    if share >= 0.9995:
        return "in every run"
    if share <= 0:
        return "in no run"
    return f"in {share * 100:.1f}% of runs"


def describe(scenario: dict, trials: int) -> str:
    """One sentence saying what happens, failures as plainly as successes."""
    points = {p["k"]: p for p in scenario["points"]}
    lead_wrong = max(p["lead_wrong"] for p in scenario["points"])
    traced_wrong = max(p["traced_wrong"] for p in scenario["points"])
    if lead_wrong == 0 and traced_wrong == 0:
        wrong_words = f"No wrong copy was named in {trials:,} runs per point."
    else:
        wrong_words = (f"A wrong copy was named at the strong-lead bar in up to {lead_wrong * 100:.2f}% of runs, and "
                       + ("never at the traced bar." if traced_wrong == 0 else f"at the traced bar in up to {traced_wrong * 100:.3f}%."))
    best = max(p["lead_right"] for p in scenario["points"])
    if best == 0:
        reason = {"translator_no_numbers": "A translator holds 6 traps, and traps alone need 8 to reach even the strong-lead bar.",
                  "print_reshuffled": "After printing, option order is the only clue. Without it nothing differs from copy to copy."
                  }.get(scenario["key"], "The clues never reach the bar.")
        return f"Canary cannot name anyone here, and says \"Not enough to name anyone yet\". {reason}"
    p14, p30 = points[14], points[30]
    if scenario["key"] == "translators_merged":
        return (f"Weak. With 14 questions one of the two is traced {_runs(p14['traced_right'])} and is a strong lead "
                f"{_runs(p14['lead_right'])}. With 30 questions one is traced {_runs(p30['traced_right'])}. {wrong_words}")
    return (f"With 14 questions the right copy is traced {_runs(p14['traced_right'])} and is at least a strong lead "
            f"{_runs(p14['lead_right'])}. With 5 questions it is traced {_runs(points[5]['traced_right'])}. {wrong_words}")


def run_sim(out: Path | None = None, trials: int = 20000, seed: int = 7) -> dict:
    """Run every scenario and write the results as JSON (CANARY_HOME/limits.json by default)."""
    rng = np.random.default_rng(seed)
    rates, source = load_rates()
    result = {"generated_at": db.now(), "trials": trials, "seed": seed, "ks": list(KS),
              "translators": config.N_TRANSLATORS, "print_copies": config.N_PRINT_COPIES,
              "bars": {"traced": fp.TRACED_BAR, "strong_lead": fp.STRONG_LEAD_BAR},
              "rates": rates, "rates_source": source, "scenarios": []}
    for s in scenarios(rates):
        points = []
        for k in KS:
            if s.get("merged"):
                point = simulate_merged(rng, k, fp.CHANCE_VALUE, rates["retold_value"], s["candidates"], trials)
            else:
                point = simulate_single(rng, s["groups"](k), s["candidates"], trials)
            points.append({"k": k, **point})
        entry = {"key": s["key"], "title": s["title"], "candidates": s["candidates"], "points": points}
        entry["sentence"] = describe(entry, trials)
        result["scenarios"].append(entry)
    out = out or limits_path()
    config.ensure_home()
    fd = os.open(out, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    return result


def load_limits(path: Path | None = None) -> dict | None:
    """The saved results, or None if the simulation has not been run or the file cannot be used."""
    path = path or limits_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data["scenarios"] or not all(len(s["points"]) == len(data["ks"]) for s in data["scenarios"]):
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None
