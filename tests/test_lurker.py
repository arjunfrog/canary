import asyncio
import logging
import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from canary import analyze, config, lurker, seed, worker
from canary import fingerprint as fp
from canary.bank import load_bank
from canary.samples import leak_text

KEY = bytes.fromhex("11" * 32)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x02" * 64
CHAT = lurker.Chat(-1001234567890, "examleaks_demo", "Exam leaks demo")
WHEN = datetime(2026, 11, 13, 9, 30, tzinfo=timezone.utc)


def message(id, text="", photo=False, document=None, sender=None, post_author=None, private=False):
    sender = sender or SimpleNamespace(id=777, username="paper_seller", first_name="Paper", last_name="Seller")
    return SimpleNamespace(id=id, raw_text=text, message=text, photo=object() if photo else None, document=document,
                           date=WHEN, sender_id=sender.id, sender=sender, post_author=post_author, is_private=private,
                           chat_id=CHAT.id)


class FakeClient:
    """Stands in for the wrapped Telethon client. Records every call so the tests can prove nothing was sent."""

    def __init__(self, history=(), media=PNG, authorised=True):
        self.history, self.media, self.authorised = list(history), media, authorised
        self.calls, self.handlers, self.connected = [], [], False

    async def connect(self):
        self.calls.append("connect")
        self.connected = True

    async def disconnect(self):
        self.calls.append("disconnect")
        self.connected = False

    def is_connected(self):
        return self.connected

    async def is_user_authorized(self):
        return self.authorised

    async def get_entity(self, name):
        self.calls.append("get_entity")
        from telethon.tl import types
        return types.Channel(id=1234567890, title="Exam leaks demo", photo=types.ChatPhotoEmpty(), date=WHEN,
                             username=name, broadcast=True)

    async def join_public(self, entity):
        self.calls.append("join_public")

    async def download_media(self, msg, file=None):
        self.calls.append("download_media")
        return self.media

    def iter_messages(self, name, limit=None):
        self.calls.append("iter_messages")

        async def gen():
            for m in self.history[:limit]:
                yield m
        return gen()

    def add_event_handler(self, callback, event=None):
        self.calls.append("add_event_handler")
        self.handlers.append(callback)

    def remove_event_handler(self, callback, event=None):
        self.calls.append("remove_event_handler")


def go(coro):
    return asyncio.run(coro)


LONG = "1. " + "A long question about physics with enough words to be a paper. " * 5


def test_a_long_text_post_becomes_a_queued_leak_row(conn):
    leak_id = go(lurker.handle_message(conn, FakeClient(), message(41, LONG), CHAT))
    row = conn.execute("SELECT * FROM leaks WHERE id = ?", (leak_id,)).fetchone()
    assert (row["source"], row["status"], row["chat_id"], row["chat_title"]) == ("telegram", "queued", CHAT.id, "Exam leaks demo")
    assert (row["chat_username"], row["message_id"], row["message_url"]) == ("examleaks_demo", 41, "https://t.me/examleaks_demo/41")
    assert (row["sender_id"], row["sender_username"], row["sender_name"]) == (777, "paper_seller", "Paper Seller")
    assert row["raw_text"] == LONG and row["image_path"] is None and row["posted_at"] == "2026-11-13T09:30:00+00:00"


def test_a_photo_is_saved_under_its_hash_with_its_caption(conn):
    client = FakeClient()
    leak_id = go(lurker.handle_message(conn, client, message(42, "NEET paper page 1", photo=True), CHAT))
    row = conn.execute("SELECT * FROM leaks WHERE id = ?", (leak_id,)).fetchone()
    assert row["raw_text"] == "NEET paper page 1" and len(row["image_sha256"]) == 64
    saved = config.home() / "leaks"
    assert row["image_path"].startswith(str(saved)) and open(row["image_path"], "rb").read() == PNG
    assert client.calls == ["download_media"]


