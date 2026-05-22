"""Tests for schema creation and table structure."""

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


class TestSchemaCreation:
    """The six core tables and their constraints are created by init."""

    def test_all_tables_exist(self, db):
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {r["name"] for r in rows}
        assert EXPECTED_TABLES.issubset(tables)

    def test_indexes_exist(self, db):
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "idx_trades_user_time" in names
        assert "idx_snapshots_user_time" in names
        assert "idx_chat_user_time" in names

    def test_users_profile_columns(self, db):
        cols = {r["name"] for r in db.execute("PRAGMA table_info(users_profile)")}
        assert cols == {"id", "cash_balance", "created_at"}

    def test_watchlist_unique_user_ticker(self, db):
        import pytest

        # PYPL is not in the seeded watchlist, so the first insert succeeds.
        db.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES ('x', 'default', 'PYPL', '2026-01-01')"
        )
        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) "
                "VALUES ('y', 'default', 'PYPL', '2026-01-01')"
            )

    def test_positions_unique_user_ticker(self, db):
        import pytest

        db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES ('p1', 'default', 'TSLA', 5, 250.0, '2026-01-01')"
        )
        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES ('p2', 'default', 'TSLA', 1, 251.0, '2026-01-01')"
            )

    def test_trades_side_check_constraint(self, db):
        import pytest

        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES ('t1', 'default', 'AAPL', 'hold', 1, 190.0, '2026-01-01')"
            )

    def test_chat_role_check_constraint(self, db):
        import pytest

        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
                "VALUES ('c1', 'default', 'system', 'hi', NULL, '2026-01-01')"
            )

    def test_user_id_defaults_to_default(self, db):
        db.execute(
            "INSERT INTO watchlist (id, ticker, added_at) "
            "VALUES ('w1', 'PYPL', '2026-01-01')"
        )
        row = db.execute(
            "SELECT user_id FROM watchlist WHERE id = 'w1'"
        ).fetchone()
        assert row["user_id"] == "default"
