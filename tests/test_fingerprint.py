import pytest

from canary import fingerprint as fp

KEY = bytes.fromhex("11" * 32)


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
