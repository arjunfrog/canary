import pytest

from canary import cli, db, worker


def queue(conn, text="a leak"):
    cur = conn.execute("INSERT INTO leaks (source, raw_text, received_at) VALUES ('manual', ?, ?)", (text, db.now()))
    conn.commit()
    return cur.lastrowid


def status(conn, leak_id):
    return conn.execute("SELECT status, error FROM leaks WHERE id = ?", (leak_id,)).fetchone()


def test_worker_takes_leaks_oldest_first(conn):
    first, second = queue(conn), queue(conn)
    seen = []

    def handler(c, leak):
        seen.append(leak["id"])
        c.execute("UPDATE leaks SET status = 'done' WHERE id = ?", (leak["id"],))
        c.commit()

    assert worker.process_next(conn, handler) and worker.process_next(conn, handler)
    assert not worker.process_next(conn, handler)
    assert seen == [first, second]
    assert status(conn, first)["status"] == "done"


def test_failing_handler_marks_the_leak_failed_and_the_worker_continues(conn):
    bad, good = queue(conn), queue(conn)

    def handler(c, leak):
        raise RuntimeError("the photo reader is out of quota")

    worker.process_next(conn, handler)
    assert status(conn, bad)["status"] == "failed"
    assert "out of quota" in status(conn, bad)["error"]
    assert status(conn, good)["status"] == "queued"


def test_add_leak_and_cases(conn, tmp_path, capsys):
    leak = tmp_path / "leak.txt"
    leak.write_text("1. A car starts from rest...")
    assert cli.main(["add-leak", "--text", str(leak)]) == 0
    assert cli.main(["cases"]) == 0
    out = capsys.readouterr().out
    assert "Leak 1 queued." in out and "queued" in out and "manual" in out


def test_verify_audit_command(conn, capsys):
    assert cli.main(["verify-audit"]) == 0
    assert "verifies" in capsys.readouterr().out


@pytest.mark.parametrize("command", sorted(cli.NOT_BUILT))
def test_unbuilt_commands_say_which_task_builds_them(command, capsys):
    assert cli.main([command]) == 2
    assert f"task {cli.NOT_BUILT[command][1]}" in capsys.readouterr().out
