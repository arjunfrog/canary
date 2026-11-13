import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")     # the app's tests need no screen

from canary import db


@pytest.fixture(autouse=True)
def canary_home(tmp_path, monkeypatch):
    """Every test gets its own empty CANARY_HOME, so nothing touches ~/.canary."""
    monkeypatch.setenv("CANARY_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def conn():
    connection = db.connect()
    yield connection
    connection.close()