def test_image_documents_up_to_10_mb_are_kept_and_everything_else_is_ignored(conn):
    doc = lambda mime, size: SimpleNamespace(mime_type=mime, size=size)
    client = FakeClient()
    assert go(lurker.handle_message(conn, client, message(1, document=doc("image/png", 9_000_000)), CHAT))
    assert go(lurker.handle_message(conn, client, message(2, document=doc("image/png", 11_000_000)), CHAT)) is None
    assert go(lurker.handle_message(conn, client, message(3, LONG, document=doc("application/pdf", 1000)), CHAT)) is None
    assert go(lurker.handle_message(conn, client, message(4, document=doc("video/mp4", 1000)), CHAT)) is None
    assert go(lurker.handle_message(conn, client, message(5, "short text"), CHAT)) is None
    assert go(lurker.handle_message(conn, client, message(6, "x" * 199), CHAT)) is None
    assert go(lurker.handle_message(conn, client, message(7, "x" * 200), CHAT))
    assert go(lurker.handle_message(conn, client, message(8, LONG, private=True), CHAT)) is None
    assert conn.execute("SELECT count(*) FROM leaks").fetchone()[0] == 2
    assert client.calls == ["download_media"]


def test_a_file_that_only_claims_to_be_an_image_is_dropped(conn):
    client = FakeClient(media=b"MZ\x90\x00 not an image")
    assert go(lurker.handle_message(conn, client, message(9, photo=True), CHAT)) is None
    assert conn.execute("SELECT count(*) FROM leaks").fetchone()[0] == 0
    assert not list((config.home() / "leaks").iterdir())


def test_duplicates_are_skipped_and_not_downloaded_again(conn):
    client = FakeClient()
    assert go(lurker.handle_message(conn, client, message(42, photo=True), CHAT))
    assert go(lurker.handle_message(conn, client, message(42, photo=True), CHAT)) is None
    assert client.calls == ["download_media"] and conn.execute("SELECT count(*) FROM leaks").fetchone()[0] == 1


def test_a_channel_post_stores_its_author_signature(conn):
    channel = SimpleNamespace(id=1234567890, username="examleaks_demo", title="Exam leaks demo")
    leak_id = go(lurker.handle_message(conn, FakeClient(), message(50, LONG, sender=channel, post_author="Admin R"), CHAT))
    row = conn.execute("SELECT * FROM leaks WHERE id = ?", (leak_id,)).fetchone()
    assert (row["sender_name"], row["sender_username"]) == ("Admin R", "examleaks_demo")
    leak_id = go(lurker.handle_message(conn, FakeClient(), message(51, LONG, sender=channel), CHAT))
    assert conn.execute("SELECT sender_name FROM leaks WHERE id = ?", (leak_id,)).fetchone()[0] == "Exam leaks demo"


def test_at_most_ten_new_leaks_a_minute_per_chat_and_drops_are_logged(conn, caplog):
    now = [0.0]
    limiter = lurker.RateLimit(clock=lambda: now[0])
    kept = [go(lurker.handle_message(conn, FakeClient(), message(100 + i, LONG), CHAT, limiter)) for i in range(13)]
    assert sum(1 for k in kept if k) == 10 and kept[10:] == [None, None, None]
    assert sum("Dropped message" in r.getMessage() for r in caplog.records) == 3
    # every drop is counted and logged, but the audit log gets one row a minute per chat, so a flood cannot fill it
    assert limiter.dropped[CHAT.id] == 3
    dropped = conn.execute("SELECT detail FROM audit_log WHERE action = 'leaks dropped, chat too busy'").fetchall()
    assert len(dropped) == 1 and '"first_message_id": 110' in dropped[0][0]
    other = lurker.Chat(-1009, "another_chat", "Another")
    assert go(lurker.handle_message(conn, FakeClient(), message(1, LONG), other, limiter))    # other chats are unaffected
    now[0] = 61.0
    assert go(lurker.handle_message(conn, FakeClient(), message(200, LONG), CHAT, limiter))
    for i in range(12):
        go(lurker.handle_message(conn, FakeClient(), message(300 + i, LONG), CHAT, limiter))
    assert conn.execute("SELECT count(*) FROM audit_log WHERE action = 'leaks dropped, chat too busy'").fetchone()[0] == 2


