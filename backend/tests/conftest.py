"""Shared pytest fixtures.

Pytest-asyncio is configured via pyproject.toml (asyncio_mode=auto).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from app.db.init_db import init_db


@pytest.fixture
def db_path(tmp_path) -> str:
    """Create a fresh, initialized SQLite database in a temp directory."""
    p = tmp_path / "finally_test.db"
    init_db(str(p))
    return str(p)


@pytest.fixture
def db_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Open a sqlite3 connection (Row factory) against the initialized test DB."""
    # check_same_thread=False required for handle_chat which uses
    # asyncio.to_thread (runs DB operations in a thread-pool worker).
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Spin up a fresh FastAPI app with an isolated SQLite DB per test.

    Sets DB_PATH to a temp file BEFORE calling :func:`create_app`, so the
    lifespan creates a clean DB and an isolated PriceCache + simulator. Uses
    ``with TestClient(app)`` to trigger lifespan startup + shutdown.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    # create_app() is the entry point; calling it fresh per fixture instance
    # guarantees no shared state between tests.
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
