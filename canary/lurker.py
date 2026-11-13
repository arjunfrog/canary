"""The Telegram listener: an ordinary account that reads watched public chats and saves paper-like posts.

It only reads. It never sends, replies, reacts, marks as read or opens private chats. The Telethon
client is wrapped in ReadOnlyTelegram, which lets through the few reading calls used here and refuses
every other one. The login session lives in the vault as a string, never as a file.

Everything a message carries (text, captions, names, files) is untrusted data and is only stored.
"""
import asyncio
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import timezone

from . import audit, db, leaks
from .reader import MAX_IMAGE_BYTES

log = logging.getLogger("canary.lurker")

MIN_TEXT_CHARS = 200          # text-only posts shorter than this are not papers
BACKFILL = 50                 # messages read from each watched chat on start
MAX_PER_MINUTE = 10           # new leaks accepted per chat per minute
MAX_FLOOD_WAIT = 3600
REFRESH_SECONDS = 20          # how often the listener rereads the list of watched chats
PORTS = (443, 5222, 80)       # Telegram's own ports. Some networks block MTProto on 443 but not on the others
CONNECT_SECONDS = 25
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


class TelegramNotReady(Exception):
    """Telegram cannot be used yet. The message says what the operator should do."""


class ReadOnlyTelegram:
    """The only door to Telegram. Reading calls pass through; anything that could write does not exist here."""

    _ALLOWED = frozenset({"connect", "disconnect", "is_connected", "is_user_authorized", "get_entity", "get_me",
                          "iter_messages", "download_media", "add_event_handler", "remove_event_handler"})

    def __init__(self, client):
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name):
        if name in ReadOnlyTelegram._ALLOWED:
            return getattr(object.__getattribute__(self, "_client"), name)
        raise AttributeError(f"The Telegram account is read-only here: {name!r} is not allowed.")

    def __setattr__(self, name, value):
        raise AttributeError("ReadOnlyTelegram cannot be changed.")

    async def join_public(self, entity) -> None:
        """Join a public channel or group, so its posts can be read. Used only by the `watch` command."""
        from telethon.errors import UserAlreadyParticipantError
        from telethon.tl.functions.channels import JoinChannelRequest
        try:
            await object.__getattribute__(self, "_client")(JoinChannelRequest(entity))
        except UserAlreadyParticipantError:
            pass


def clean_username(text: str) -> str:
    """"@name", "t.me/name" or "https://t.me/name" -> "name". Anything else is refused."""
    name = re.sub(r"^(https?://)?(t\.me/|telegram\.me/)", "", text.strip(), flags=re.I).lstrip("@").strip("/")
    if not _USERNAME.match(name):
        raise TelegramNotReady(f"{text!r} is not a public Telegram username. Use the name after t.me/, such as examleaks_demo.")
    return name


def ports() -> tuple[int, ...]:
    """The ports to try, in order. CANARY_TG_PORT pins one."""
    import os
    pinned = os.environ.get("CANARY_TG_PORT", "").strip()
    if pinned:
        try:
            return (int(pinned),)
        except ValueError:
            raise TelegramNotReady(f"CANARY_TG_PORT must be a port number, not {pinned!r}.") from None
    return PORTS


def connection_on(port: int):
    """A Telethon connection class that always uses this port.

    Every connection Telethon opens goes through this class: the first one, reconnects, and the ones it
    opens when Telegram moves the account to another data centre. So once a port works, it is kept.
    """
    from telethon.network.connection import ConnectionTcpFull
    if port == 443:
        return ConnectionTcpFull

    class OnPort(ConnectionTcpFull):
        def __init__(self, ip, _port, dc_id, **kwargs):
            super().__init__(ip, port, dc_id, **kwargs)

    OnPort.__name__ = f"ConnectionTcpFullOnPort{port}"
    return OnPort


UNREACHABLE = ("Could not reach Telegram from this network on port {ports}. The network may be blocking it. "
               "Try another network, such as a phone hotspot. Typed leaks still work.")


async def connect_any(build):
    """Connect on the first port that works. build(port) returns an unconnected client. Returns (client, port)."""
    tried = ports()
    for port in tried:
        client = build(port)
        try:
            await asyncio.wait_for(client.connect(), CONNECT_SECONDS)
            return client, port
        except (OSError, EOFError, ConnectionError, asyncio.TimeoutError) as exc:   # EOFError: the server cut it off
            log.info("Telegram did not answer on port %s (%s)", port, type(exc).__name__)
            try:
                await client.disconnect()
            except Exception:
                pass
    raise TelegramNotReady(UNREACHABLE.format(ports=" or ".join(str(p) for p in tried)))


