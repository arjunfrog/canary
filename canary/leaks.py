"""Adding a leak by hand: pasted text or an image file. This is how a leak is analysed with no network."""
import hashlib
import os
import sqlite3
from pathlib import Path

from . import audit, config, db
from .reader import MAX_IMAGE_BYTES, image_type

MAX_TEXT_CHARS = 400_000
EXTENSION = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class LeakRefused(ValueError):
    """The text or file cannot be taken as a leak. The message is worded for the person using the app."""


def save_image(data: bytes) -> tuple[str, str]:
    """Keep a leak image in CANARY_HOME/leaks under its own hash. Returns (path, sha256).

    The file type comes from the image's first bytes, never from a file name, and only JPEG, PNG and
    WebP are kept.
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise LeakRefused("That image is larger than 10 MB.")
    kind = image_type(data)
    if kind is None:
        raise LeakRefused("That file is not a JPEG, PNG or WebP image.")
    config.ensure_home()
    sha = hashlib.sha256(data).hexdigest()
    dest = config.home() / "leaks" / f"{sha[:32]}{EXTENSION[kind]}"
    fd = os.open(dest, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return str(dest), sha


def add_manual_leak(conn: sqlite3.Connection, text: str | None = None, image_path: str | Path | None = None) -> int:
    """Queue a leak typed, pasted or dropped in by the operator. Returns the new leak's id."""
    if bool(text and text.strip()) == bool(image_path):
        raise LeakRefused("Give either some text or one image.")
    stored = sha = None
    if image_path:
        try:
            if Path(image_path).stat().st_size > MAX_IMAGE_BYTES:
                raise LeakRefused("That image is larger than 10 MB.")
            data = Path(image_path).read_bytes()
        except PermissionError:
            raise LeakRefused("macOS did not let Canary open that file. It probably belongs to another app, such as "
                              "Messages or Photos. Save it to Downloads or the Desktop first, then choose it from there.") from None
        except FileNotFoundError:
            raise LeakRefused("That file is no longer there. If it came from another app, save it to Downloads or "
                              "the Desktop first, then choose it from there.") from None
        except OSError as exc:
            raise LeakRefused(f"That file could not be opened ({exc.strerror or type(exc).__name__}).") from None
        stored, sha = save_image(data)
    else:
        text = text[:MAX_TEXT_CHARS]
    now = db.now()
    cur = conn.execute(
        "INSERT INTO leaks (source, raw_text, image_path, image_sha256, posted_at, received_at) VALUES ('manual', ?, ?, ?, ?, ?)",
        (text if not image_path else None, stored, sha, now, now))
    conn.commit()
    audit.record(conn, "leak added by hand", {"leak_id": cur.lastrowid, "kind": "image" if image_path else "text"})
    return cur.lastrowid
