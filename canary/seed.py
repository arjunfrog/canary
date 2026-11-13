"""Seed data: the exam, 50 translator copies, 5,000 print copies, synthetic people and custody chains.

Every person and organisation here is invented. Names are random pairings from two short lists.
The seed never reads or changes the vault.
"""
import json
import random
import sqlite3
from datetime import datetime, timedelta

from . import audit, config, db
from .bank import load_bank
from .chain import GENESIS, link_hash

EXAM_TITLE = "Mock entrance exam (synthetic)"
N_CENTRES = 100
N_HUBS = 12
BATCH = 1000

GIVEN = ("Aarav", "Aditi", "Akhil", "Ananya", "Arnav", "Bhavna", "Chetan", "Deepa", "Dhruv", "Esha", "Farhan", "Gauri",
         "Harish", "Ila", "Imran", "Jaya", "Kabir", "Kavya", "Lakshmi", "Manoj", "Meera", "Nikhil", "Nisha", "Omkar",
         "Pooja", "Pranav", "Rachna", "Rohan", "Sahil", "Sana", "Tanvi", "Tarun", "Uma", "Varun", "Vidya", "Yash",
         "Zoya", "Girish", "Hema", "Joseph")
FAMILY = ("Agarwal", "Bose", "Chaudhary", "D'Souza", "Dutta", "Fernandes", "Ghosh", "Hegde", "Iyer", "Joshi", "Kulkarni",
          "Lal", "Menon", "Nair", "Oberoi", "Pillai", "Qureshi", "Rao", "Saxena", "Thomas", "Upadhyay", "Verma",
          "Wadhwa", "Yadav", "Zaveri", "Bhatt", "Chopra", "Gill", "Mathew", "Sinha")
LANGUAGES = ("Hindi", "Bengali", "Marathi", "Telugu", "Tamil", "Gujarati", "Urdu", "Kannada", "Odia", "Malayalam")


def _people() -> list[tuple[int, str, str, str]]:
    """(id, name, role, organisation) for about 300 invented people."""
    rng = random.Random("canary-synthetic-people")
    names = [f"{g} {f}" for g in GIVEN for f in FAMILY]
    rng.shuffle(names)
    roles = [("Exam cell officer", "Exam cell")] * 6
    roles += [("Translator", f"{LANGUAGES[i % len(LANGUAGES)]} translation panel") for i in range(config.N_TRANSLATORS)]
    roles += [("Press supervisor", f"Mock press, unit {i % 4 + 1}") for i in range(8)]
    roles += [("Regional hub officer", f"Regional hub {i // 3 + 1}") for i in range(N_HUBS * 3)]
    roles += [("Bank locker custodian", f"Centre {i + 1:03d}") for i in range(N_CENTRES)]
    roles += [("Centre superintendent", f"Centre {i + 1:03d}") for i in range(N_CENTRES)]
    return [(i + 1, names[i], role, organisation) for i, (role, organisation) in enumerate(roles)]


def _ids(people, role: str) -> list[int]:
    return [p[0] for p in people if p[2] == role]


def event_body(stage: str, copy_no: int, from_id, to_id, at: str, note: str) -> dict:
    """The part of a custody event its hash covers."""
    return {"copy": [stage, copy_no], "from": from_id, "to": to_id, "at": at, "note": note}


def _chain(stage: str, copy_no: int, copy_id: int, handovers: list[tuple]) -> list[tuple]:
    rows, prev = [], GENESIS
    for from_id, to_id, at, note in handovers:
        this = link_hash(prev, event_body(stage, copy_no, from_id, to_id, at, note))
        rows.append((copy_id, from_id, to_id, at, note, prev, this))
        prev = this
    return rows


