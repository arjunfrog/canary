import time

import pytest

from canary import fingerprint as fp
from canary.bank import load_bank
from canary.fingerprint import Clue

KEY = bytes.fromhex("11" * 32)
N_T, N_P = 50, 5000


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def decode(clues, bank):
    return fp.decode(clues, KEY, 1, bank, N_T, N_P)


def value_clues(bank, copy_no, count, misread=0):
    """Clean value clues from a translator's copy. The first `misread` point at a wrong decoy set."""
    numeric = [r for r in fp.render_translator_copy(KEY, 1, copy_no, bank) if r.set_no is not None][:count]
    clues = [Clue(r.question_id, "value", r.set_no) for r in numeric]
    for i in range(misread):
        clues[i] = Clue(clues[i].question_id, "value", clues[i].value % 8 + 1)
    return clues


def test_pick_is_stable_and_in_range():
    a = fp.pick(KEY, 1, "translation", 23, "P001", "values", 8)
    assert a == fp.pick(KEY, 1, "translation", 23, "P001", "values", 8)
    assert 0 <= a < 8


def test_pick_changes_with_key_copy_and_purpose():
    picks = lambda **kw: [fp.pick(kw.get("key", KEY), 1, "translation", kw.get("copy", 23), f"P{i:03d}",
                                  kw.get("purpose", "values"), 24) for i in range(1, 41)]
    base = picks()
    assert base != picks(key=bytes.fromhex("22" * 32))
    assert base != picks(copy=24)
    assert base != picks(purpose="order")


def test_tail_matches_hand_arithmetic():
    assert fp.tail([1 / 8] * 9, 9) == pytest.approx((1 / 8) ** 9)
    assert fp.tail([0.5, 0.5], 1) == pytest.approx(0.75)
    assert fp.tail([0.2, 0.3], 0) == pytest.approx(1.0)


@pytest.mark.parametrize("clues, verdict", [(9, "traced"), (8, "strong_lead"), (6, "strong_lead"), (5, "inconclusive")])
def test_bars_for_clean_value_clues_among_50_translators(clues, verdict):
    expected = fp.expected_false_matches(50, [fp.CHANCE_VALUE] * clues, clues)
    assert fp.verdict_for(expected) == verdict


def test_fourteen_clean_order_clues_trace_a_printed_copy():
    assert fp.verdict_for(fp.expected_false_matches(5000, [fp.CHANCE_ORDER] * 14, 14)) == "traced"


# ---- making copies

def test_same_inputs_give_the_same_copy_and_different_copies_differ(bank):
    assert fp.render_translator_copy(KEY, 1, 7, bank) == fp.render_translator_copy(KEY, 1, 7, bank)
    assert fp.render_print_copy(KEY, 1, 12, bank) == fp.render_print_copy(KEY, 1, 12, bank)
    assert fp.render_translator_copy(KEY, 1, 7, bank) != fp.render_translator_copy(KEY, 1, 8, bank)
    assert fp.render_print_copy(KEY, 1, 12, bank) != fp.render_print_copy(KEY, 1, 13, bank)
    assert fp.render_print_copy(KEY, 1, 12, bank) != fp.render_print_copy(bytes.fromhex("22" * 32), 1, 12, bank)


def test_no_translator_copy_contains_real_values(bank):
    real_stems = {q.real.stem for q in bank.questions if q.kind == "numeric"}
    for copy_no in range(1, N_T + 1):
        copy = fp.render_translator_copy(KEY, 1, copy_no, bank)
        assert all(1 <= r.set_no <= 8 for r in copy if r.set_no is not None)
        assert not real_stems & {r.stem for r in copy}


def test_translator_copy_has_six_traps_inside_biology(bank):
    copy = fp.render_translator_copy(KEY, 1, 23, bank)
    traps = [r for r in copy if r.is_trap]
    assert len(copy) == 186 and len(traps) == 6
    first_biology = next(r.number for r in copy if r.subject == "biology")
    assert all(r.number >= first_biology for r in traps)
    assert [r.number for r in copy] == list(range(1, 187))
    held = [frozenset(r.question_id for r in fp.render_translator_copy(KEY, 1, n, bank) if r.is_trap) for n in range(1, 11)]
    assert len(set(held)) > 1


