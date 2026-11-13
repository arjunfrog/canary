from canary import audit


def test_chain_verifies(conn):
    for action in ("unlocked", "case viewed", "evidence issued"):
        audit.record(conn, action, {"case_id": 7})
    assert audit.verify(conn) == (True, None)


def test_empty_log_verifies(conn):
    assert audit.verify(conn) == (True, None)


def test_edited_row_is_caught(conn):
    for action in ("unlocked", "case viewed", "evidence issued"):
        audit.record(conn, action)
    conn.execute("UPDATE audit_log SET action = 'nothing happened' WHERE id = 2")
    conn.commit()
    assert audit.verify(conn) == (False, 2)


def test_deleted_row_is_caught(conn):
    for action in ("unlocked", "case viewed", "evidence issued"):
        audit.record(conn, action)
    conn.execute("DELETE FROM audit_log WHERE id = 2")
    conn.commit()
    assert audit.verify(conn) == (False, 3)
