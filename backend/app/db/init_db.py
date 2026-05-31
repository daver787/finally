"""Lazy database initialization and seed data."""

from __future__ import annotations

import logging
import pathlib
import sqlite3
import uuid
from datetime import datetime, timezone

from .schema import (
    CREATE_CHAT_MESSAGES,
    CREATE_PORTFOLIO_SNAPSHOTS,
    CREATE_POSITIONS,
    CREATE_TRADES,
    CREATE_USERS_PROFILE,
    CREATE_WATCHLIST,
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
)

logger = logging.getLogger(__name__)


def init_db(db_path: str) -> None:
    """Initialize the SQLite database at ``db_path``.

    Creates all six tables (CREATE TABLE IF NOT EXISTS) and seeds the default
    user profile + watchlist if they don't already exist. Safe to call on every
    startup — idempotent.
    """
    # Ensure parent directory exists (e.g., /app/db on a fresh container)
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _create_tables(conn)
        _seed_default_data(conn)
        conn.commit()
    finally:
        conn.close()


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all schema tables. Idempotent via IF NOT EXISTS."""
    for ddl in (
        CREATE_USERS_PROFILE,
        CREATE_WATCHLIST,
        CREATE_POSITIONS,
        CREATE_TRADES,
        CREATE_PORTFOLIO_SNAPSHOTS,
        CREATE_CHAT_MESSAGES,
    ):
        conn.execute(ddl)


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """Seed the default user profile and watchlist tickers.

    Uses INSERT OR IGNORE for the user row and a COUNT() check before seeding
    watchlist tickers, so the function is safe to call repeatedly without
    duplicating rows.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Seed default user (idempotent via INSERT OR IGNORE)
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
    )

    # Seed default watchlist tickers only if none exist for the default user
    existing = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()[0]

    if existing == 0:
        for ticker in DEFAULT_WATCHLIST_TICKERS:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
            )
        logger.info("Seeded %d default watchlist tickers", len(DEFAULT_WATCHLIST_TICKERS))