def test_print_copy_has_real_values_no_traps_and_the_same_questions(bank):
    a, b = fp.render_print_copy(KEY, 1, 12, bank), fp.render_print_copy(KEY, 1, 4821, bank)
    assert [r.question_id for r in a] == [q.id for q in bank.paper] == [r.question_id for r in b]
    assert not any(r.is_trap for r in a) and all(r.set_no == 0 for r in a if r.set_no is not None)
    assert [r.stem for r in a] == [r.stem for r in b]
    assert [r.options for r in a] != [r.options for r in b]
    assert all(sorted(r.options) == sorted(s.options) for r, s in zip(a, b))


def test_pinned_questions_keep_their_order_and_give_no_order_clue(bank):
    pinned = {q.id for q in bank.questions if q.pinned_order}
    assert pinned
    for copy_no in (1, 2, 3):
        copy = fp.render_print_copy(KEY, 1, copy_no, bank)
        assert all(r.order == (0, 1, 2, 3) for r in copy if r.question_id in pinned)
        assert not pinned & {c.question_id for c in fp.clues_from_rendered(copy) if c.kind == "order"}
    question = next(q for q in bank.paper if q.pinned_order)
    assert fp.order_chance(question) is None
    result = decode([Clue(question.id, "order", (0, 1, 2, 3))], bank)
    assert result.clues == 0 and result.verdict == "inconclusive"


def test_a_fixed_last_option_stays_last():
    class Q:
        id, kind, pinned_order = "X1", "fixed", False
        options = ("alpha", "all of the above", "beta", "gamma")
    assert fp.fixed_last_index(Q) == 1 and fp.order_chance(Q) == fp.CHANCE_ORDER_FIXED_LAST
    orders = {fp.order_for(KEY, 1, "print", n, Q) for n in range(1, 200)}
    assert len(orders) == 6 and all(o[3] == 1 for o in orders)


# ---- decoding

def test_nine_clean_value_clues_are_traced_to_the_right_translator(bank):
    result = decode(value_clues(bank, 23, 9), bank)
    assert (result.stage, result.verdict, result.copy_no, result.score) == ("translation", "traced", 23, 9)
    assert result.expected_false_matches == pytest.approx(50 / 8 ** 9)


def test_six_clean_value_clues_are_a_strong_lead(bank):
    result = decode(value_clues(bank, 23, 6), bank)
    assert (result.stage, result.verdict, result.copy_no) == ("translation", "strong_lead", 23)


def test_four_value_clues_are_inconclusive_and_name_no_copy(bank):
    result = decode(value_clues(bank, 23, 4), bank)
    assert (result.verdict, result.copy_no) == ("inconclusive", None)
    assert result.matched == []


def test_fourteen_value_clues_with_two_misread_still_find_the_translator(bank):
    result = decode(value_clues(bank, 23, 14, misread=2), bank)
    assert result.copy_no == 23 and result.score == 12 and result.verdict == "traced"


def test_five_value_clues_plus_three_traps_are_a_strong_lead(bank):
    traps = [r for r in fp.render_translator_copy(KEY, 1, 23, bank) if r.is_trap][:3]
    result = decode(value_clues(bank, 23, 5) + [Clue(r.question_id, "trap") for r in traps], bank)
    assert (result.stage, result.verdict, result.copy_no, result.score) == ("translation", "strong_lead", 23, 8)


def test_fourteen_clean_order_clues_with_real_values_trace_a_printed_copy(bank):
    copy = fp.render_print_copy(KEY, 1, 4821, bank)[:14]
    clues = fp.clues_from_rendered(copy)
    assert sum(c.kind == "order" for c in clues) == 14 and all(c.value == 0 for c in clues if c.kind == "value")
    result = decode(clues, bank)
    assert (result.stage, result.verdict, result.copy_no, result.score, result.clues) == ("print", "traced", 4821, 14, 14)
    assert result.candidates == N_P