def make_client(vault, session: str | None = None, port: int = 443) -> ReadOnlyTelegram:
    """A Telethon client built from the vault's values, with the session kept in memory only."""
    api_id, api_hash = vault.get("tg_api_id"), vault.get("tg_api_hash")
    if not api_id or not api_hash:
        raise TelegramNotReady("Telegram is not set up. Add tg_api_id and tg_api_hash with: python -m canary vault set NAME")
    session = session or vault.get("tg_session")
    if not session:
        raise TelegramNotReady("Telegram is not logged in. Run: python -m canary tg-login")
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    try:
        return ReadOnlyTelegram(TelegramClient(StringSession(session), int(api_id), api_hash,
                                               connection=connection_on(port), connection_retries=1))
    except ValueError:
        raise TelegramNotReady("tg_api_id must be a number, and tg_session must be a session saved by tg-login.") from None


async def _patiently(call, *args, **kwargs):
    """Run one Telegram call. If Telegram says to slow down, wait the stated time and try once more."""
    from telethon.errors import FloodWaitError
    try:
        return await call(*args, **kwargs)
    except FloodWaitError as exc:
        if exc.seconds > MAX_FLOOD_WAIT:
            raise TelegramNotReady(f"Telegram asked this account to wait {exc.seconds // 60} minutes. Try again later.") from None
        log.warning("Telegram asked for a %s second wait", exc.seconds)
        await asyncio.sleep(exc.seconds + 1)
        return await call(*args, **kwargs)


# ---- commands

async def login(vault, ask=input, ask_secret=None) -> str:
    """One-time interactive login. Stores the session string in the vault and returns the account's first name."""
    import getpass
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id, api_hash = vault.get("tg_api_id"), vault.get("tg_api_hash")
    if not api_id or not api_hash:
        raise TelegramNotReady("Add tg_api_id and tg_api_hash first, with: python -m canary vault set NAME")
    from telethon.errors import RPCError
    ask_secret = ask_secret or getpass.getpass
    try:
        api_id = int(api_id)
    except ValueError:
        raise TelegramNotReady("tg_api_id must be the number shown on my.telegram.org.") from None
    client, port = await connect_any(lambda p: TelegramClient(StringSession(), api_id, api_hash,
                                                               connection=connection_on(p), connection_retries=1))
    if port != 443:
        print(f"Reached Telegram on port {port}; this network blocks the usual one.")
    try:
        await client.start(phone=lambda: ask("Phone number, with country code: "),
                           code_callback=lambda: ask("Login code sent by Telegram: "),
                           password=lambda: ask_secret("Two-step password: "))
    except RPCError as exc:
        await client.disconnect()
        raise TelegramNotReady(f"Telegram refused the login: {exc.__class__.__name__}. {exc.message or ''}".strip()) from None
    except (OSError, EOFError, ConnectionError):
        await client.disconnect()
        raise TelegramNotReady("The connection to Telegram dropped during login. Run tg-login again.") from None
    try:
        me = await client.get_me()
        vault.set("tg_session", client.session.save())
        return getattr(me, "first_name", None) or "the account"
    finally:
        await client.disconnect()


async def watch(conn: sqlite3.Connection, vault, username: str, client=None) -> str:
    """Join a public channel or group if needed and add it to watched_chats. Returns its title."""
    name = clean_username(username)
    if client is None:
        make_client(vault)                                     # says what is missing before any network use
        client, _ = await connect_any(lambda port: make_client(vault, port=port))
    else:
        await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramNotReady("Telegram is not logged in. Run: python -m canary tg-login")
        try:
            entity = await _patiently(client.get_entity, name)
        except (ValueError, TypeError):
            raise TelegramNotReady(f"No public channel or group is called {name}.") from None
        if not _is_public_chat(entity):
            raise TelegramNotReady(f"{name} is not a public channel or group. Canary never opens private chats.")
        await _patiently(client.join_public, entity)
        title = str(getattr(entity, "title", name))[:200]
    finally:
        await client.disconnect()
    conn.execute("INSERT INTO watched_chats (username, title, added_at) VALUES (?, ?, ?) "
                 "ON CONFLICT(username) DO UPDATE SET title = excluded.title", (name, title, db.now()))
    conn.commit()
    audit.record(conn, "chat watched", {"username": name})
    return title


