"""The Telegram listener: an ordinary account that reads watched public chats and saves paper-like posts.

To build (task 7 in docs/PROMPTS.md), with Telethon. It never sends, replies, reacts,
marks as read or opens private chats.
"""
import asyncio
import sqlite3


async def login(vault) -> None:
    """One-time interactive login. Stores the session string in the vault."""
    raise NotImplementedError("task 7: tg-login")


async def watch(conn: sqlite3.Connection, vault, username: str) -> None:
    raise NotImplementedError("task 7: watch")


async def run_listener(conn: sqlite3.Connection, vault, stop: asyncio.Event) -> None:
    """Listen to watched chats and insert a queued leak for each kept message."""
    raise NotImplementedError("task 7: run_listener")
