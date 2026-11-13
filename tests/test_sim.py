import json

import numpy as np
import pytest

from canary import cli, config, sim
from canary import fingerprint as fp


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return sim.run_sim(tmp_path_factory.mktemp("sim") / "limits.json", trials=6000, seed=7)


def point(result, key, k):
    scenario = next(s for s in result["scenarios"] if s["key"] == key)
    return next(p for p in scenario["points"] if p["k"] == k)


def test_it_uses_the_real_bars_and_chance_rates(result):
    assert result["bars"] == {"traced": fp.TRACED_BAR, "strong_lead": fp.STRONG_LEAD_BAR}
    assert point(result, "translator_typed", 10)["traced_needs"] == 10        # 50 x (1/8)^9 clears the bar only with a miss-free 10
    assert point(result, "translator_typed", 14)["lead_needs"] == 9
    assert point(result, "print_photo", 14)["traced_needs"] == 10
    assert sim.threshold([fp.CHANCE_VALUE] * 9, 50, fp.TRACED_BAR) == 9 and sim.threshold([fp.CHANCE_VALUE] * 5, 50, 1e-3) is None


def test_the_seven_scenarios_are_all_there(result):
    assert [s["key"] for s in result["scenarios"]] == [
        "translator_typed", "translator_retold", "translator_photo", "translator_no_numbers", "translators_merged",
        "print_photo", "print_reshuffled"]
    assert result["ks"] == [3, 5, 8, 10, 14, 20, 30]
    assert all(len(s["points"]) == 7 and s["sentence"] for s in result["scenarios"])
    assert result["rates_source"] == "assumed"


def test_the_headline_numbers_match_the_research_run(result):
    assert point(result, "translator_typed", 14)["traced_right"] == pytest.approx(0.999, abs=0.004)
    assert point(result, "translator_retold", 14)["traced_right"] == pytest.approx(0.979, abs=0.012)
    assert point(result, "print_photo", 14)["traced_right"] == pytest.approx(0.994, abs=0.006)
    assert point(result, "translators_merged", 14)["traced_right"] == pytest.approx(0.03, abs=0.015)
    assert point(result, "translators_merged", 30)["traced_right"] == pytest.approx(0.83, abs=0.04)
    assert point(result, "translator_typed", 5)["lead_right"] == 0


def test_failures_are_shown_as_plainly_as_successes(result):
    for key in ("translator_no_numbers", "print_reshuffled"):
        scenario = next(s for s in result["scenarios"] if s["key"] == key)
        assert all(p["lead_right"] == p["traced_right"] == p["lead_wrong"] == p["traced_wrong"] == 0 for p in scenario["points"])
        assert "cannot name anyone" in scenario["sentence"] and "Not enough to name anyone yet" in scenario["sentence"]
    merged = next(s for s in result["scenarios"] if s["key"] == "translators_merged")
    assert merged["sentence"].startswith("Weak.")


def test_a_wrong_copy_is_almost_never_named_and_never_traced(result):
    for scenario in result["scenarios"]:
        for p in scenario["points"]:
            assert p["traced_wrong"] == 0
            assert p["lead_wrong"] <= 0.002


def test_the_best_innocent_score_is_drawn_from_the_exact_distribution():
    rng = np.random.default_rng(3)
    chances = [1 / 8] * 10
    exact = sim.best_of_others(rng, chances, 49, 40000)
    brute = np.random.default_rng(4).binomial(10, 1 / 8, (40000, 49)).max(axis=1)
    assert abs(exact.mean() - brute.mean()) < 0.03
    assert sim.score_pmf([0.5, 0.5]) == pytest.approx([0.25, 0.5, 0.25])


def test_measured_rates_replace_the_assumed_ones(canary_home):
    config.ensure_home()
    assert sim.load_rates() == (sim.DEFAULT_RATES, "assumed")
    (config.home() / "measured.json").write_text(json.dumps({"photo_order": 0.3, "photo_value": 0.2}))
    rates, source = sim.load_rates()
    assert (rates["photo_order"], rates["typed_value"], source) == (0.3, 0.02, "partly measured")
    result = sim.run_sim(trials=2000)
    assert result["rates_source"] == "partly measured"
    assert point(result, "print_photo", 10)["traced_right"] < 0.5          # worse reads, fewer traces
    (config.home() / "measured.json").write_text("not json")
    assert sim.load_rates()[1] == "assumed"


def test_sim_command_writes_limits_json(canary_home, capsys):
    assert sim.load_limits() is None
    assert cli.main(["sim", "--trials", "1500"]) == 0
    out = capsys.readouterr().out
    assert "limits.json" in out and "Misread rates are assumed" in out
    saved = sim.load_limits()
    assert saved["trials"] == 1500 and len(saved["scenarios"]) == 7
    sim.limits_path().write_text("{broken")
    assert sim.load_limits() is None
