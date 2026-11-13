#!/usr/bin/env python3
"""Monte Carlo check of Canary's tracing limits.

Two stages, each with its own candidates and clues:
  translation: 50 translator copies. Clues: decoy value set (chance 1/8),
               trap question (chance 1/4), option order (chance 1/24).
  print:       5,000 printed copies. Clue: option order (chance 1/24).

A leak's clues are compared with every candidate copy. Score = clues matched.
A copy is named only if candidates x P(at least that many matches by luck) is
under the bar: 1e-6 for Traced, 1e-3 for Strong lead. The probability is exact
(Poisson-binomial). Misreads are independent, which real photo readers may not be.

Usage: fingerprint_sim.py [--trials 4000] [--seed 7]
"""
import argparse
import numpy as np

VALUE, TRAP, ORDER = 1 / 8, 1 / 4, 1 / 24
BARS = (("Strong lead", 1e-3), ("Traced", 1e-6))
KS = (5, 8, 10, 14, 20, 30)


def tail_table(ps):
    """tail[m] = P(at least m matches by luck) for clues with chance rates ps."""
    dist = np.zeros(len(ps) + 1)
    dist[0] = 1.0
    for p in ps:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    return np.cumsum(dist[::-1])[::-1]


def threshold(ps, n, bar):
    hits = np.nonzero(n * tail_table(ps) <= bar)[0]
    return int(hits[0]) if len(hits) and hits[0] > 0 else None


def draw(rng, groups, trials, n_others):
    """groups: list of (clue count, chance rate, misread rate)."""
    true = np.zeros(trials, dtype=int)
    best = np.zeros((trials, n_others), dtype=int)
    for k, p, err in groups:
        true += rng.binomial(k, (1 - err) + err * p, trials)
        best += rng.binomial(k, p, (trials, n_others))
    return true, best.max(axis=1)


def single(rng, groups, n, trials):
    ps = [p for k, p, _ in groups for _ in range(k)]
    true, best = draw(rng, groups, trials, n - 1)
    out = []
    for _, bar in BARS:
        t = threshold(ps, n, bar)
        if t is None:
            out.append(None)
            continue
        right = np.mean((true >= t) & (true > best))
        wrong = int(np.sum((best >= t) & (best >= true)))
        out.append((right * 100, t, len(ps), wrong))
    return out


def merged(rng, k, p, err, n, trials, leakers, extra=()):
    """Leakers merge copies: each question comes from one of them."""
    owner = rng.integers(0, leakers, (trials, k))
    scores = np.zeros((trials, leakers), dtype=int)
    for j in range(leakers):
        chance = np.where(owner == j, (1 - err) + err * p, p)
        scores[:, j] = (rng.random((trials, k)) < chance).sum(axis=1)
    best = rng.binomial(k, p, (trials, n - leakers)).max(axis=1)
    ps = [p] * k
    out = []
    for _, bar in BARS:
        t = threshold(ps, n, bar)
        if t is None:
            out.append(None)
            continue
        top = scores.max(axis=1)
        out.append((np.mean((top >= t) & (top > best)) * 100, t, k, int(np.sum(best >= t))))
    return out


def cell(r):
    return "never" if r is None else f"{r[0]:5.1f}% {r[1]}/{r[2]} w{r[3]}"


def table(title, rows, compute):
    for i, (label, _) in enumerate(BARS):
        print(f"== {title}, {label}: right copy named % [matches needed/clues], wrong namings")
        print(f"{'scenario':46s}" + "".join(f"{'k=' + str(k):>17s}" for k in KS))
        for name, fn in rows:
            print(f"{name:46s}" + "".join(f"{cell(compute(fn, k)[i]):>17s}" for k in KS))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    nt, npc = 50, 5000
    print(f"translators={nt} print copies={npc} trials={a.trials} seed={a.seed}")
    print("k = questions leaked. Misread rates are assumed, not measured.\n")

    translation = [
        ("Typed, values kept (2% misread)", lambda k: [(k, VALUE, 0.02)]),
        ("Retold or translated (5% misread)", lambda k: [(k, VALUE, 0.05)]),
        ("Messy handwriting (20% misread)", lambda k: [(k, VALUE, 0.20)]),
        ("Phone photo: values 5%, option order 10%", lambda k: [(k, VALUE, 0.05), (k, ORDER, 0.10)]),
        ("Typed, values kept, plus 3 traps seen", lambda k: [(k, VALUE, 0.02), (3, TRAP, 0.0)]),
    ]
    table("Translation stage, 50 translators", translation,
          lambda fn, k: single(rng, fn(k), nt, a.trials))

    print("Numbers removed: a translator holds 6 traps and traps alone need 8 for a")
    print("Strong lead, so a leak with no numbers and no option order is never named.\n")

    printed = [
        ("Clean photo or retype (2% misread)", lambda k: [(k, ORDER, 0.02)]),
        ("Typical phone photo (10% misread)", lambda k: [(k, ORDER, 0.10)]),
        ("Messy handwriting (20% misread)", lambda k: [(k, ORDER, 0.20)]),
    ]
    table("Print stage, 5,000 copies, option order", printed,
          lambda fn, k: single(rng, fn(k), npc, a.trials))
    print("Print stage with options reshuffled or left out: no clue, never named.\n")

    for leakers in (2, 3):
        rows = [(f"{leakers} translators merge, values (5% misread)", leakers)]
        table("Merged copies, at least one leaker named", rows,
              lambda L, k: merged(rng, k, VALUE, 0.05, nt, a.trials, L))

    print("== Fewest clean clues that can reach each bar")
    for name, p, n in (("value sets, 50 translators", VALUE, nt),
                       ("value sets, 500 translators", VALUE, 500),
                       ("traps, 50 translators", TRAP, nt),
                       ("option order, 5,000 copies", ORDER, npc),
                       ("option order, 50,000 copies", ORDER, 50000)):
        for label, bar in BARS:
            k = next(k for k in range(1, 200) if n * p**k <= bar)
            print(f"  {name:30s} {label:12s} needs {k}")


if __name__ == "__main__":
    main()
