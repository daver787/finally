"""Database connection and lazy initialization for FinAlly.

The backend never runs an explicit migration step. ``init_db`` creates the
schema and seeds default data on first use; calling it again is a no-op.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    INDEX_STATEMENTS,
    SCHEMA_STATEMENTS,
)

# Project root is three parents up from this file: app/db/init_db.py -> backend/ -> finally/
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def get_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection.

    Returns a connection with ``row_factory`` set to ``sqlite3.Row`` (so rows
    behave like dicts) and foreign-key enforcement enabled. The caller owns the
    connection and is responsible for closing it.

    ``db_path`` may be ``":memory:"`` for tests. For file-backed databases the
    parent directory is created if missing.

    ``check_same_thread=False``: FastAPI runs sync route handlers in a thread
    pool, so a connection opened in a dependency may be used by a different
    worker thread. Each connection is still confined to a single request, so
    SQLite's own serialization keeps this safe.
    """
    if db_path != ":memory:":
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        db_path = str(path)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create all tables (IF NOT EXISTS) and seed default data if empty.

    Idempotent: safe to call on every startup. Seeding only happens when the
    ``users_profile`` table has no rows, so existing data is never overwritten.
    """
    conn = get_db(db_path)
    try:
        _create_schema(conn)
        _seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def init_db_conn(conn: sqlite3.Connection) -> None:
    """Initialize schema and seed data on an already-open connection.

    Useful for in-memory test databases where a single connection must persist
    for the lifetime of the database. Does not commit or close the connection.
    """
    _create_schema(conn)
    _seed_if_empty(conn)


def _create_schema(conn: sqlite3.Connection) -> None:
    """Run every CREATE TABLE / CREATE INDEX statement."""
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """Insert the default user and watchlist if no user profile exists."""
    row = conn.execute("SELECT COUNT(*) AS n FROM users_profile").fetchone()
    if row["n"] > 0:
        return

    now = _utc_now_iso()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )
    conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now)
            for ticker in DEFAULT_WATCHLIST
        ],
    )