def unwatch(conn: sqlite3.Connection, username: str) -> bool:
    """Stop watching a chat. The account stays a member; nothing is sent to Telegram."""
    name = clean_username(username)
    removed = conn.execute("DELETE FROM watched_chats WHERE lower(username) = lower(?)", (name,)).rowcount > 0
    conn.commit()
    if removed:
        audit.record(conn, "chat unwatched", {"username": name})
    return removed


def _is_public_chat(entity) -> bool:
    """A public channel or public group: it has a username and is not a person or a bot."""
    return bool(getattr(entity, "username", None)) and hasattr(entity, "title") and not hasattr(entity, "first_name")


# ---- turning a message into a leak

@dataclass
class Chat:
    id: int
    username: str
    title: str


class RateLimit:
    """At most `limit` new leaks per chat in any 60 seconds."""

    def __init__(self, limit: int = MAX_PER_MINUTE, clock=time.monotonic):
        self.limit, self._clock, self._seen = limit, clock, {}
        self._reported: dict[int, float] = {}
        self.dropped: dict[int, int] = {}                # per chat, since it was last written to the audit log

    def allow(self, chat_id: int) -> bool:
        now = self._clock()
        recent = [t for t in self._seen.get(chat_id, []) if now - t < 60]
        allowed = len(recent) < self.limit
        if allowed:
            recent.append(now)
        else:
            self.dropped[chat_id] = self.dropped.get(chat_id, 0) + 1
        self._seen[chat_id] = recent
        return allowed

    def should_report(self, chat_id: int) -> bool:
        """True at most once a minute per chat, so a flooded chat cannot flood the audit log as well."""
        now = self._clock()
        if chat_id in self._reported and now - self._reported[chat_id] < 60:
            return False
        self._reported[chat_id] = now
        return True


def kind_of(message) -> str | None:
    """What makes this message worth keeping: "photo", "image" (an image sent as a file) or "text". None to ignore."""
    if getattr(message, "photo", None):
        return "photo"
    document = getattr(message, "document", None)
    if document is not None:
        mime, size = str(getattr(document, "mime_type", "") or ""), getattr(document, "size", None)
        if mime.startswith("image/") and isinstance(size, int) and size <= MAX_IMAGE_BYTES:
            return "image"
        return None
    text = getattr(message, "raw_text", None) or getattr(message, "message", None) or ""
    return "text" if len(text) >= MIN_TEXT_CHARS else None


def _short(value, limit: int = 200):
    return str(value)[:limit] if value else None


