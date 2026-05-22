"""Shared fixtures for database-layer tests."""

import sqlite3

import pytest

from app.db import init_db_conn


@pytest.fixture
def db() -> sqlite3.Connection:
    """An in-memory SQLite database with schema created and default data seeded.

    A single connection is yielded so the in-memory database survives for the
    whole test; it is closed on teardown.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db_conn(conn)
    yield conn
    conn.close()
