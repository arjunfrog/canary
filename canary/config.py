"""Where things live, and the few fixed settings.

All runtime data sits under CANARY_HOME (default ~/.canary), never in the repo.
Directories are created 0700 and files 0600. Windows ignores these modes, so there the
protection is the user's own profile folder plus the vault's encryption.
"""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
BANK_DB = PACKAGE_DIR / "data" / "bank.db"      # read-only question bank
SCHEMA_SQL = PACKAGE_DIR / "schema.sql"

IDLE_LOCK_SECONDS = 600                        # the app locks after this long with no key or mouse activity

EXAM_ID = 1                                    # one exam per installation
N_TRANSLATORS = 50
N_PRINT_COPIES = 5000
TRAPS_PER_TRANSLATOR = 6

SUBDIRS = ("leaks", "copies", "evidence", "cache", "replay")


def home() -> Path:
    return Path(os.environ.get("CANARY_HOME", Path.home() / ".canary"))


def ensure_home() -> Path:
    root = home()
    for d in (root, *(root / s for s in SUBDIRS)):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
    return root


def db_path() -> Path:
    return home() / "canary.db"


def vault_path() -> Path:
    return home() / "vault.bin"