def test_usernames_are_cleaned_and_anything_odd_is_refused():
    assert lurker.clean_username("@examleaks_demo") == "examleaks_demo"
    assert lurker.clean_username("https://t.me/examleaks_demo/") == "examleaks_demo"
    for bad in ("", "ab", "+919999999999", "t.me/joinchat/AAAA-xyz", "name; DROP TABLE leaks", "../etc/passwd"):
        with pytest.raises(lurker.TelegramNotReady):
            lurker.clean_username(bad)


def test_watch_joins_and_records_and_unwatch_removes(conn):
    client = FakeClient()
    assert go(lurker.watch(conn, None, "@examleaks_demo", client=client)) == "Exam leaks demo"
    assert client.calls == ["connect", "get_entity", "join_public", "disconnect"]
    assert [r["username"] for r in conn.execute("SELECT username FROM watched_chats")] == ["examleaks_demo"]
    assert lurker.unwatch(conn, "examleaks_demo") and not lurker.unwatch(conn, "examleaks_demo")
    assert conn.execute("SELECT count(*) FROM watched_chats").fetchone()[0] == 0


def test_watch_refuses_people_and_private_chats(conn, monkeypatch):
    client = FakeClient()

    async def a_person(name):
        return SimpleNamespace(id=5, username=name, first_name="Someone")
    monkeypatch.setattr(client, "get_entity", a_person)
    with pytest.raises(lurker.TelegramNotReady, match="never opens private chats"):
        go(lurker.watch(conn, None, "some_person", client=client))
    assert "join_public" not in client.calls and conn.execute("SELECT count(*) FROM watched_chats").fetchone()[0] == 0


def test_the_listener_backfills_then_handles_new_messages_and_never_sends(conn):
    bank = load_bank()
    seed.seed(conn)
    paper = leak_text(fp.render_translator_copy(KEY, 1, 23, bank)[:14])
    conn.execute("INSERT INTO watched_chats (username, title, added_at) VALUES ('examleaks_demo', 'Exam leaks demo', '2026')")
    conn.commit()
    client = FakeClient(history=[message(10, paper), message(11, "hello"), message(12, photo=True)])
    state, seen = lurker.ListenerState(), []

    async def scenario():
        from telethon import utils
        stop = asyncio.Event()
        task = asyncio.create_task(lurker.run_listener(conn, None, stop, on_leak=seen.append, state=state, client=client))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if client.handlers and len(seen) == 2:
                break
        assert state.connected and state.watching == 1
        chat_id = utils.get_peer_id(await client.get_entity("examleaks_demo"))
        live = message(13, LONG)
        await client.handlers[0](SimpleNamespace(chat_id=chat_id, is_private=False, message=live))
        await client.handlers[0](SimpleNamespace(chat_id=-100999, is_private=False, message=message(14, LONG)))   # not watched
        await client.handlers[0](SimpleNamespace(chat_id=chat_id, is_private=True, message=message(15, LONG)))    # private
        stop.set()
        await task

    go(scenario())
    assert [r["message_id"] for r in conn.execute("SELECT message_id FROM leaks ORDER BY message_id")] == [10, 12, 13]
    assert len(seen) == 3 and not state.connected
    allowed = {"connect", "disconnect", "get_entity", "iter_messages", "download_media", "add_event_handler", "remove_event_handler"}
    assert set(client.calls) <= allowed

    # the text posted in the channel comes out as the right case
    handler = lambda c, leak: analyze.analyze_leak(c, leak, KEY, None)
    worker.process_next(conn, handler)
    case = conn.execute("""SELECT c.verdict, c.stage, p.copy_no FROM cases c JOIN leaks l ON l.id = c.leak_id
                           JOIN copies p ON p.id = c.copy_id WHERE l.message_id = 10""").fetchone()
    assert tuple(case) == ("traced", "translation", 23)


def test_without_a_login_the_listener_says_what_to_do_and_stops(conn):
    class EmptyVault:
        def get(self, name):
            return None
    state = lurker.ListenerState()
    go(lurker.run_listener(conn, EmptyVault(), asyncio.Event(), state=state))
    assert not state.connected and "vault set" in state.message
    unauthorised = lurker.ListenerState()
    go(lurker.run_listener(conn, None, asyncio.Event(), state=unauthorised, client=FakeClient(authorised=False)))
    assert "tg-login" in unauthorised.message


