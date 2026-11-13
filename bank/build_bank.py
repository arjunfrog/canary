#!/usr/bin/env python3
"""Build bank.db, Canary's question bank, from physics.py, chemistry.py and biology.py.

Run:  python3 bank/build_bank.py     (rebuilds canary/data/bank.db)

Tables written:
  questions   one row per question. Numeric stems keep their {placeholders}.
  value_sets  nine rows per numeric question: set_no 0 is the real values,
              1 to 8 are decoys. Each row has the rendered stem, the answer and
              the three distractors as text, so nothing needs evaluating later.
  meta        counts and notes.

The build fails loudly if any rule is broken: nine usable value sets per numeric
question, four distinct options everywhere, short stems on page 1, exact counts.
"""
import itertools
import json
import random
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import biology
import chemistry
import physics

HERE = Path(__file__).parent
DB = HERE.parent / "canary" / "data" / "bank.db"
SOURCE = "Written in the style of previous-year NEET questions. Not verbatim copies."
STATEMENT_OPTIONS = [
    "Both Statement I and Statement II are correct",
    "Both Statement I and Statement II are incorrect",
    "Statement I is correct but Statement II is incorrect",
    "Statement I is incorrect but Statement II is correct",
]
DIFFICULTY = {"E": "easy", "M": "medium", "H": "hard"}
PAGE_ONE = 14          # first questions of the paper: numeric physics, short stems
PAGE_ONE_MAX_WORDS = 25
SETS = 9               # 1 real + 8 decoys
# real questions, traps and reserves per group
PLAN = {
    ("physics", "numeric"): (36, 0, 9),
    ("physics", "fixed"): (9, 0, 3),
    ("chemistry", "numeric"): (15, 0, 4),
    ("chemistry", "fixed"): (30, 0, 8),
    ("biology", "fixed"): (90, 24, 22),
}
errors = []


def fmt(v):
    v = round(float(v), 3)
    return str(int(v)) if v == int(v) else f"{v:.3f}".rstrip("0").rstrip(".")


def clean(v):
    return isinstance(v, (int, float)) and abs(v) < 1e7 and abs(v * 1000 - round(v * 1000)) < 1e-6


def ev(expr, params):
    # Expressions come only from the data files in this folder.
    return eval(expr, {"__builtins__": {}}, dict(params))


def make_value_sets(qid, stem, unit, answer, distractors, values, constraint):
    combos = values if isinstance(values, list) else [
        dict(zip(values, c)) for c in itertools.product(*values.values())]
    valid = []
    for p in combos:
        try:
            if constraint and not ev(constraint, p):
                continue
            nums = [ev(e, p) for e in [answer] + distractors]
        except ZeroDivisionError:
            continue
        if not all(clean(n) for n in nums) or nums[0] <= 0:
            continue
        texts = [f"{fmt(n)} {unit}".strip() for n in nums]
        if len(set(texts)) < 4:
            continue
        valid.append((p, texts))
    random.Random(qid).shuffle(valid)
    chosen, seen = [], set()
    for p, texts in valid:
        key = tuple(sorted(fmt(x) for x in p.values()))   # same numbers in any order count as one
        if key in seen:
            continue
        seen.add(key)
        chosen.append((p, texts))
        if len(chosen) == SETS:
            break
    if len(chosen) < SETS:
        errors.append(f"{qid}: only {len(chosen)} usable value sets ({len(valid)} valid combos): {stem[:50]}")
    rows = []
    for i, (p, texts) in enumerate(chosen):
        shown = {k: fmt(v) for k, v in p.items()}
        rows.append((qid, i, int(i == 0), json.dumps(shown), stem.format(**shown), texts[0], json.dumps(texts[1:], ensure_ascii=False)))
    return rows


def collect():
    """Return question dicts in source order, with stable ids."""
    out = []
    for subject, mod, prefix in (("physics", physics, "P"), ("chemistry", chemistry, "C"), ("biology", biology, "B")):
        n = 0
        for topic, diff, stem, unit, answer, distractors, values, constraint in getattr(mod, "NUMERIC", []):
            n += 1
            out.append(dict(id=f"{prefix}{n:03d}", subject=subject, group="numeric", topic=topic, difficulty=DIFFICULTY[diff],
                            stem=stem, unit=unit, answer=answer, distractors=distractors, values=values,
                            constraint=constraint, pinned=0))
        for topic, diff, stem, correct, *wrong in mod.FIXED:
            n += 1
            qid = f"{prefix}{n:03d}"
            opts = [correct] + wrong
            random.Random(qid).shuffle(opts)
            out.append(dict(id=qid, subject=subject, group="fixed", topic=topic, difficulty=DIFFICULTY[diff],
                            stem=stem, options=opts, correct_index=opts.index(correct), pinned=0))
        for topic, diff, s1, s2, correct_index in mod.STATEMENTS:
            n += 1
            out.append(dict(id=f"{prefix}{n:03d}", subject=subject, group="fixed", topic=topic, difficulty=DIFFICULTY[diff],
                            stem=f"Statement I: {s1} Statement II: {s2} Choose the correct option.",
                            options=list(STATEMENT_OPTIONS), correct_index=correct_index, pinned=1))
    return out