def seed(conn: sqlite3.Connection) -> dict:
    """Fill the database from the bank. Safe to run twice. Returns row counts."""
    bank = load_bank()
    exam = conn.execute("SELECT created_at FROM exams WHERE id = ?", (config.EXAM_ID,)).fetchone()
    if exam is None:
        conn.execute("INSERT INTO exams (id, title, is_synthetic, created_at) VALUES (?, ?, 1, ?)",
                     (config.EXAM_ID, EXAM_TITLE, db.now()))
        exam = conn.execute("SELECT created_at FROM exams WHERE id = ?", (config.EXAM_ID,)).fetchone()
    anchor = datetime.fromisoformat(exam["created_at"])

    def at(days: float, minutes: int = 0) -> str:
        return (anchor + timedelta(days=days, minutes=minutes)).isoformat(timespec="seconds")

    conn.executemany(
        "INSERT OR IGNORE INTO questions (id, exam_id, position, subject, kind, difficulty, body, is_reserve) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(q.id, config.EXAM_ID, q.position, q.subject, q.kind, q.difficulty,
          json.dumps({"topic": q.topic, "stem": q.stem, "options": list(q.options), "pinned_order": q.pinned_order},
                     ensure_ascii=False), int(q.is_reserve)) for q in bank.questions])
    people = _people()
    conn.executemany("INSERT OR IGNORE INTO people (id, display_name, role, organisation) VALUES (?, ?, ?, ?)", people)
    conn.commit()

    officers, translators = _ids(people, "Exam cell officer"), _ids(people, "Translator")
    press, hubs = _ids(people, "Press supervisor"), _ids(people, "Regional hub officer")
    lockers, supers = _ids(people, "Bank locker custodian"), _ids(people, "Centre superintendent")
    have = {(r["stage"], r["copy_no"]) for r in conn.execute("SELECT stage, copy_no FROM copies WHERE exam_id = ?",
                                                             (config.EXAM_ID,))}
    with_events = {r[0] for r in conn.execute("SELECT DISTINCT copy_id FROM custody_events")}
    rng = random.Random("canary-custody")

    copies, events = [], []
    for n in range(1, config.N_TRANSLATORS + 1):
        copy_id, officer, holder = n, officers[n % len(officers)], translators[n - 1]
        jitter = rng.randrange(0, 240)
        if ("translation", n) not in have:
            copies.append((copy_id, config.EXAM_ID, "translation", n, holder))
        if copy_id not in with_events:
            events += _chain("translation", n, copy_id, [
                (None, officer, at(-10, jitter), "Prepared at the exam cell"),
                (officer, holder, at(-9, jitter), "Handed to the translator"),
                (holder, officer, at(-3, jitter), "Returned to the exam cell"),
            ])
    conn.executemany("INSERT INTO copies (id, exam_id, stage, copy_no, holder_id) VALUES (?, ?, ?, ?, ?)", copies)
    conn.executemany("INSERT INTO custody_events (copy_id, from_id, to_id, at, note, prev_hash, event_hash) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", events)
    conn.commit()

    per_centre = config.N_PRINT_COPIES // N_CENTRES
    for first in range(1, config.N_PRINT_COPIES + 1, BATCH):          # batched, so a stop part-way loses little
        copies, events = [], []
        for n in range(first, min(first + BATCH, config.N_PRINT_COPIES + 1)):
            copy_id = config.N_TRANSLATORS + n
            centre = min((n - 1) // per_centre, N_CENTRES - 1)
            presser, hub = press[centre % len(press)], hubs[centre % len(hubs)]
            locker, superintendent = lockers[centre], supers[centre]
            jitter = centre * 3 + (n % 7)
            if ("print", n) not in have:
                copies.append((copy_id, config.EXAM_ID, "print", n, superintendent))
            if copy_id not in with_events:
                events += _chain("print", n, copy_id, [
                    (None, presser, at(-2.5, jitter), "Printed and sealed at the press"),
                    (presser, hub, at(-2, jitter), "Received at the regional hub"),
                    (hub, locker, at(-1, jitter), f"Placed in the bank locker for centre {centre + 1:03d}"),
                    (locker, superintendent, at(-0.1, jitter), "Collected by the centre superintendent"),
                ])
        conn.executemany("INSERT INTO copies (id, exam_id, stage, copy_no, holder_id) VALUES (?, ?, ?, ?, ?)", copies)
        conn.executemany("INSERT INTO custody_events (copy_id, from_id, to_id, at, note, prev_hash, event_hash) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", events)
        conn.commit()

    counts = row_counts(conn)
    audit.record(conn, "seeded", counts)
    return counts


def row_counts(conn: sqlite3.Connection) -> dict:
    one = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "exams": one("SELECT count(*) FROM exams"),
        "questions": one("SELECT count(*) FROM questions"),
        "people": one("SELECT count(*) FROM people"),
        "translator copies": one("SELECT count(*) FROM copies WHERE stage = 'translation'"),
        "print copies": one("SELECT count(*) FROM copies WHERE stage = 'print'"),
        "custody events": one("SELECT count(*) FROM custody_events"),
    }


def custody_chain(conn: sqlite3.Connection, copy_id: int) -> tuple[list[dict], bool]:
    """One copy's custody events in order, each marked with whether its hash still fits, and the overall result."""
    copy = conn.execute("SELECT stage, copy_no FROM copies WHERE id = ?", (copy_id,)).fetchone()
    if copy is None:
        return [], False
    rows = conn.execute(
        """SELECT e.*, f.display_name AS from_name, f.role AS from_role, f.organisation AS from_org,
                  t.display_name AS to_name, t.role AS to_role, t.organisation AS to_org
           FROM custody_events e LEFT JOIN people f ON f.id = e.from_id LEFT JOIN people t ON t.id = e.to_id
           WHERE e.copy_id = ? ORDER BY e.id""", (copy_id,)).fetchall()
    events, prev, all_ok = [], GENESIS, bool(rows)
    for r in rows:
        body = event_body(copy["stage"], copy["copy_no"], r["from_id"], r["to_id"], r["at"], r["note"])
        ok = r["prev_hash"] == prev and r["event_hash"] == link_hash(prev, body)
        all_ok = all_ok and ok
        events.append({"id": r["id"], "at": r["at"], "note": r["note"], "from_id": r["from_id"], "to_id": r["to_id"],
                       "from_name": r["from_name"], "to_name": r["to_name"], "to_role": r["to_role"],
                       "to_organisation": r["to_org"], "prev_hash": r["prev_hash"], "event_hash": r["event_hash"],
                       "ok": ok})
        prev = r["event_hash"]
    return events, all_ok


def verify_chain(conn: sqlite3.Connection, stage: str, copy_no: int) -> bool:
    """Check one copy's custody chain with canary.chain.link_hash."""
    row = conn.execute("SELECT id FROM copies WHERE exam_id = ? AND stage = ? AND copy_no = ?",
                       (config.EXAM_ID, stage, copy_no)).fetchone()
    if row is None:
        raise LookupError(f"There is no {stage} copy {copy_no}. Run: python -m canary seed")
    return custody_chain(conn, row["id"])[1]