def test_the_wrapper_refuses_every_call_that_could_write():
    class Real:
        def __getattr__(self, name):
            return lambda *a, **k: name
    wrapped = lurker.ReadOnlyTelegram(Real())
    assert wrapped.iter_messages() == "iter_messages" and wrapped.download_media() == "download_media"
    for name in ("send_message", "send_file", "send_read_acknowledge", "forward_messages", "edit_message",
                 "delete_messages", "send_reaction", "pin_message", "get_dialogs", "iter_dialogs", "inline_query",
                 "conversation", "action", "__call__"):
        with pytest.raises((AttributeError, TypeError)):
            getattr(wrapped, name)()
    with pytest.raises(AttributeError):
        wrapped.extra = 1


def test_the_listener_source_has_no_writing_calls():
    source = inspect.getsource(lurker)
    code = "\n".join(line.split("#")[0] for line in source.splitlines() if not line.strip().startswith(('"""', "It ", "client is")))
    for forbidden in ("send_message", "send_file", ".reply(", ".respond(", "mark_read", "send_read_acknowledge",
                      "SendReactionRequest", "forward_", ".edit(", ".delete(", "get_dialogs", "iter_dialogs",
                      "ImportChatInviteRequest", ".click("):
        assert forbidden not in code, forbidden


# ---- networks that block Telegram on its usual port

class PortClient:
    """A client whose connect works only on the ports a network lets through."""

    def __init__(self, port, open_ports, log):
        self.port, self.open_ports, self.log = port, open_ports, log

    async def connect(self):
        self.log.append(("connect", self.port))
        if self.port not in self.open_ports:
            raise asyncio.IncompleteReadError(b"", 8)           # what a blocked port looks like: cut off at once

    async def disconnect(self):
        self.log.append(("disconnect", self.port))


def test_connect_falls_back_to_the_next_port_that_works(monkeypatch):
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)
    log = []
    client, port = go(lurker.connect_any(lambda p: PortClient(p, {5222}, log)))
    assert port == 5222 and client.port == 5222
    assert log == [("connect", 443), ("disconnect", 443), ("connect", 5222)]
    log.clear()
    # the port that worked is remembered and tried first next time
    assert go(lurker.connect_any(lambda p: PortClient(p, {443, 5222}, log)))[1] == 5222 and log == [("connect", 5222)]
    log.clear()
    # if the remembered port stops working (another network), the others are tried again
    assert go(lurker.connect_any(lambda p: PortClient(p, {443}, log)))[1] == 443
    assert log == [("connect", 5222), ("disconnect", 5222), ("connect", 443)]
    assert lurker.remembered_port() == 443


def test_when_every_port_is_blocked_it_says_so_in_plain_words(monkeypatch):
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)
    with pytest.raises(lurker.TelegramNotReady, match="port 443 or 5222 or 80.*phone hotspot.*Typed leaks still work"):
        go(lurker.connect_any(lambda p: PortClient(p, set(), [])))


def test_a_port_can_be_pinned(monkeypatch):
    monkeypatch.setenv("CANARY_TG_PORT", "5222")
    log = []
    assert go(lurker.connect_any(lambda p: PortClient(p, {443, 5222}, log)))[1] == 5222 and log == [("connect", 5222)]
    monkeypatch.setenv("CANARY_TG_PORT", "five")
    with pytest.raises(lurker.TelegramNotReady, match="port number"):
        lurker.ports()


def test_the_chosen_port_is_used_for_every_connection_even_after_a_move_to_another_data_centre():
    from telethon.network.connection import ConnectionTcpFull
    assert lurker.connection_on(443) is ConnectionTcpFull
    forced = lurker.connection_on(5222)
    assert issubclass(forced, ConnectionTcpFull)
    for dc_id, ip in ((2, "149.154.167.51"), (5, "91.108.56.130")):       # Telegram asks for 443 when it moves the account
        conn = forced(ip, 443, dc_id, loggers={"telethon.network.connection.connection": logging.getLogger("t")})
        assert (conn._ip, conn._port) == (ip, 5222)


