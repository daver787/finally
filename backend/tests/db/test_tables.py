"""Tests for table-level behavior: positions, trades, snapshots, chat messages."""

import json
import uuid


def _new_id() -> str:
    return str(uuid.uuid4())


class TestPositionsNeverDeleted:
    """A full sell sets quantity=0; the position row is never removed."""

    def test_buy_creates_position_row(self, db):
        db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', 'AAPL', 10, 190.0, '2026-01-01')",
            (_new_id(),),
        )
        row = db.execute(
            "SELECT quantity FROM positions WHERE ticker = 'AAPL'"
        ).fetchone()
        assert row["quantity"] == 10

    def test_full_sell_sets_quantity_zero_not_delete(self, db):
        pos_id = _new_id()
        db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', 'TSLA', 5, 250.0, '2026-01-01')",
            (pos_id,),
        )
        # Selling everything: update quantity to 0, do NOT delete the row.
        db.execute(
            "UPDATE positions SET quantity = 0, updated_at = '2026-01-02' WHERE id = ?",
            (pos_id,),
        )
        rows = db.execute(
            "SELECT * FROM positions WHERE ticker = 'TSLA'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["quantity"] == 0

    def test_rebuy_updates_existing_zero_row(self, db):
        pos_id = _new_id()
        db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', 'NVDA', 0, 800.0, '2026-01-01')",
            (pos_id,),
        )
        db.execute(
            "UPDATE positions SET quantity = 3, avg_cost = 810.0, updated_at = '2026-01-03' "
            "WHERE user_id = 'default' AND ticker = 'NVDA'",
        )
        rows = db.execute(
            "SELECT * FROM positions WHERE ticker = 'NVDA'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["quantity"] == 3
        assert rows[0]["avg_cost"] == 810.0

    def test_fractional_quantity_supported(self, db):
        db.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', 'MSFT', 2.5, 420.25, '2026-01-01')",
            (_new_id(),),
        )
        row = db.execute(
            "SELECT quantity, avg_cost FROM positions WHERE ticker = 'MSFT'"
        ).fetchone()
        assert row["quantity"] == 2.5
        assert row["avg_cost"] == 420.25


class TestTradesAppendOnly:
    """The trades table is an append-only log of executed orders."""

    def test_insert_trade(self, db):
        trade_id = _new_id()
        db.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, 'default', 'AAPL', 'buy', 10, 190.0, '2026-01-01T10:00:00')",
            (trade_id,),
        )
        row = db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        assert row["side"] == "buy"
        assert row["quantity"] == 10
        assert row["price"] == 190.0

    def test_multiple_trades_same_ticker_all_retained(self, db):
        for side, qty, price in [
            ("buy", 10, 190.0),
            ("buy", 5, 192.0),
            ("sell", 3, 195.0),
        ]:
            db.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, 'default', 'AAPL', ?, ?, ?, '2026-01-01')",
                (_new_id(), side, qty, price),
            )
        rows = db.execute(
            "SELECT * FROM trades WHERE ticker = 'AAPL'"
        ).fetchall()
        assert len(rows) == 3

    def test_trades_ordered_by_executed_at(self, db):
        for ts in ["2026-01-03", "2026-01-01", "2026-01-02"]:
            db.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, 'default', 'V', 'buy', 1, 280.0, ?)",
                (_new_id(), ts),
            )
        rows = db.execute(
            "SELECT executed_at FROM trades ORDER BY executed_at"
        ).fetchall()
        assert [r["executed_at"] for r in rows] == [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
        ]

    def test_sell_trade_supports_fractional_quantity(self, db):
        db.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, 'default', 'GOOGL', 'sell', 1.25, 175.5, '2026-01-01')",
            (_new_id(),),
        )
        row = db.execute(
            "SELECT quantity FROM trades WHERE ticker = 'GOOGL'"
        ).fetchone()
        assert row["quantity"] == 1.25


class TestPortfolioSnapshots:
    """Portfolio value snapshots can be inserted and queried over time."""

    def test_insert_and_query_snapshot(self, db):
        snap_id = _new_id()
        db.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, 'default', 10500.0, '2026-01-01T12:00:00')",
            (snap_id,),
        )
        row = db.execute(
            "SELECT * FROM portfolio_snapshots WHERE id = ?", (snap_id,)
        ).fetchone()
        assert row["total_value"] == 10500.0

    def test_snapshots_ordered_chronologically(self, db):
        values = [(10000.0, "2026-01-01"), (10250.0, "2026-01-02"), (9800.0, "2026-01-03")]
        for total, ts in values:
            db.execute(
                "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
                "VALUES (?, 'default', ?, ?)",
                (_new_id(), total, ts),
            )
        rows = db.execute(
            "SELECT total_value FROM portfolio_snapshots ORDER BY recorded_at"
        ).fetchall()
        assert [r["total_value"] for r in rows] == [10000.0, 10250.0, 9800.0]


class TestChatMessages:
    """Chat messages store role, content, and an optional JSON actions blob."""

    def test_insert_user_message_with_null_actions(self, db):
        msg_id = _new_id()
        db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, 'default', 'user', 'What is my P&L?', NULL, '2026-01-01')",
            (msg_id,),
        )
        row = db.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        assert row["role"] == "user"
        assert row["content"] == "What is my P&L?"
        assert row["actions"] is None

    def test_insert_assistant_message_with_json_actions(self, db):
        actions = {
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            "watchlist_changes": [],
        }
        msg_id = _new_id()
        db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, 'default', 'assistant', 'Bought 1 AAPL.', ?, '2026-01-01')",
            (msg_id, json.dumps(actions)),
        )
        row = db.execute(
            "SELECT actions FROM chat_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        parsed = json.loads(row["actions"])
        assert parsed == actions

    def test_messages_ordered_by_created_at(self, db):
        for ts, content in [
            ("2026-01-01T09:00", "first"),
            ("2026-01-01T09:01", "second"),
            ("2026-01-01T09:02", "third"),
        ]:
            db.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
                "VALUES (?, 'default', 'user', ?, NULL, ?)",
                (_new_id(), content, ts),
            )
        rows = db.execute(
            "SELECT content FROM chat_messages ORDER BY created_at"
        ).fetchall()
        assert [r["content"] for r in rows] == ["first", "second", "third"]