def assign_roles(questions):
    """Mark each question real, trap or reserve, and give real ones a position."""
    for (subject, group), (n_real, n_trap, n_reserve) in PLAN.items():
        qs = [q for q in questions if q["subject"] == subject and q["group"] == group]
        if len(qs) != n_real + n_trap + n_reserve:
            errors.append(f"{subject} {group}: have {len(qs)}, need {n_real + n_trap + n_reserve}")
        fixed_first = qs[:PAGE_ONE] if (subject, group) == ("physics", "numeric") else []
        rest = qs[len(fixed_first):]
        random.Random(f"roles-{subject}-{group}").shuffle(rest)
        order = fixed_first + rest
        for i, q in enumerate(order):
            q["role"] = "real" if i < n_real else "trap" if i < n_real + n_trap else "reserve"
    position = 0
    for subject in ("physics", "chemistry", "biology"):
        real = [q for q in questions if q["subject"] == subject and q["role"] == "real"]
        real.sort(key=lambda q: (q["group"] != "numeric" if subject == "physics" and int(q["id"][1:]) <= PAGE_ONE else True,
                                 q["id"]))
        for q in real:
            position += 1
            q["position"] = position


def main():
    questions = collect()
    assign_roles(questions)

    q_rows, v_rows = [], []
    for q in questions:
        kind = "trap" if q["role"] == "trap" else q["group"]
        if q["group"] == "numeric":
            sets = make_value_sets(q["id"], q["stem"], q["unit"], q["answer"], q["distractors"], q["values"], q["constraint"])
            v_rows += sets
            q_rows.append((q["id"], q.get("position"), q["subject"], q["topic"], q["difficulty"], kind,
                           int(q["role"] == "reserve"), q["stem"], q["unit"], q["answer"],
                           json.dumps(q["distractors"]), None, None, 0, SOURCE))
        else:
            if len(set(q["options"])) != 4:
                errors.append(f"{q['id']}: options are not four distinct strings")
            q_rows.append((q["id"], q.get("position"), q["subject"], q["topic"], q["difficulty"], kind,
                           int(q["role"] == "reserve"), q["stem"], None, None, None,
                           json.dumps(q["options"], ensure_ascii=False), q["correct_index"], q["pinned"], SOURCE))

    stems = [r[7] for r in q_rows]
    for s in {s for s in stems if stems.count(s) > 1}:
        errors.append(f"duplicate stem: {s[:60]}")
    by_pos = {q["position"]: q for q in questions if q.get("position")}
    for pos in range(1, PAGE_ONE + 1):
        q = by_pos.get(pos)
        if not q or q["group"] != "numeric" or q["subject"] != "physics":
            errors.append(f"position {pos} is not a numeric physics question")
        elif len(q["stem"].split()) > PAGE_ONE_MAX_WORDS:
            errors.append(f"{q['id']}: page-1 stem has {len(q['stem'].split())} words")
    for qid in {r[0] for r in v_rows}:
        rendered = [r[4] for r in v_rows if r[0] == qid]
        numbers = [tuple(re.findall(r"\d+(?:\.\d+)?", s)) for s in rendered]
        if len(set(numbers)) != len(numbers):
            errors.append(f"{qid}: two value sets show the same numbers")

    if errors:
        print("\n".join(errors))
        sys.exit(f"\n{len(errors)} problem(s). bank.db not written.")

    DB.unlink(missing_ok=True)
    db = sqlite3.connect(DB)
    db.executescript("""
        CREATE TABLE questions (
            id TEXT PRIMARY KEY,
            position INTEGER UNIQUE,            -- 1 to 180 for real questions, NULL for traps and reserves
            subject TEXT NOT NULL CHECK (subject IN ('physics','chemistry','biology')),
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
            kind TEXT NOT NULL CHECK (kind IN ('numeric','fixed','trap')),
            is_reserve INTEGER NOT NULL DEFAULT 0,
            stem TEXT NOT NULL,                 -- numeric stems contain {placeholders}
            unit TEXT,                          -- numeric only
            answer_expr TEXT,                   -- numeric only
            distractor_exprs TEXT,              -- numeric only, JSON list of 3
            options TEXT,                       -- fixed and trap only, JSON list of 4
            correct_index INTEGER,              -- fixed and trap only
            pinned_order INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL
        );
        CREATE TABLE value_sets (
            question_id TEXT NOT NULL REFERENCES questions(id),
            set_no INTEGER NOT NULL,            -- 0 = real values, 1 to 8 = decoys
            is_real INTEGER NOT NULL,
            params TEXT NOT NULL,               -- JSON, values as shown in the stem
            stem TEXT NOT NULL,                 -- stem with the values filled in
            answer TEXT NOT NULL,
            distractors TEXT NOT NULL,          -- JSON list of 3
            PRIMARY KEY (question_id, set_no)
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    db.executemany("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", q_rows)
    db.executemany("INSERT INTO value_sets VALUES (?,?,?,?,?,?,?)", v_rows)
    count = lambda where: db.execute(f"SELECT count(*) FROM questions WHERE {where}").fetchone()[0]
    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "total": count("1"),
        "real": count("position IS NOT NULL"),
        "traps": count("kind = 'trap'"),
        "reserves": count("is_reserve = 1"),
        "numeric": count("kind = 'numeric'"),
        "value_sets_per_numeric": SETS,
    }
    db.executemany("INSERT INTO meta VALUES (?,?)", [(k, str(v)) for k, v in meta.items()])
    db.commit()

    print(f"Wrote {DB}")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print("  by subject and role:")
    for row in db.execute("""SELECT subject,
                                    sum(position IS NOT NULL), sum(kind='trap'), sum(is_reserve), sum(kind='numeric')
                             FROM questions GROUP BY subject ORDER BY min(rowid)"""):
        print(f"    {row[0]:10s} real {row[1]:3d}  traps {row[2]:2d}  reserves {row[3]:2d}  numeric {row[4]:2d}")
    db.close()


if __name__ == "__main__":
    main()
