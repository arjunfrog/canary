import json

import pytest

from canary import cli, score

FROZEN = "a4ffe1b1f7bb5af6c3d75091600f83f7b9f367def67f0426f135e13d324ea618"
KINDS = {"translator_typed", "translator_values_only", "print_typed", "print_no_order", "translated", "retold_typed",
         "numbers_removed", "fake", "garbled", "typos", "photo_mock"}


def test_the_score_set_is_the_frozen_one():
    leaks, digest = score.load_set()
    assert digest == FROZEN, "the score set changed. Leaks and expected answers must never be edited"
    assert len(leaks) == 90 and {x["kind"] for x in leaks} == KINDS


def test_a_third_of_every_kind_is_set_aside():
    leaks, _ = score.load_set()
    assert sum(x["held"] for x in leaks) == 30
    for kind in KINDS:
        rows = [x for x in leaks if x["kind"] == kind]
        assert sum(x["held"] for x in rows) * 3 == len(rows)


def test_every_leak_has_a_known_answer_made_from_a_known_copy():
    leaks, _ = score.load_set()
    for leak in leaks:
        verdict, copy = leak["expect"]["verdict"], leak["expect"]["copy"]
        assert verdict in ("traced", "strong_lead", "inconclusive", "not_our_paper", "unreadable")
        assert (copy is not None) == (verdict in ("traced", "strong_lead"))
        assert (leak["source"] is None) == (leak["kind"] == "fake")
        if copy is not None:
            assert copy == leak["source"]
        assert (leak["text"] is None) != (leak["reader"] is None)


def test_set_aside_leaks_are_never_printed(capsys):
    leaks, _ = score.load_set()
    held = next(x for x in leaks if x["held"])
    with pytest.raises(PermissionError):
        score.show(held["id"])
    with pytest.raises(SystemExit):
        cli.main(["score", "--show", str(held["id"])])
    lines = []
    outcomes = [score.Outcome(x["id"], x["kind"], x["held"], ("traced", None), ("inconclusive", None), False, False, x["note"])
                for x in leaks]
    score.report(outcomes, "0" * 64, say=lines.append)
    printed = "\n".join(lines)
    for leak in leaks:
        if leak["held"]:
            assert f"leak {leak['id']:>2} " not in printed
    assert "set-aside leaks:   0/30" in printed and "leaks I may read:  0/60" in printed


def test_naming_a_wrong_copy_fails_the_whole_run():
    right = score.Outcome(1, "print_typed", False, ("traced", ("print", 7)), ("traced", ("print", 7)), True, False)
    wrong = score.Outcome(2, "fake", True, ("not_our_paper", None), ("strong_lead", ("print", 9)), False, True)
    lines = []
    assert score.report([right] * 9, "0" * 64, say=lines.append)
    assert not score.report([right] * 9 + [wrong], "0" * 64, say=lines.append)
    assert "RUN FAILED" in lines[-1]


def test_a_leak_from_the_set_is_scored_through_the_real_analysis():
    leaks, _ = score.load_set()
    leak = next(x for x in leaks if not x["held"] and x["kind"] == "translator_typed")
    verdict, copy = score.answer(leak)
    assert verdict in ("traced", "strong_lead", "inconclusive", "not_our_paper", "unreadable")
    assert copy is None or copy[0] in ("translation", "print")
    assert score.show(leak["id"]) == leak["text"]


def test_score_command_runs_and_no_wrong_copy_is_named(capsys):
    code = cli.main(["score"])
    out = capsys.readouterr().out
    assert "leaks I may read:" in out and "set-aside leaks:" in out
    assert code == 0 and "No wrong copy was named." in out
