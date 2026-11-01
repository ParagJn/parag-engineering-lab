from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.config import Settings
from app.main import create_app
from app.repos import Store

from ._hermetic import scrub


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch: pytest.MonkeyPatch, tmp_path):
    scrub(monkeypatch, tmp_path / "no-such.env")
    yield
    config.get_settings.cache_clear()


REAL_DATA_DIR = (Path(__file__).resolve().parent.parent / "data").resolve()


@pytest.fixture(autouse=True)
def never_open_the_real_database(monkeypatch: pytest.MonkeyPatch):
    """A test that builds an app WITHOUT `make_settings` gets the default data folder, which is the developer's real database. That happened once
    (2026-10-31): two tests added a project each to it on every run, and the user found twelve strangers in their project list. The audit log is
    append-only, so those could be archived but never deleted. This makes the same mistake fail the test at once, naming the path."""
    real_open = Store.open.__func__

    def guarded(cls, path, *args, **kwargs):
        target = Path(path).resolve()
        if target == REAL_DATA_DIR or REAL_DATA_DIR in target.parents:
            raise AssertionError(
                f"this test opened the REAL database ({target}). Build settings with the make_settings fixture, or pass data_dir=str(tmp_path / 'data'); "
                "never create Settings(_env_file=None, ...) and an app from it directly."
            )
        return real_open(cls, path, *args, **kwargs)

    monkeypatch.setattr(Store, "open", classmethod(guarded))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def make_settings(tmp_path) -> Callable[..., Settings]:
    def build(**overrides) -> Settings:
        # Every app built in a test gets its own throwaway database folder.
        overrides.setdefault("data_dir", str(tmp_path / "data"))
        # And its own recordings folder, so no test can read or write the real backend/recordings.
        overrides.setdefault("recordings_dir", str(tmp_path / "recordings"))
        return Settings(_env_file=None, **overrides)

    return build


@pytest.fixture
def clock() -> Callable[[], str]:
    """Deterministic, strictly increasing timestamps: 00:00:00.001Z, .002Z, ..."""
    ticks = itertools.count(1)

    def now() -> str:
        n = next(ticks)
        return f"2026-01-01T{n // 3600000:02d}:{n // 60000 % 60:02d}:{n // 1000 % 60:02d}.{n % 1000:03d}Z"

    return now


@pytest.fixture
def store(tmp_path, clock) -> Store:
    counter = itertools.count(1)
    return Store.open(tmp_path / "store" / "test.db", clock=clock, id_factory=lambda: f"p{next(counter):03d}")


@pytest.fixture
def project(store):
    return store.projects.create(name="Room Booking", actor="human:tester")


@pytest.fixture
def client(make_settings) -> TestClient:
    return TestClient(create_app(make_settings()))
