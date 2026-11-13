#!/usr/bin/env python3
"""Build canary/data/score_set.json: the leaks `python -m canary score` is measured on.

Run once:  .venv/bin/python scripts/make_score_set.py

Every leak is made from a known copy (or is a known fake), so its right answer is known before the tool
sees it. The expected verdict follows the brief's published bars applied to the clues the leak really
carries, never what the tool happens to say. Every third leak of each kind is set aside ("held": true):
those are only ever scored, never read. The file is frozen once written. Do not edit a leak or its
expected answer to raise the score.
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
from canary.samples import (FAKE_PAPER, FAKE_TOPICAL, LABELS, MORE_FAKE, MORE_TOPICAL, garble, retell,  # noqa: E402
                            strip_numbers, typos)

KEY = score.SCORE_KEY
OUT = ROOT / "canary" / "data" / "score_set.json"
rng = random.Random("canary-score-set-1")
bank = load_bank()
leaks = []


def copy_of(stage: str):
    n = rng.randint(1, 50 if stage == "translation" else 5000)
    render = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    return n, render(KEY, 1, n, bank)


def numeric_run(copy, count: int):
    """`count` consecutive numeric questions from the physics or chemistry part of a copy."""
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


def biology_run(copy, count: int, want_trap: bool | None = None):
    bio = [q for q in copy if q.subject == "biology" and not q.pinned]
    for _ in range(200):
        start = rng.randint(0, len(bio) - count)
        part = bio[start:start + count]
        if want_trap is None or any(q.is_trap for q in part) == want_trap:
            return part
    raise SystemExit("no biology run fits")


def any_run(copy, count: int):
    start = rng.randint(0, len(copy) - count)
    return copy[start:start + count]


def shown(q, options=True, stem=None, opts=None):
    return {"number": q.number, "stem": stem if stem is not None else q.stem,
            "options": list(opts if opts is not None else q.options) if options else []}


def write(items, style: str, renumber: bool = False, header: str = "", footer: str = "") -> str:
    """Type questions out in one of the ways leaks really get pasted."""
    blocks = []
    for i, item in enumerate(items):
        number = i + 1 if renumber else item["number"]
        stem, opts = item["stem"], item["options"]
        if style == "q_paren":
            lines = [f"Q{number}) {stem}"] + [f"{'abcd'[j]}) {o}" for j, o in enumerate(opts)]
        elif style == "numeric_labels":
            lines = [f"{number}. {stem}"] + ([" ".join(f"({j + 1}) {o}" for j, o in enumerate(opts))] if opts else [])
        elif style == "one_line":
            lines = [f"{number}. {stem} " + " ".join(f"({LABELS[j]}) {o}" for j, o in enumerate(opts))]
        elif style == "dotted":
            lines = [f"{number}) {stem}"] + [f"{LABELS[j]}. {o}" for j, o in enumerate(opts)]
        else:
            lines = [f"{number}. {stem}"]
            if opts:
                lines += [f"(A) {opts[0]}    (B) {opts[1]}", f"(C) {opts[2]}    (D) {opts[3]}"]
        blocks.append("\n".join(line.rstrip() for line in lines))
    return header + "\n\n".join(blocks) + "\n" + footer


STYLES = ["plain", "q_paren", "numeric_labels", "one_line", "dotted"]
HEADERS = ["", "Forwarded from NEET 2026 papers\nREAL PAPER 100% CONFIRMED\n\n", "leaked just now, share fast\n\n", ""]
FOOTERS = ["", "\nJoin @examleaks_demo for the full paper\n", "\nmore pages coming, DM for price\n", ""]


def add(kind: str, verdict: str, source, named: bool, text: str | None = None, reader: dict | None = None, note: str = ""):
    """source: (stage, copy_no) the leak really came from, or None for a fake. named: should that copy be named."""
    leaks.append({"kind": kind, "note": note, "text": text, "reader": reader,
                  "source": list(source) if source else None,
                  "expect": {"verdict": verdict, "copy": list(source) if named and source else None}})


def agrees(verdict: str, source, intact, values=True, order=True, traps=True) -> bool:
    """Does the exact maths, given a perfect read of the clues this leak really carries, give the declared answer?

    A leak goes into the set only if the answer declared for its kind and the brief's maths agree, so no
    expected answer rests on a hand count alone. `intact` holds the questions whose clues survive in the leak.
    """
    clues = fp.clues_from_rendered(intact, values=values, order=order, traps=traps)
    decoded = fp.decode(clues, KEY, 1, bank, 50, 5000)
    if verdict in ("traced", "strong_lead"):
        return decoded.verdict == verdict and (decoded.stage, decoded.copy_no) == tuple(source)
    return decoded.verdict == verdict and decoded.copy_no is None


def until(build):
    """Draw leaks until one is unambiguous. build() returns True once it has added a leak."""
    for _ in range(200):
        if build():
            return
    raise SystemExit("could not build an unambiguous leak")


def reader_json(items, legible=True, stems=None, stems_en=None, options_en=False):
    out = []
    for i, item in enumerate(items):
        out.append({"number": item["number"], "legible": item.get("legible", legible),
                    "stem": stems[i] if stems else item["stem"], "options": item["options"],
                    "stem_en": stems_en[i] if stems_en else None,
                    "options_en": item["options"] if options_en and item["options"] else None})
    return {"questions": out}


DEVANAGARI = str.maketrans("0123456789", "०१२३४५६७८९")

# 1. typed translator leaks, values and options kept: far past the traced bar
for i in range(9):
    def build(i=i):
        n, copy = copy_of("translation")
        part = any_run(copy, rng.choice([9, 12, 14, 14, 18, 24, 30]))
        if not agrees("traced", ("translation", n), part):
            return False
        add("translator_typed", "traced", ("translation", n), True,
            text=write([shown(q) for q in part], STYLES[i % 5], renumber=i % 2 == 1, header=HEADERS[i % 4], footer=FOOTERS[(i + 1) % 4]),
            note=f"{len(part)} questions")
        return True
    until(build)

# 2. typed translator leaks, values only (no options). 50 x (1/8)^n: traced from 9, strong lead from 6, nothing under 6
for i, count in enumerate([12, 14, 15, 6, 7, 6, 3, 4, 4]):
    def build(i=i, count=count):
        n, copy = copy_of("translation")
        part = numeric_run(copy, count)
        verdict = "traced" if count >= 9 else "strong_lead" if count >= 6 else "inconclusive"
        if not agrees(verdict, ("translation", n), part, order=False):
            return False
        add("translator_values_only", verdict, ("translation", n), verdict != "inconclusive",
            text=write([shown(q, options=False) for q in part], STYLES[(i * 2) % 5], renumber=i % 3 == 0), note=f"{count} numeric")
        return True
    until(build)

# 3. typed printed-copy leaks, options kept. 5000 x (1/24)^n: traced from 8, strong lead at 5 or 6
for i, count in enumerate([14, 10, 12, 14, 9, 20, 5, 6, 5]):
    def build(i=i, count=count):
        n, copy = copy_of("print")
        if i in (2, 4):
            part = biology_run(copy, count)                       # no numbers at all: only option order to go on
        elif count <= 6:
            part = numeric_run(copy, count)
        else:
            part = [q for q in any_run(copy, count + 4) if not q.pinned][:count]
        verdict = "traced" if count >= 8 else "strong_lead"
        if not agrees(verdict, ("print", n), part):
            return False
        add("print_typed", verdict, ("print", n), True,
            text=write([shown(q) for q in part], STYLES[(i + 1) % 5], renumber=i % 2 == 0, header=HEADERS[(i + 1) % 4]),
            note=f"{count} questions")
        return True
    until(build)

# 4. printed-copy leaks with no usable option order: nobody can be named
for i in range(6):
    n, copy = copy_of("print")
    part = any_run(copy, rng.choice([10, 14, 16]))
    if i < 3:
        items = [shown(q, options=False) for q in part]
    else:
        items = []
        for q in part:
            opts = list(q.options)
            while opts == list(q.options) and not q.pinned:
                rng.shuffle(opts)
            items.append(shown(q, opts=opts))
    add("print_no_order", "inconclusive", ("print", n), False, text=write(items, STYLES[i % 5]),
        note="options left out" if i < 3 else "options reshuffled by the leaker")

# 5. translated leaks: a translator's paper in another language, read by the (mocked) photo reader
for i in range(9):
    def build(i=i):
        n, copy = copy_of("translation")
        part = numeric_run(copy, rng.choice([13, 14, 15]))
        with_options = i % 3 != 2
        if not agrees("traced", ("translation", n), part, order=with_options):
            return False
        items = [shown(q, options=with_options) for q in part]
        for item in items:
            item["options"] = [o.translate(DEVANAGARI) for o in item["options"]]
        hindi = [f"प्रश्न {q.number}. इस प्रश्न का पाठ हिंदी में है और इसमें दी गई संख्याएँ वही हैं।".translate(DEVANAGARI) for q in part]
        english = [retell(q.stem, seed=1000 + i) for q in part]
        data = reader_json(items, stems=hindi, stems_en=english)
        for item, q in zip(data["questions"], part):
            item["options_en"] = list(q.options) if with_options else None
        add("translated", "traced", ("translation", n), True, reader=data,
            note=f"{len(part)} numeric, {'with' if with_options else 'no'} options")
        return True
    until(build)

# 6. retold in English and typed, values kept, no options
for i in range(6):
    def build(i=i):
        n, copy = copy_of("translation")
        part = numeric_run(copy, rng.choice([12, 13, 14]))
        if not agrees("traced", ("translation", n), part, order=False):
            return False
        items = [shown(q, options=False, stem=retell(q.stem, seed=2000 + i)) for q in part]
        add("retold_typed", "traced", ("translation", n), True, text=write(items, STYLES[i % 5], renumber=True, header=HEADERS[i % 4]),
            note=f"{len(part)} numeric")
        return True
    until(build)

# 7. numbers removed. With no option order either, nobody can be named. Biology with its options still can be.
for i in range(9):
    def build(i=i):
        n, copy = copy_of("translation")
        if i < 3:
            part = numeric_run(copy, rng.choice([10, 14]))
            items = [shown(q, options=i == 1, stem=strip_numbers(q.stem), opts=[strip_numbers(o) for o in q.options]) for q in part]
            add("numbers_removed", "inconclusive", ("translation", n), False, text=write(items, "plain"),
                note="physics or chemistry, numbers stripped")
        elif i < 6:
            part = biology_run(copy, rng.choice([10, 12]), want_trap=True)
            if not agrees("inconclusive", ("translation", n), part, values=False, order=False):
                return False
            add("numbers_removed", "inconclusive", ("translation", n), False, text=write([shown(q, options=False) for q in part], STYLES[i % 5]),
                note="biology with a trap, no options: traps alone never reach a bar")
        else:
            part = biology_run(copy, rng.choice([10, 12, 14]))
            if not agrees("traced", ("translation", n), part):
                return False
            add("numbers_removed", "traced", ("translation", n), True, text=write([shown(q) for q in part], STYLES[i % 5]),
                note="biology with options: no numbers, but the option order is intact")
        return True
    until(build)

# 8. fake papers
clear, topical = FAKE_PAPER + MORE_FAKE, FAKE_TOPICAL + MORE_TOPICAL
for i in range(12):
    count = rng.choice([10, 12, 14, 16])
    picked = rng.sample(clear, count)
    if i % 4 == 1:
        picked = picked[:count - 3] + rng.sample(topical, 3)       # a real fake covers the same syllabus
        rng.shuffle(picked)
    items = [{"number": j + 1, "stem": stem, "options": list(opts) if i % 4 != 2 else []} for j, (stem, opts) in enumerate(picked)]
    text = write(items, STYLES[i % 5], header=HEADERS[i % 4], footer=FOOTERS[i % 4])
    if i % 4 == 3:
        text = typos(text, seed=300 + i)
    add("fake", "not_our_paper", None, False, text=text,
        note=["clear fake", "fake with 3 questions on topics the bank also covers", "fake without options", "fake with typing slips"][i % 4])

# 9. garbled: real leaks damaged past use. Unreadable, never "not our paper", never a copy
for i in range(9):
    stage = "translation" if i % 2 == 0 else "print"
    n, copy = copy_of(stage)
    part = any_run(copy, 14)
    rate = [0.35, 0.45, 0.6][i % 3]
    if i < 6:
        add("garbled", "unreadable", (stage, n), False, text=garble(write([shown(q) for q in part], "plain"), rate, seed=400 + i),
            note=f"typed text, damage {rate}")
    else:
        items = [{"number": q.number, "legible": False, "stem": garble(q.stem, rate, seed=500 + q.number),
                  "options": [garble(o, rate, seed=600 + q.number + j) for j, o in enumerate(q.options)]} for q in part]
        add("garbled", "unreadable", (stage, n), False, reader=reader_json(items), note=f"photo reader output, damage {rate}")

# 10. typed with typing slips in the words only: every number and label is intact
for i in range(6):
    def build(i=i):
        stage = "translation" if i % 2 == 0 else "print"
        n, copy = copy_of(stage)
        part = numeric_run(copy, 14) if stage == "translation" else [q for q in any_run(copy, 18) if not q.pinned][:14]
        if not agrees("traced", (stage, n), part):
            return False
        add("typos", "traced", (stage, n), True, text=typos(write([shown(q) for q in part], STYLES[i % 5]), seed=700 + i),
            note="14 questions with typing slips")
        return True
    until(build)

# 11. photo reader output in English with a few misreads, as a phone photo gives
for i in range(6):
    def build(i=i):
        stage = "print" if i < 3 else "translation"
        n, copy = copy_of(stage)
        part = copy[:14]                                              # page 1
        items = [shown(q) for q in part]
        spoiled = rng.sample(range(14), 2)
        if not agrees("traced", (stage, n), [q for j, q in enumerate(part) if j not in spoiled]):
            return False
        for j in spoiled:
            if stage == "print":
                a, b = rng.sample(range(4), 2)
                items[j]["options"][a], items[j]["options"][b] = items[j]["options"][b], items[j]["options"][a]
            else:
                items[j]["stem"] = "".join(str((int(ch) + 3) % 10) if ch in "0123456789" else ch for ch in items[j]["stem"])
            items[j]["legible"] = False
        add("photo_mock", "traced", (stage, n), True, reader=reader_json(items), note="page 1, two questions misread and flagged")
        return True
    until(build)

# every third leak of each kind is set aside
seen = {}
for leak in leaks:
    seen[leak["kind"]] = seen.get(leak["kind"], 0) + 1
    leak["held"] = seen[leak["kind"]] % 3 == 0
for i, leak in enumerate(leaks, start=1):
    leak["id"] = i

body = json.dumps({"format": "canary-score-set-1", "key_note": "made with score.SCORE_KEY, a public key used for nothing else",
                   "leaks": leaks}, ensure_ascii=False, indent=1)
OUT.write_text(body, encoding="utf-8")
held = sum(leak["held"] for leak in leaks)
print(f"Wrote {OUT.relative_to(ROOT)}: {len(leaks)} leaks, {len(leaks) - held} to read and {held} set aside.")
print(f"sha256 {hashlib.sha256(body.encode()).hexdigest()}")
for kind in dict.fromkeys(leak["kind"] for leak in leaks):
    print(f"  {kind:24} {sum(leak['kind'] == kind for leak in leaks)}")
