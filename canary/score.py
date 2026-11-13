"""The scored test set: `python -m canary score`.

canary/data/score_set.json holds leaks made from known copies, each with the answer it should get. The
score is the share of leaks that get the right verdict and the right copy. Naming a wrong copy fails the
whole run, whatever the share.

A third of the leaks are set aside. They are scored, but this module never prints anything about any one
of them: not its text, not its kind, not which ones failed. That keeps them unread.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from . import analyze, config
from .bank import load_bank

SCORE_KEY = bytes.fromhex("c0a1" * 16)          # public, and used only to make and score this set
SCORE_SET = config.PACKAGE_DIR / "data" / "score_set.json"
SCORE_SET_2 = config.PACKAGE_DIR / "data" / "score_set_2.json"      # harder leaks, added once the first set was saturated


@dataclass
class Outcome:
    id: int
    kind: str
    held: bool
    expected: tuple          # (verdict, copy or None)
    got: tuple
    right: bool
    wrong_copy: bool         # a copy was named that the leak did not come from
    note: str = ""
    set: int = 1


def load_set(path: Path | None = None) -> tuple[list[dict], str]:
    """Every leak and one digest for the files they came from. With no path: both frozen sets, in order."""
    leaks, digests = [], []
    for part, source in enumerate([path] if path else [SCORE_SET, SCORE_SET_2], start=1):
        body = source.read_text(encoding="utf-8")
        digests.append(hashlib.sha256(body.encode("utf-8")).hexdigest())
        for leak in json.loads(body)["leaks"]:
            leaks.append({**leak, "set": part})
    return leaks, digests[0] if len(digests) == 1 else hashlib.sha256("".join(digests).encode()).hexdigest()


def answer(leak: dict, bank=None) -> tuple:
    """What the tool says about one leak: (verdict or "unreadable", (stage, copy_no) or None)."""
    bank = bank or load_bank()
    if leak.get("reader") is not None:
        result = analyze.analyse_questions(analyze.questions_from_reader(leak["reader"]), SCORE_KEY, bank=bank)
    else:
        result = analyze.analyse_text(leak["text"] or "", SCORE_KEY, bank=bank)
    verdict = result.verdict if result.status == "done" else "unreadable"
    copy = (result.stage, result.copy_no) if result.copy_no is not None else None
    return verdict, copy


def run(path: Path | None = None) -> tuple[list[Outcome], str]:
    leaks, digest = load_set(path)
    bank = load_bank()
    outcomes = []
    for leak in leaks:
        expected = (leak["expect"]["verdict"], tuple(leak["expect"]["copy"]) if leak["expect"]["copy"] else None)
        got = answer(leak, bank)
        source = tuple(leak["source"]) if leak["source"] else None
        outcomes.append(Outcome(leak["id"], leak["kind"], bool(leak["held"]), expected, got, got == expected,
                                got[1] is not None and got[1] != source, leak.get("note", ""), leak.get("set", 1)))
    return outcomes, digest


def summarise(outcomes: list[Outcome]) -> dict:
    def part(rows):
        return {"right": sum(o.right for o in rows), "total": len(rows), "wrong_copy": sum(o.wrong_copy for o in rows)}
    out = {"read": part([o for o in outcomes if not o.held]), "held": part([o for o in outcomes if o.held])}
    for number in sorted({o.set for o in outcomes}):
        out[f"set{number}"] = {"read": part([o for o in outcomes if o.set == number and not o.held]),
                               "held": part([o for o in outcomes if o.set == number and o.held])}
    return out


def _share(part: dict) -> str:
    return f"{part['right']}/{part['total']} = {part['right'] / max(1, part['total']):.1%}"


def report(outcomes: list[Outcome], digest: str, say=print, show_failures: bool = True) -> bool:
    """Print the scores. Returns False if any wrong copy was named. Nothing is said about any set-aside leak."""
    summary = summarise(outcomes)
    read, held = summary["read"], summary["held"]
    say(f"score set {digest[:12]}: {len(outcomes)} leaks")
    if show_failures:
        kinds = dict.fromkeys(o.kind for o in outcomes)
        for kind in kinds:
            rows = [o for o in outcomes if o.kind == kind and not o.held]
            say(f"  {kind:24} {sum(o.right for o in rows)}/{len(rows)}")
        for o in outcomes:
            if not o.held and not o.right:
                flag = "  WRONG COPY NAMED" if o.wrong_copy else ""
                say(f"  leak {o.id:>2} ({o.kind}; {o.note}): expected {o.expected}, got {o.got}{flag}")
    sets = sorted(k for k in summary if k.startswith("set"))
    if len(sets) > 1:
        for name in sets:
            say(f"{name[:3]} {name[3:]}:  readable {_share(summary[name]['read'])},  set aside {_share(summary[name]['held'])}")
    say(f"leaks I may read:  {_share(read)}")
    say(f"set-aside leaks:   {_share(held)}")
    wrong = read["wrong_copy"] + held["wrong_copy"]
    if wrong:
        say(f"RUN FAILED: a wrong copy was named {wrong} time(s) ({read['wrong_copy']} read, {held['wrong_copy']} set aside).")
        return False
    say("No wrong copy was named.")
    return True


def show(leak_id: int, path: Path | None = None) -> str:
    """The text of one leak, for reading a failure. Set-aside leaks are refused."""
    leaks, _ = load_set(path)
    leak = next((x for x in leaks if x["id"] == leak_id), None)
    if leak is None:
        raise LookupError(f"There is no leak {leak_id} in the score set.")
    if leak["held"]:
        raise PermissionError(f"Leak {leak_id} is set aside. It is only ever scored, never read.")
    if leak.get("reader") is not None:
        return json.dumps(leak["reader"], ensure_ascii=False, indent=1)
    return leak["text"]
