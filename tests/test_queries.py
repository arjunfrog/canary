import json

import pytest

from canary import analyze, leaks, queries, seed, worker
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import fake_paper_text, garble, leak_text

KEY = bytes.fromhex("11" * 32)


@pytest.fixture
def world(conn):
    """A seeded database with one leak of each kind, analysed."""
    seed.seed(conn)
    bank = load_bank()
    translator = fp.render_translator_copy(KEY, 1, 23, bank)
    ids = {
        "translator": leaks.add_manual_leak(conn, text=leak_text(translator[:14])),
        "print": leaks.add_manual_leak(conn, text=leak_text(fp.render_print_copy(KEY, 1, 4821, bank)[:14])),
        "fake": leaks.add_manual_leak(conn, text=fake_paper_text()),
        "garbled": leaks.add_manual_leak(conn, text=garble(leak_text(translator[:14]), 0.4, seed=3)),
        "few": leaks.add_manual_leak(conn, text=leak_text(translator[20:24], options=False)),
    }
    conn.execute("""UPDATE leaks SET source = 'telegram', chat_title = 'Exam <b>leaks</b> demo', chat_username = 'examleaks_demo',
                    chat_id = -100123, message_id = 41, message_url = 'https://t.me/examleaks_demo/41',
                    sender_name = 'Paper Seller', sender_username = 'paper_seller' WHERE id = ?""", (ids["translator"],))
    conn.commit()
    handler = lambda c, leak: analyze.analyze_leak(c, leak, KEY, None, bank)
    while worker.process_next(conn, handler):
        pass
    ids["queued"] = leaks.add_manual_leak(conn, text="still waiting " * 30)
    return conn, ids


def test_list_leaks_is_newest_first_with_chat_sender_status_and_verdict(world):
    conn, ids = world
    rows = queries.list_leaks(conn, limit=50)
    assert all(isinstance(r, queries.LeakRow) for r in rows)
    assert [r.id for r in rows] == sorted(ids.values(), reverse=True)
    by_id = {r.id: r for r in rows}
    first = by_id[ids["translator"]]
    assert (first.chat, first.sender, first.status, first.verdict) == ("Exam <b>leaks</b> demo", "Paper Seller (@paper_seller)", "done", "traced")
    assert (first.stage, first.copy_no) == ("translation", 23) and first.posted_at
    assert (by_id[ids["print"]].verdict, by_id[ids["print"]].copy_no) == ("traced", 4821)
    assert (by_id[ids["fake"]].verdict, by_id[ids["fake"]].copy_no, by_id[ids["fake"]].chat) == ("not_our_paper", None, "Added by hand")
    assert (by_id[ids["garbled"]].status, by_id[ids["garbled"]].verdict, by_id[ids["garbled"]].case_id) == ("unreadable", None, None)
    assert (by_id[ids["few"]].verdict, by_id[ids["few"]].copy_no) == ("inconclusive", None)
    assert by_id[ids["queued"]].status == "queued"
    assert len(queries.list_leaks(conn, limit=2)) == 2


def test_get_case_has_the_leak_clues_funnel_and_custody(world):
    conn, ids = world
    case_id = queries.get_leak(conn, ids["translator"]).case_id
    view = queries.get_case(conn, case_id)
    assert isinstance(view, queries.CaseView) and view.leak_id == ids["translator"]
    assert (view.verdict, view.stage, view.copy_no, view.candidates) == ("traced", "translation", 23, 50)
    assert view.message_url == "https://t.me/examleaks_demo/41" and view.raw_text.startswith("1. ")
    assert len(view.steps) == 28 and view.steps[-1]["remaining"] == 1 and "alive" not in view.steps[0]
    assert len(view.clues) == 28 and all(c.read_ok and c.matched for c in view.clues)
    assert {c.kind for c in view.clues} == {"value", "order"} and view.clues[0].position == 1
    assert len(view.questions) == 14 and all(q.exposed and q.span for q in view.questions)
    assert view.holder_role == "Translator" and view.holder_name
    assert view.custody_ok is True and [e.note for e in view.custody] == [
        "Prepared at the exam cell", "Handed to the translator", "Returned to the exam cell"]
    in_force = view.holder_at_leak
    assert in_force is view.custody[-1] and sum(e.in_force for e in view.custody) == 1   # posted after the copy came back
    assert view.response and view.response["exposed_count"] == 14
    assert queries.get_case(conn, 99999) is None


def test_the_custody_event_in_force_follows_the_time_of_the_post(world):
    conn, ids = world
    view = queries.get_leak(conn, ids["translator"])
    during = view.custody[1].at                                  # the moment it was handed to the translator
    conn.execute("UPDATE leaks SET posted_at = ? WHERE id = ?", (during, ids["translator"]))
    conn.commit()
    again = queries.get_leak(conn, ids["translator"])
    assert again.holder_at_leak.note == "Handed to the translator" and again.holder_at_leak.to_role == "Translator"
    conn.execute("UPDATE leaks SET posted_at = '2001-01-01T00:00:00+00:00' WHERE id = ?", (ids["translator"],))
    conn.commit()
    assert queries.get_leak(conn, ids["translator"]).holder_at_leak is None     # before any handover


def test_a_changed_custody_event_shows_as_not_verifying(world):
    conn, ids = world
    conn.execute("UPDATE custody_events SET note = 'Never left the exam cell' WHERE copy_id = 23 AND note LIKE 'Handed%'")
    conn.commit()
    view = queries.get_leak(conn, ids["translator"])
    assert view.custody_ok is False and [e.ok for e in view.custody] == [True, False, True]


def test_views_without_a_named_copy_name_nobody(world):
    conn, ids = world
    few = queries.get_leak(conn, ids["few"])
    assert (few.verdict, few.copy_no, few.holder_name, few.custody) == ("inconclusive", None, None, [])
    assert all(c.matched is None for c in few.clues) and len(few.steps) == 4
    stored = json.loads(conn.execute("SELECT steps FROM cases WHERE leak_id = ?", (ids["few"],)).fetchone()[0])
    assert stored["copy_no"] is None and "alive" not in json.dumps(stored)       # nobody is named, even in the database
    fake = queries.get_leak(conn, ids["fake"])
    assert (fake.verdict, fake.stage, fake.response, fake.steps) == ("not_our_paper", None, None, [])
    assert not any(q.exposed for q in fake.questions)
    garbled = queries.get_leak(conn, ids["garbled"])
    assert (garbled.status, garbled.verdict, garbled.case_id) == ("unreadable", None, None)


def test_a_view_survives_a_round_trip_through_json(world):
    conn, ids = world
    view = queries.get_leak(conn, ids["print"])
    again = queries.CaseView.from_json(json.loads(json.dumps(view.to_json())))
    assert again == view and again.holder_at_leak.to_role == "Centre superintendent"


def test_status_counts_leaks_and_lists_watched_chats(world):
    conn, ids = world
    conn.execute("INSERT INTO watched_chats (username, title, added_at) VALUES ('examleaks_demo', 'Exam leaks demo', '2026')")
    conn.commit()
    status = queries.status(conn)
    assert status.watched == [("examleaks_demo", "Exam leaks demo")] and status.seeded
    assert status.counts == {"done": 4, "unreadable": 1, "queued": 1} and status.total == 6