def leak_row(message, chat: Chat, image_path: str | None, image_sha256: str | None) -> dict:
    """The leaks row for one kept message. Names and text are stored as plain text and never acted on."""
    sender = getattr(message, "sender", None)
    name = " ".join(p for p in (getattr(sender, "first_name", None), getattr(sender, "last_name", None)) if p) \
        or getattr(sender, "title", None)
    posted = getattr(message, "date", None)
    if posted is not None:
        posted = (posted if posted.tzinfo else posted.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    return {
        "source": "telegram", "chat_id": chat.id, "chat_title": _short(chat.title), "chat_username": chat.username,
        "message_id": int(message.id), "message_url": f"https://t.me/{chat.username}/{int(message.id)}",
        "sender_id": getattr(message, "sender_id", None), "sender_username": _short(getattr(sender, "username", None), 64),
        "sender_name": _short(getattr(message, "post_author", None) or name),
        "raw_text": (getattr(message, "raw_text", None) or getattr(message, "message", None) or "")[:leaks.MAX_TEXT_CHARS] or None,
        "image_path": image_path, "image_sha256": image_sha256,
        "posted_at": posted.isoformat(timespec="seconds") if posted else None, "received_at": db.now(),
    }


async def handle_message(conn: sqlite3.Connection, client, message, chat: Chat, limiter: RateLimit | None = None) -> int | None:
    """Keep one message as a queued leak if it looks like a paper. Returns the leak id, or None if it was skipped."""
    if getattr(message, "is_private", False) or kind_of(message) is None:
        return None
    if conn.execute("SELECT 1 FROM leaks WHERE chat_id = ? AND message_id = ?", (chat.id, int(message.id))).fetchone():
        return None                                              # seen before
    if limiter is not None and not limiter.allow(chat.id):
        log.warning("Dropped message %s in %s: more than %s leaks a minute", message.id, chat.username, MAX_PER_MINUTE)
        if limiter.should_report(chat.id):
            audit.record(conn, "leaks dropped, chat too busy", {"chat": chat.username, "first_message_id": int(message.id),
                                                                "limit_per_minute": limiter.limit})
        return None
    image_path = sha = None
    if kind_of(message) in ("photo", "image"):
        data = await _patiently(client.download_media, message, file=bytes)
        try:
            image_path, sha = leaks.save_image(data or b"")
        except leaks.LeakRefused:
            log.warning("Skipped message %s in %s: its file is not a usable image", message.id, chat.username)
            return None
    row = leak_row(message, chat, image_path, sha)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO leaks ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


# ---- listening

@dataclass
class ListenerState:
    """What the status line shows about Telegram."""
    connected: bool = False
    message: str = "Telegram is not set up."
    watching: int = 0


async def _resolve(conn: sqlite3.Connection, client, known: dict[int, Chat]) -> dict[int, Chat]:
    """Look up every watched username. Returns chat id -> Chat, keeping ones already known."""
    from telethon import utils
    wanted = [r["username"] for r in conn.execute("SELECT username FROM watched_chats ORDER BY username")]
    by_name = {c.username.lower(): c for c in known.values()}
    chats = {}
    for name in wanted:
        chat = by_name.get(name.lower())
        if chat is None:
            try:
                entity = await _patiently(client.get_entity, name)
            except (ValueError, TypeError):
                log.warning("Watched chat %s could not be found", name)
                continue
            if not _is_public_chat(entity):
                continue
            chat = Chat(utils.get_peer_id(entity), name, str(getattr(entity, "title", name)))
        chats[chat.id] = chat
    return chats


async def backfill(conn: sqlite3.Connection, client, chat: Chat, on_leak=None) -> int:
    """Read the last 50 messages of one chat through the same path as live ones."""
    kept = 0
    async for message in client.iter_messages(chat.username, limit=BACKFILL):
        leak_id = await handle_message(conn, client, message, chat)
        if leak_id:
            kept += 1
            if on_leak:
                on_leak(leak_id)
    return kept


async def run_listener(conn: sqlite3.Connection, vault, stop: asyncio.Event, on_leak=None,
                       state: ListenerState | None = None, client=None) -> None:
    """Listen to watched chats and insert a queued leak for each kept message, until `stop` is set."""
    state = state or ListenerState()
    fixed = client                                             # tests hand in a fake client; normally it is built here
    if fixed is None:
        try:
            make_client(vault)                                 # says what is missing before any network use
        except TelegramNotReady as exc:
            state.connected, state.message = False, str(exc)
            return
    from telethon import events
    chats: dict[int, Chat] = {}
    limiter = RateLimit()

    async def on_message(event) -> None:
        chat = chats.get(event.chat_id)
        if chat is None or event.is_private:                     # only watched public chats are ever read
            return
        try:
            leak_id = await handle_message(conn, client, event.message, chat, limiter)
        except Exception:                                        # one bad message must not stop the listener
            log.exception("Could not keep message %s", getattr(event.message, "id", "?"))
            return
        if leak_id and on_leak:
            on_leak(leak_id)

    delay = 5
    while not stop.is_set():
        client = fixed
        try:
            if fixed is None:
                client, port = await connect_any(lambda p: make_client(vault, port=p))
            else:
                await client.connect()
                port = 443
            if not await client.is_user_authorized():
                state.connected, state.message = False, "Telegram is not logged in. Run: python -m canary tg-login"
                return
            client.add_event_handler(on_message, events.NewMessage(incoming=True))
            state.connected = True
            state.message = "Telegram connected." if port == 443 else f"Telegram connected on port {port}."
            delay = 5
            done: set[int] = set()
            while not stop.is_set():
                current = await _resolve(conn, client, dict(chats))      # names already looked up are not asked again
                chats.clear()
                chats.update(current)
                state.watching = len(chats)
                for chat in list(chats.values()):
                    if chat.id not in done:
                        done.add(chat.id)
                        await backfill(conn, client, chat, on_leak)
                if not client.is_connected():
                    raise ConnectionError("Telegram disconnected")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=REFRESH_SECONDS)
                except asyncio.TimeoutError:
                    pass
        except TelegramNotReady as exc:
            state.connected, state.message = False, str(exc)
        except Exception as exc:
            log.warning("Telegram listener stopped: %s", type(exc).__name__)
            state.connected, state.message = False, "Telegram is not reachable. Typed leaks still work."
        finally:
            try:
                if client is not None:
                    client.remove_event_handler(on_message)
                    await client.disconnect()
            except Exception:
                pass
        if not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 120)
    state.connected = False
