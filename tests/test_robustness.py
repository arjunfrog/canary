"""Randomised checks on the two outcomes that must never happen: a wrong copy named, and a real paper called a fake.

These grew out of probing done after the scored rounds (see SCORES.md). They use their own random leaks,
not the score sets, so they neither read nor depend on the set-aside leaks.
"""
import random
import re

import pytest

from canary import analyze, score
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import (FAKE_PAPER, FAKE_TOPICAL, MORE_FAKE, MORE_TOPICAL, SAME_FRAME, garble, regional, retell, retell_hard,
                            strip_numbers, typos)

KEY = score.SCORE_KEY


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def block(questions, change=lambda s: s, options=True, shuffle=None):
    out = []
    for i, q in enumerate(questions):
        shown = list(q.options)
        if shuffle is not None:
            shuffle.shuffle(shown)
        out.append(f"{i + 1}. {change(q.stem)}" + (f"\n(A) {shown[0]}    (B) {shown[1]}\n(C) {shown[2]}    (D) {shown[3]}" if options else ""))
    return "\n\n".join(out) + "\n"


def a_copy(rng, bank, stage=None):
    stage = stage or rng.choice(["translation", "print"])
    n = rng.randint(1, 50 if stage == "translation" else 5000)
    render = fp.render_translator_copy if stage == "translation" else fp.render_print_copy
    return (stage, n), render(KEY, 1, n, bank)


def named(result):
    return (result.stage, result.copy_no) if result.copy_no is not None else None


def test_no_change_to_a_real_leak_makes_the_tool_name_another_copy(bank):
    rng = random.Random(1)
    changes = {
        "plain": lambda part, i: block(part),
        "typos": lambda part, i: typos(block(part), seed=i, rate=0.3),
        "damage": lambda part, i: garble(block(part), rng.choice([0.03, 0.08, 0.15, 0.25]), seed=i),
        "retold": lambda part, i: block(part, lambda s: retell(s, i), options=i % 2 == 0),
        "retold loosely": lambda part, i: block(part, lambda s: retell_hard(s, i), options=i % 2 == 0),
        "numbers removed": lambda part, i: strip_numbers(block(part, options=i % 2 == 0)),
        "typed in Hindi": lambda part, i: block(part, lambda s: regional(s, i)),
        "options reshuffled": lambda part, i: block(part, shuffle=rng),
        "no options": lambda part, i: block(part, options=False),
    }
    for i in range(180):
        source, copy = a_copy(rng, bank)
        count = rng.randint(3, 20)
        start = rng.randint(0, len(copy) - count)
        how = list(changes)[i % len(changes)]
        result = analyze.analyse_text(changes[how](copy[start:start + count], i), KEY, bank=bank)
        assert named(result) in (None, source), f"{how}: named {named(result)} for a leak from {source}"


def test_merged_copies_never_point_at_someone_who_was_not_involved(bank):
    rng = random.Random(2)
    for i in range(80):
        stage = rng.choice(["translation", "print"])
        involved = [a_copy(rng, bank, stage) for _ in range(rng.choice([2, 3]))]
        count, start = rng.randint(8, 30), rng.randint(0, 150)
        part = [rng.choice(involved)[1][start + j] for j in range(count)]
        result = analyze.analyse_text(block(part), KEY, bank=bank)
        assert named(result) in [None] + [source for source, _ in involved]


def test_fakes_and_invented_numbers_never_name_anyone(bank):
    rng = random.Random(3)
    numbers = [2, 3, 4, 5, 6, 8, 10, 12, 20, 25, 30, 40, 50, 60, 100, 200]
    fakes = FAKE_PAPER + MORE_FAKE + FAKE_TOPICAL + MORE_TOPICAL + SAME_FRAME
    for i in range(120):
        out = []
        for j, (stem, options) in enumerate(rng.sample(fakes, rng.randint(6, 18))):
            if rng.random() < 0.5:
                stem = re.sub(r"\d+(?:\.\d+)?", lambda m: str(rng.choice(numbers)), stem)
            out.append(f"{j + 1}. {stem}\n(A) {options[0]}    (B) {options[1]}\n(C) {options[2]}    (D) {options[3]}")
        result = analyze.analyse_text("\n\n".join(out) + "\n", KEY, bank=bank)
        assert named(result) is None and result.verdict not in ("traced", "strong_lead")
    for i in range(60):                                           # the bank's own stems with numbers the leaker made up
        _, copy = a_copy(rng, bank, "translation")
        out = []
        for j, q in enumerate(rng.sample([q for q in copy if q.set_no], 14)):
            stem = re.sub(r"\d+(?:\.\d+)?", lambda m: str(rng.choice(numbers)), q.stem)
            unit = q.options[0].split(" ", 1)[1] if " " in q.options[0] else ""
            options = [f"{rng.choice(numbers)} {unit}".strip() for _ in range(4)]
            out.append(f"{j + 1}. {stem}\n(A) {options[0]}    (B) {options[1]}\n(C) {options[2]}    (D) {options[3]}")
        assert named(analyze.analyse_text("\n\n".join(out) + "\n", KEY, bank=bank)) is None


def test_a_damaged_real_paper_is_never_called_not_our_paper(bank):
    rng = random.Random(5)
    for i in range(200):
        source, copy = a_copy(rng, bank)
        count = rng.randint(3, 20)
        start = rng.randint(0, len(copy) - count)
        rate = rng.choice([0.03, 0.08, 0.15, 0.25, 0.35, 0.5, 0.7, 0.9])
        result = analyze.analyse_text(garble(block(copy[start:start + count]), rate, seed=i), KEY, bank=bank)
        assert result.verdict != "not_our_paper", f"damage {rate}, {count} questions from {source}"
        assert named(result) in (None, source)


def test_one_swapped_subject_is_a_different_question_but_damage_and_retelling_are_not(bank):
    matcher = analyze.matcher_for(bank)
    ours = bank.by_id[next(q.id for q in bank.paper if q.stem == "Morphine is obtained from")]
    ask = lambda stem: matcher.different_subject(ours, analyze.ReadQuestion(1, stem))
    assert ask("Quinine is obtained from") and ask("Litmus solution is obtained from")
    assert not ask("Morphine is obtained from") and not ask("Morphnie is obtained from")        # a typing slip
    assert not ask("Mor#hine is ob1tained frm") and not ask("zq#rt kx obtlained wqm")           # damage
    assert not ask("From what is morphine obtained?")                                           # reworded
