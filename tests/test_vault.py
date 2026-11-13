import stat
import sys

import pytest

from canary import config
from canary.vault import Vault, WrongPassphrase

PASSPHRASE = "correct horse battery"


@pytest.fixture
def vault(canary_home):
    config.ensure_home()
    return Vault.create(config.vault_path(), PASSPHRASE, {"gemini_api_key": "g-123"})


def test_round_trip(vault):
    opened = Vault.open(config.vault_path(), PASSPHRASE)
    assert opened.get("gemini_api_key") == "g-123"
    assert len(opened.get("fingerprint_key")) == 64
    assert len(opened.get("signing_key")) == 64
    assert opened.get("fingerprint_key") == vault.get("fingerprint_key")


def test_wrong_passphrase_fails(vault):
    with pytest.raises(WrongPassphrase):
        Vault.open(config.vault_path(), "not the passphrase")


def test_tampered_file_fails(vault):
    path = config.vault_path()
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 1
    path.write_bytes(bytes(blob))
    with pytest.raises(WrongPassphrase):
        Vault.open(path, PASSPHRASE)


def test_secrets_are_not_in_the_file_or_repr(vault):
    blob = config.vault_path().read_bytes()
    assert b"g-123" not in blob
    assert vault.get("fingerprint_key").encode() not in blob
    assert "g-123" not in repr(vault)


def test_set_persists_and_rejects_unknown_names(vault):
    vault.set("tg_api_id", "12345")
    assert Vault.open(config.vault_path(), PASSPHRASE).get("tg_api_id") == "12345"
    with pytest.raises(KeyError):
        vault.set("something_else", "x")


def test_file_is_private_and_create_does_not_overwrite(vault):
    if sys.platform != "win32":
        assert stat.S_IMODE(config.vault_path().stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        Vault.create(config.vault_path(), PASSPHRASE)


def test_check_passphrase(vault):
    assert vault.check(PASSPHRASE)
    assert not vault.check("wrong")
