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


def test_run_worker_processes_the_queue_off_the_event_loop_and_requeues_interrupted_leaks(conn):
    import asyncio
    import threading
    stuck, waiting = queue(conn), queue(conn)
    conn.execute("UPDATE leaks SET status = 'reading' WHERE id = ?", (stuck,))      # a run that was stopped part-way
    conn.commit()
    done, threads = [], set()

    def handler(c, leak):
        threads.add(threading.current_thread().name)
        c.execute("UPDATE leaks SET status = 'done' WHERE id = ?", (leak["id"],))
        c.commit()

    async def scenario():
        stop = asyncio.Event()

        def on_done(leak_id):
            done.append(leak_id)
            if len(done) == 2:
                stop.set()
        await asyncio.wait_for(worker.run_worker(handler, stop, on_done=on_done, interval=0.05), timeout=10)

    asyncio.run(scenario())
    assert done == [stuck, waiting]
    assert threads and threading.current_thread().name not in threads
    assert status(conn, stuck)["status"] == status(conn, waiting)["status"] == "done"