def test_the_listener_reports_the_port_and_a_blocked_network(conn, monkeypatch):
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)

    class Vault:
        def get(self, name):
            return {"tg_api_id": "12345", "tg_api_hash": "0" * 32, "tg_session": "1Aabc"}.get(name)

    built = []

    def make(vault, session=None, port=443):
        client = FakeClient()
        client.port = port

        async def connect():
            client.calls.append("connect")
            if port != 5222:
                raise asyncio.IncompleteReadError(b"", 8)
            client.connected = True
        client.connect = connect
        built.append(client)
        return client

    monkeypatch.setattr(lurker, "make_client", make)
    state = lurker.ListenerState()

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(lurker.run_listener(conn, Vault(), stop, state=state))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if state.connected:
                break
        assert state.message == "Telegram connected on port 5222."
        stop.set()
        await task
    go(scenario())
    assert [c.port for c in built if "connect" in c.calls] == [443, 5222]

    monkeypatch.setenv("CANARY_TG_PORT", "443")
    blocked = lurker.ListenerState()

    async def blocked_scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(lurker.run_listener(conn, Vault(), stop, state=blocked))
        for _ in range(200):
            await asyncio.sleep(0.01)
            if "Could not reach" in blocked.message:
                break
        stop.set()
        await task
    go(blocked_scenario())
    assert not blocked.connected and "phone hotspot" in blocked.message


def test_login_explains_a_blocked_network_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("CANARY_TG_PORT", "1")                  # nothing answers there

    class Vault:
        def get(self, name):
            return {"tg_api_id": "12345", "tg_api_hash": "0" * 32}.get(name)

    monkeypatch.setattr(lurker, "CONNECT_SECONDS", 3)
    with pytest.raises(lurker.TelegramNotReady, match="Could not reach Telegram"):
        go(lurker.login(Vault(), ask=lambda prompt: pytest.fail("must not ask for a phone number"), ask_secret=lambda p: ""))


class SavedLoginClient(PortClient):
    """With a saved login the connection always opens; a blocked port only shows when Telegram is asked something."""

    async def connect(self):
        self.log.append(("connect", self.port))

    async def ping(self):
        self.log.append(("ping", self.port))
        if self.port not in self.open_ports:
            raise ConnectionError("Cannot send requests while disconnected")


def test_a_port_only_counts_once_telegram_answers_on_it(monkeypatch):
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)
    log = []
    client, port = go(lurker.connect_any(lambda p: SavedLoginClient(p, {5222}, log)))
    assert port == 5222
    assert log == [("connect", 443), ("ping", 443), ("disconnect", 443), ("connect", 5222), ("ping", 5222)]


def test_a_port_where_telegram_never_answers_is_given_up_quickly(monkeypatch):
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)
    monkeypatch.setattr(lurker, "ANSWER_SECONDS", 0.2)

    class Silent(SavedLoginClient):
        async def ping(self):
            if self.port == 443:
                await asyncio.sleep(60)                         # Telethon retrying forever on a blocked port

    client, port = go(lurker.connect_any(lambda p: Silent(p, {5222}, [])))
    assert port == 5222


def test_a_refusal_from_telegram_still_proves_the_connection_works():
    from telethon.errors import RPCError

    class Refuses:
        async def __call__(self, request):
            raise RPCError(request, "API_ID_INVALID", 400)

    go(lurker.answers(Refuses()))                              # no exception: Telegram answered


def test_telethon_retry_messages_are_kept_out_of_the_terminal():
    assert logging.getLogger("telethon").getEffectiveLevel() >= logging.ERROR


def test_the_remembered_port_is_a_private_file_and_nonsense_in_it_is_ignored(canary_home, monkeypatch):
    import stat
    import sys
    monkeypatch.delenv("CANARY_TG_PORT", raising=False)
    assert lurker.ports() == (443, 5222, 80)
    lurker.remember_port(80)
    assert lurker.ports() == (80, 443, 5222)
    if sys.platform != "win32":
        assert stat.S_IMODE((canary_home / "telegram_port").stat().st_mode) == 0o600
    (canary_home / "telegram_port").write_text("22")              # only Telegram's own ports are ever tried
    assert lurker.ports() == (443, 5222, 80)
