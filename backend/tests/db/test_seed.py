"""Tests for seed data and idempotent initialization."""

import sqlite3
import tempfile
from pathlib import Path

from app.db import DEFAULT_WATCHLIST, get_db, init_db, init_db_conn


class TestSeedData:
    """The default user and watchlist are seeded on first init."""

    def test_default_user_seeded(self, db):
        rows = db.execute("SELECT * FROM users_profile").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == "default"
        assert rows[0]["cash_balance"] == 10000.0
        assert rows[0]["created_at"]

    def test_watchlist_has_ten_entries(self, db):
        rows = db.execute("SELECT ticker FROM watchlist").fetchall()
        assert len(rows) == 10
        assert {r["ticker"] for r in rows} == set(DEFAULT_WATCHLIST)

    def test_watchlist_entries_have_uuid_ids(self, db):
        rows = db.execute("SELECT id FROM watchlist").fetchall()
        ids = {r["id"] for r in rows}
        assert len(ids) == 10  # all unique
        for entry_id in ids:
            assert len(entry_id) == 36  # canonical UUID string length

    def test_no_positions_or_trades_seeded(self, db):
        assert db.execute("SELECT COUNT(*) n FROM positions").fetchone()["n"] == 0
        assert db.execute("SELECT COUNT(*) n FROM trades").fetchone()["n"] == 0


class TestIdempotency:
    """Re-initializing must never duplicate or overwrite seed data."""

    def test_init_db_conn_twice_no_duplicates(self, db):
        # The `db` fixture already called init_db_conn once.
        init_db_conn(db)
        assert db.execute("SELECT COUNT(*) n FROM users_profile").fetchone()["n"] == 1
        assert db.execute("SELECT COUNT(*) n FROM watchlist").fetchone()["n"] == 10

    def test_init_db_file_twice_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "finally.db"
            init_db(db_path)
            init_db(db_path)
            conn = get_db(db_path)
            try:
                users = conn.execute("SELECT COUNT(*) n FROM users_profile").fetchone()
                watch = conn.execute("SELECT COUNT(*) n FROM watchlist").fetchone()
            finally:
                conn.close()
            assert users["n"] == 1
            assert watch["n"] == 10

    def test_init_db_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "nested" / "dir" / "finally.db"
            init_db(db_path)
            assert db_path.exists()

    def test_existing_data_not_overwritten_on_reinit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "finally.db"
            init_db(db_path)
            conn = get_db(db_path)
            conn.execute(
                "UPDATE users_profile SET cash_balance = 500.0 WHERE id = 'default'"
            )
            conn.commit()
            conn.close()

            init_db(db_path)  # must not reseed over the modified balance

            conn = get_db(db_path)
            try:
                balance = conn.execute(
                    "SELECT cash_balance FROM users_profile WHERE id = 'default'"
                ).fetchone()["cash_balance"]
            finally:
                conn.close()
            assert balance == 500.0


class TestGetDb:
    """get_db produces a usable, correctly configured connection."""

    def test_returns_connection_with_row_factory(self):
        conn = get_db(":memory:")
        try:
            assert conn.row_factory is sqlite3.Row
        finally:
            conn.close()

    def test_foreign_keys_enabled(self):
        conn = get_db(":memory:")
        try:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1
        finally:
            conn.close()