def test_order_clues_alone_search_both_stages(bank):
    copy = fp.render_print_copy(KEY, 1, 77, bank)[100:114]
    result = decode(fp.clues_from_rendered(copy, values=False), bank)
    assert result.candidates == N_T + N_P
    assert (result.stage, result.verdict, result.copy_no) == ("print", "traced", 77)


def test_a_tie_for_best_names_nobody(bank):
    question = bank.paper[0]
    sets = fp.codebook(KEY, 1, bank, N_T, N_P).value_sets(question.id)
    shared = int(sets[0])
    assert (sets == shared).sum() > 1
    result = decode([Clue(question.id, "value", shared)], bank)
    assert result.tie and result.copy_no is None and result.verdict == "inconclusive"


def test_trap_chance_is_the_share_of_translators_holding_it(bank):
    book = fp.codebook(KEY, 1, bank, N_T, N_P)
    ids, holds = book.trap_table()
    assert holds.shape == (N_T, 24) and (holds.sum(axis=1) == 6).all()
    for copy_no in (1, 23, 50):
        held = {r.question_id for r in fp.render_translator_copy(KEY, 1, copy_no, bank) if r.is_trap}
        assert held == {ids[j] for j in range(24) if holds[copy_no - 1, j]}
    assert sum(book.trap_share(t) for t in ids) == pytest.approx(6.0)


def test_codebook_agrees_with_the_rendered_copies(bank):
    book = fp.codebook(KEY, 1, bank, N_T, N_P)
    for stage, render, copy_no in (("translation", fp.render_translator_copy, 31), ("print", fp.render_print_copy, 2718)):
        for r in render(KEY, 1, copy_no, bank)[:60]:
            codes = book.orders(stage, r.question_id)
            if codes is not None:
                assert codes[copy_no - 1] == fp._code(r.order)
            if stage == "translation" and r.set_no is not None:
                assert book.value_sets(r.question_id)[copy_no - 1] == r.set_no


def test_funnel_narrows_to_one_and_ends_at_the_decoded_risk(bank):
    clues = fp.clues_from_rendered(fp.render_print_copy(KEY, 1, 4821, bank)[:14])
    steps = fp.funnel(clues, KEY, 1, bank, N_T, N_P)
    assert len(steps) == 14 and steps[0]["candidates"] == N_P
    assert steps[0]["remaining"] < N_P and steps[-1]["remaining"] == 1 and steps[-1]["alive"] == [4820]
    assert steps[-1]["expected_false_matches"] == pytest.approx(decode(clues, bank).expected_false_matches)
    assert all(a["expected_false_matches"] >= b["expected_false_matches"] for a, b in zip(steps, steps[1:]))


def test_decoding_against_5000_copies_takes_under_two_seconds(bank):
    key = bytes.fromhex("5a" * 32)                         # a key no other test has warmed up
    clues = fp.clues_from_rendered(fp.render_print_copy(key, 1, 4821, bank)[:40])
    started = time.perf_counter()
    result = fp.decode(clues, key, 1, bank, N_T, N_P)
    assert time.perf_counter() - started < 2.0
    assert result.copy_no == 4821


def test_decode_command_prints_the_copy_and_funnel(bank, canary_home, tmp_path, monkeypatch, capsys):
    from canary import cli, config
    from canary.samples import leak_text
    from canary.vault import Vault
    config.ensure_home()
    vault = Vault.create(config.vault_path(), "a long test passphrase")
    key = bytes.fromhex(vault.get("fingerprint_key"))
    leak = tmp_path / "leak.txt"
    leak.write_text(leak_text(fp.render_translator_copy(key, 1, 23, bank)[:14]), encoding="utf-8")
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "a long test passphrase")
    assert cli.main(["decode", "--text", str(leak)]) == 0
    out = capsys.readouterr().out
    assert "translation" in out and "traced" in out and "copy:     23" in out and "funnel" in out
    assert vault.get("fingerprint_key") not in out
