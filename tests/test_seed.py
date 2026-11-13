import time

import pytest

from canary import audit, cli, config, seed


@pytest.fixture
def seeded(conn):
    counts = seed.seed(conn)
    return conn, counts


def test_seed_fills_everything_in_under_a_minute(conn):
    started = time.monotonic()
    counts = seed.seed(conn)
    assert time.monotonic() - started < 60
    assert counts == {"exams": 1, "questions": 250, "people": 300, "translator copies": 50, "print copies": 5000,
                      "custody events": 50 * 3 + 5000 * 4}


def test_seed_is_idempotent(seeded):
    conn, counts = seeded
    hashes = [r[0] for r in conn.execute("SELECT event_hash FROM custody_events ORDER BY id")]
    assert seed.seed(conn) == counts
    assert hashes == [r[0] for r in conn.execute("SELECT event_hash FROM custody_events ORDER BY id")]


def test_every_translator_copy_is_held_by_its_own_translator(seeded):
    conn, _ = seeded
    rows = conn.execute("""SELECT c.copy_no, p.role, p.id FROM copies c JOIN people p ON p.id = c.holder_id
                           WHERE c.stage = 'translation'""").fetchall()
    assert len(rows) == 50 and {r["role"] for r in rows} == {"Translator"} and len({r["id"] for r in rows}) == 50
    notes = [r["note"] for r in conn.execute("""SELECT note FROM custody_events e JOIN copies c ON c.id = e.copy_id
                                                WHERE c.stage = 'print' AND c.copy_no = 4821 ORDER BY e.id""")]
    assert len(notes) == 4 and "press" in notes[0] and "hub" in notes[1] and "locker" in notes[2] and "superintendent" in notes[3]


def test_chains_verify_and_any_edit_breaks_them(seeded):
    conn, _ = seeded
    assert seed.verify_chain(conn, "translation", 23) and seed.verify_chain(conn, "print", 4821)
    conn.execute("""UPDATE custody_events SET at = '2020-01-01T00:00:00+00:00' WHERE id =
                    (SELECT min(e.id) FROM custody_events e JOIN copies c ON c.id = e.copy_id
                     WHERE c.stage = 'print' AND c.copy_no = 4821)""")
    conn.commit()
    assert not seed.verify_chain(conn, "print", 4821)
    assert seed.verify_chain(conn, "print", 4820)
    conn.execute("""DELETE FROM custody_events WHERE id =
                    (SELECT min(e.id) + 1 FROM custody_events e JOIN copies c ON c.id = e.copy_id
                     WHERE c.stage = 'translation' AND c.copy_no = 23)""")
    conn.commit()
    assert not seed.verify_chain(conn, "translation", 23)


def test_seed_does_not_touch_the_vault(seeded, canary_home):
    assert not config.vault_path().exists()
    conn, _ = seeded
    assert audit.verify(conn) == (True, None)


def test_seed_and_verify_chain_commands(conn, capsys):
    assert cli.main(["seed"]) == 0
    assert "print copies" in capsys.readouterr().out
    assert cli.main(["verify-chain", "--stage", "print", "--copy", "12"]) == 0
    assert "verifies" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["verify-chain", "--stage", "print", "--copy", "5001"])


def test_every_handover_is_in_the_past_and_in_order(seeded):
    from canary import db
    conn, _ = seeded
    assert conn.execute("SELECT max(at) FROM custody_events").fetchone()[0] < db.now()
    for copy_id in (1, 23, 50, 51, 4871, 5050):
        times = [r["at"] for r in conn.execute("SELECT at FROM custody_events WHERE copy_id = ? ORDER BY id", (copy_id,))]
        assert times == sorted(times)
