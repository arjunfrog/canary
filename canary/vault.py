"""The vault: every secret in one file, encrypted under a passphrase.

vault.bin = magic + salt + nonce + AES-256-GCM(JSON of secrets). The key comes from
the passphrase through scrypt. Secrets exist in memory only after unlock and are
never written anywhere else, printed or logged.
"""
import json
import os
import secrets as pysecrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"CNRY1"
SALT_LEN, NONCE_LEN = 16, 12
SECRET_NAMES = ("fingerprint_key", "signing_key", "tg_api_id", "tg_api_hash", "tg_session")
OBSOLETE = ("gemini_api_key",)        # photos are read on the Mac now; an old key is erased from the vault on unlock
GENERATED = ("fingerprint_key", "signing_key")


class WrongPassphrase(Exception):
    pass


def _key(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())


def new_keys() -> dict:
    """A fresh fingerprint key and Ed25519 signing key, both as hex."""
    signing = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return {"fingerprint_key": pysecrets.token_hex(32), "signing_key": signing.hex()}


class Vault:
    def __init__(self, path: Path, key: bytes, salt: bytes, secrets: dict):
        self.path, self._key, self._salt, self._secrets = path, key, salt, secrets   # the passphrase itself is not kept

    @classmethod
    def create(cls, path: Path, passphrase: str, secrets: dict | None = None) -> "Vault":
        if path.exists():
            raise FileExistsError(f"{path} already exists")
        unknown = set(secrets or {}) - set(SECRET_NAMES)
        if unknown:
            raise KeyError(f"unknown secret {sorted(unknown)[0]!r}; expected one of {', '.join(SECRET_NAMES)}")
        salt = os.urandom(SALT_LEN)
        vault = cls(path, _key(passphrase, salt), salt, {**new_keys(), **(secrets or {})})
        vault.save()
        return vault

    @classmethod
    def open(cls, path: Path, passphrase: str) -> "Vault":
        blob = path.read_bytes()
        if not blob.startswith(MAGIC):
            raise ValueError(f"{path} is not a Canary vault")
        body = blob[len(MAGIC):]
        salt, nonce, sealed = body[:SALT_LEN], body[SALT_LEN:SALT_LEN + NONCE_LEN], body[SALT_LEN + NONCE_LEN:]
        key = _key(passphrase, salt)
        try:
            plain = AESGCM(key).decrypt(nonce, sealed, MAGIC)
        except InvalidTag:
            raise WrongPassphrase("wrong passphrase, or the vault file was changed") from None
        vault = cls(path, key, salt, json.loads(plain))
        if any(name in vault._secrets for name in OBSOLETE):
            for name in OBSOLETE:
                vault._secrets.pop(name, None)
            vault.save()                                   # rewritten without it, under the same passphrase
        return vault

    def get(self, name: str) -> str | None:
        return self._secrets.get(name)

    def set(self, name: str, value: str) -> None:
        if name not in SECRET_NAMES:
            raise KeyError(f"unknown secret {name!r}; expected one of {', '.join(SECRET_NAMES)}")
        self._secrets[name] = value
        self.save()

    def names(self) -> list[str]:
        """Which secrets are filled in. Never returns values."""
        return sorted(k for k, v in self._secrets.items() if v)

    def check(self, passphrase: str) -> bool:
        """True if this is the vault's passphrase. Used to unlock an idle dashboard."""
        return pysecrets.compare_digest(_key(passphrase, self._salt), self._key)

    def save(self) -> None:
        nonce = os.urandom(NONCE_LEN)                      # a new nonce for every write
        sealed = AESGCM(self._key).encrypt(nonce, json.dumps(self._secrets).encode(), MAGIC)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(MAGIC + self._salt + nonce + sealed)
        os.replace(tmp, self.path)

    def __repr__(self) -> str:
        return f"<Vault {self.path.name}: {len(self.names())} secrets>"
