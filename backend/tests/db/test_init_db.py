"""Tests for app.db.init_db — schema creation and seed data."""

from __future__ import annotations

import sqlite3

import pytest

from app.db.init_db import init_db
from app.db.schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
)

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def _all_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def test_init_db_creates_all_six_tables(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))

    conn = sqlite3.connect(str(p))
    try:
        tables = _all_tables(conn)
    finally:
        conn.close()

    assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"


def test_init_db_seeds_default_user(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))

    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, cash_balance FROM users_profile").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["id"] == DEFAULT_USER_ID
    assert rows[0]["cash_balance"] == DEFAULT_CASH_BALANCE


def test_init_db_seeds_default_watchlist(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))

    conn = sqlite3.connect(str(p))
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        ).fetchall()
    finally:
        conn.close()

    tickers = {r[0] for r in rows}
    assert tickers == set(DEFAULT_WATCHLIST_TICKERS)
    assert len(rows) == 10


def test_init_db_is_idempotent(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))
    init_db(str(p))  # second call MUST NOT duplicate seed data or raise

    conn = sqlite3.connect(str(p))
    try:
        user_count = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0]
        watch_count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    finally:
        conn.close()

    assert user_count == 1
    assert watch_count == 10


def test_watchlist_has_unique_user_ticker(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))

    conn = sqlite3.connect(str(p))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                ("dup-id", DEFAULT_USER_ID, "AAPL", "2026-01-01T00:00:00+00:00"),
            )
            conn.commit()
    finally:
        conn.close()


def test_positions_has_unique_user_ticker(tmp_path):
    p = tmp_path / "test.db"
    init_db(str(p))

    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", DEFAULT_USER_ID, "AAPL", 10.0, 190.0, "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("p2", DEFAULT_USER_ID, "AAPL", 5.0, 200.0, "2026-01-01T00:00:00+00:00"),
            )
            conn.commit()
    finally:
        conn.close()
