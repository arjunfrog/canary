#!/usr/bin/env python3
"""Build canary/data/score_set_2.json: a second, harder set, added after the first one was saturated.

Run once:  .venv/bin/python scripts/make_score_set_2.py

Same rules as the first set: every leak comes from a known copy or is a known fake, the expected answer
follows the brief's maths applied to the clues the leak really carries, every third leak of each kind is
set aside, and the file is frozen once written.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from canary import fingerprint as fp  # noqa: E402
from canary import score  # noqa: E402
from canary.bank import load_bank  # noqa: E402
from canary.samples import (FAKE_PAPER, LABELS, MORE_FAKE, SAME_FRAME, garble, regional, retell_hard)  # noqa: E402

KEY = score.SCORE_KEY
OUT = ROOT / "canary" / "data" / "score_set_2.json"
rng = random.Random("canary-score-set-2")
bank = load_bank()
leaks = []
DEVANAGARI = str.maketrans("0123456789", "०१२३४५६७८९")


def copy_of(stage: str):
    n = rng.randint(1, 50 if stage == "translation" else 5000)
    render = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    return n, render(KEY, 1, n, bank)


def numeric_run(copy, count: int):
    runs, run = [], []
    for q in copy:
        if q.set_no is not None:
            run.append(q)
        else:
            if run:
                runs.append(run)
            run = []
    runs = [r for r in runs if len(r) >= count]
    run = rng.choice(runs)
    start = rng.randint(0, len(run) - count)
    return run[start:start + count]


def block(number, stem, opts) -> str:
    lines = [f"{number}. {stem}" if number is not None else stem]
    if opts:
        lines += [f"(A) {opts[0]}    (B) {opts[1]}", f"(C) {opts[2]}    (D) {opts[3]}"]
    return "\n".join(lines)


def agrees(verdict: str, source, intact, values=True, order=True) -> bool:
    decoded = fp.decode(fp.clues_from_rendered(intact, values=values, order=order), KEY, 1, bank, 50, 5000)
    if verdict in ("traced", "strong_lead"):
        return decoded.verdict == verdict and (decoded.stage, decoded.copy_no) == tuple(source)
    return decoded.verdict == verdict and decoded.copy_no is None


def add(kind, verdict, source, named, text=None, reader=None, note=""):
    leaks.append({"kind": kind, "note": note, "text": text, "reader": reader, "source": list(source) if source else None,
                  "expect": {"verdict": verdict, "copy": list(source) if named and source else None}})


def until(build):
    for _ in range(200):
        if build():
            return
    raise SystemExit("could not build an unambiguous leak")


# 1. fakes with no options, some sharing a sentence frame with a bank question
for i in range(6):
    picked = rng.sample(FAKE_PAPER + MORE_FAKE, rng.choice([8, 9, 10])) + rng.sample(SAME_FRAME, rng.choice([3, 4]))
    rng.shuffle(picked)
    text = "\n\n".join(block(j + 1, stem, None) for j, (stem, _) in enumerate(picked)) + "\n"
    add("fake_same_frame", "not_our_paper", None, False, text=text, note="fake, no options, 3 or 4 stems share a frame with a bank stem")

# 2. translated leaks with a loose retelling: reworded throughout, numbers sometimes in another order
for i in range(6):
    def build(i=i):
        n, copy = copy_of("translation")
        part = numeric_run(copy, rng.choice([13, 14, 15]))
        if not agrees("traced", ("translation", n), part):
            return False
        questions = [{"number": q.number, "legible": True,
                      "stem": f"प्रश्न {q.number}. इस प्रश्न का पाठ हिंदी में है।".translate(DEVANAGARI),
                      "options": [o.translate(DEVANAGARI) for o in q.options],
                      "stem_en": retell_hard(q.stem, seed=3000 + i), "options_en": list(q.options)} for q in part]
        add("translated_loose", "traced", ("translation", n), True, reader={"questions": questions}, note=f"{len(part)} numeric, loosely retold")
        return True
    until(build)

# 3. typed in Hindi with nobody to translate it: only the numbers, units and options can be read
for i in range(6):
    def build(i=i):
        n, copy = copy_of("translation")
        part = numeric_run(copy, rng.choice([12, 14]))
        if not agrees("traced", ("translation", n), part):
            return False
        digits = DEVANAGARI if i % 2 else {}
        text = "\n\n".join(block(q.number, regional(q.stem, seed=4000 + i).translate(digits), [o.translate(digits) for o in q.options])
                           for q in part) + "\n"
        add("regional_typed", "traced", ("translation", n), True, text=text,
            note=f"{len(part)} numeric, typed in Hindi, {'Devanagari' if i % 2 else 'ASCII'} digits")
        return True
    until(build)

# 4. a real leak inside a longer post: chatter, then real questions, then questions from somewhere else
for i in range(6):
    def build(i=i):
        stage = "translation" if i % 2 == 0 else "print"
        n, copy = copy_of(stage)
        part = numeric_run(copy, rng.choice([10, 12]))
        if not agrees("traced", (stage, n), part):
            return False
        extra = rng.sample(FAKE_PAPER + MORE_FAKE, 5)
        text = ("Guys this is the real one, my cousin got it from inside. Do not share outside the group.\n"
                "Payment only by UPI. 100% match or money back.\n\n"
                + "\n\n".join(block(q.number, q.stem, q.options) for q in part)
                + "\n\nBonus: expected questions from last year's coaching test\n\n"
                + "\n\n".join(block(200 + j, stem, opts) for j, (stem, opts) in enumerate(extra)) + "\n")
        add("mixed_post", "traced", (stage, n), True, text=text, note=f"{len(part)} real questions, chatter, then 5 from elsewhere")
        return True
    until(build)

# 5. damaged so badly that almost nothing is left: still "couldn't read it", never "not our paper"
for i in range(6):
    stage = "translation" if i % 2 == 0 else "print"
    n, copy = copy_of(stage)
    start = rng.randint(0, len(copy) - 14)
    part = copy[start:start + 14]
    rate = [0.7, 0.8, 0.9][i % 3]
    text = garble("\n\n".join(block(q.number, q.stem, q.options) for q in part) + "\n", rate, seed=5000 + i)
    add("garbled_heavy", "unreadable", (stage, n), False, text=text, note=f"typed text, damage {rate}")

# 6. no question numbers at all: paragraphs separated by blank lines
for i in range(6):
    def build(i=i):
        stage = "translation" if i % 2 == 0 else "print"
        n, copy = copy_of(stage)
        part = numeric_run(copy, rng.choice([12, 14]))
        if not agrees("traced", (stage, n), part):
            return False
        text = "\n\n".join(block(None, q.stem, q.options) for q in part) + "\n"
        add("unnumbered", "traced", (stage, n), True, text=text, note=f"{len(part)} questions with no numbers, blank lines between")
        return True
    until(build)

seen = {}
for leak in leaks:
    seen[leak["kind"]] = seen.get(leak["kind"], 0) + 1
    leak["held"] = seen[leak["kind"]] % 3 == 0
for i, leak in enumerate(leaks, start=101):
    leak["id"] = i

body = json.dumps({"format": "canary-score-set-1", "leaks": leaks}, ensure_ascii=False, indent=1)
OUT.write_text(body, encoding="utf-8")
held = sum(leak["held"] for leak in leaks)
print(f"Wrote {OUT.relative_to(ROOT)}: {len(leaks)} leaks, {len(leaks) - held} to read and {held} set aside.")
print(f"sha256 {hashlib.sha256(body.encode()).hexdigest()}")
