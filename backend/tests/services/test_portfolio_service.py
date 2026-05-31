"""Tests for app.services.portfolio — execute_trade, build_portfolio_summary, record_snapshot."""

from __future__ import annotations

import pytest

from app.db.schema import DEFAULT_USER_ID
from app.market.cache import PriceCache
from app.services.portfolio import (
    TradeError,
    build_portfolio_summary,
    execute_trade,
    record_snapshot,
)


def test_execute_trade_buy_creates_position(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    result = execute_trade(
        ticker="AAPL", side="buy", quantity=2, conn=db_conn, price_cache=cache
    )

    assert result["ticker"] == "AAPL"
    assert result["side"] == "buy"
    assert result["quantity"] == 2
    assert result["price"] == 190.0
    assert abs(result["cash_balance"] - (10000.0 - 380.0)) < 0.001
    assert abs(result["total_value"] - 10000.0) < 0.001

    row = db_conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "AAPL"),
    ).fetchone()
    assert row is not None
    assert float(row["quantity"]) == 2.0
    assert float(row["avg_cost"]) == 190.0

    trade_rows = db_conn.execute(
        "SELECT side FROM trades WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "AAPL"),
    ).fetchall()
    assert len(trade_rows) == 1
    assert trade_rows[0]["side"] == "buy"

    snap_rows = db_conn.execute(
        "SELECT COUNT(*) AS n FROM portfolio_snapshots WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    assert int(snap_rows["n"]) >= 1


def test_execute_trade_buy_weighted_average_cost(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    execute_trade(ticker="AAPL", side="buy", quantity=2, conn=db_conn, price_cache=cache)

    cache.update("AAPL", 200.0)
    execute_trade(ticker="AAPL", side="buy", quantity=2, conn=db_conn, price_cache=cache)

    row = db_conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "AAPL"),
    ).fetchone()
    assert float(row["quantity"]) == 4.0
    assert abs(float(row["avg_cost"]) - 195.0) < 0.001


def test_execute_trade_sell_to_zero_preserves_row(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    execute_trade(ticker="AAPL", side="buy", quantity=1, conn=db_conn, price_cache=cache)

    result = execute_trade(
        ticker="AAPL", side="sell", quantity=1, conn=db_conn, price_cache=cache
    )

    row = db_conn.execute(
        "SELECT quantity FROM positions WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "AAPL"),
    ).fetchone()
    assert row is not None  # row was NOT deleted
    assert float(row["quantity"]) == 0.0
    assert abs(result["cash_balance"] - 10000.0) < 0.001


def test_buy_insufficient_cash_raises(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="AAPL", side="buy", quantity=100, conn=db_conn, price_cache=cache
        )
    assert "insufficient" in str(exc_info.value).lower()


def test_sell_insufficient_shares_raises(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="AAPL", side="sell", quantity=1, conn=db_conn, price_cache=cache
        )
    assert "insufficient" in str(exc_info.value).lower()


def test_unknown_ticker_no_price_raises(db_conn):
    cache = PriceCache()
    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="ZZZZ", side="buy", quantity=1, conn=db_conn, price_cache=cache
        )
    assert "no price" in str(exc_info.value).lower()


def test_build_portfolio_summary_returns_live_valuation(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    execute_trade(ticker="AAPL", side="buy", quantity=2, conn=db_conn, price_cache=cache)

    cache.update("AAPL", 200.0)
    result = build_portfolio_summary(conn=db_conn, price_cache=cache)

    assert abs(result["cash_balance"] - 9620.0) < 0.001
    assert abs(result["total_value"] - 10020.0) < 0.001
    assert isinstance(result["positions"], list)
    assert len(result["positions"]) == 1
    pos = result["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 2.0
    assert pos["avg_cost"] == 190.0
    assert pos["current_price"] == 200.0
    assert abs(pos["unrealized_pnl"] - 20.0) < 0.001
    assert abs(pos["pnl_percent"] - 5.263) < 0.01


def test_record_snapshot_writes_row(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    execute_trade(ticker="AAPL", side="buy", quantity=1, conn=db_conn, price_cache=cache)

    record_snapshot(conn=db_conn, price_cache=cache)
    rows = db_conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at ASC",
        (DEFAULT_USER_ID,),
    ).fetchall()
    assert len(rows) >= 2
    latest = rows[-1]
    assert abs(float(latest["total_value"]) - 10000.0) < 0.01


def test_invalid_side_raises(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="AAPL", side="hold", quantity=1, conn=db_conn, price_cache=cache
        )
    msg = str(exc_info.value).lower()
    assert "hold" in msg or "invalid side" in msg


def test_non_positive_quantity_raises(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="AAPL", side="buy", quantity=0, conn=db_conn, price_cache=cache
        )
    assert "positive" in str(exc_info.value).lower()

    with pytest.raises(TradeError) as exc_info:
        execute_trade(
            ticker="AAPL", side="buy", quantity=-1, conn=db_conn, price_cache=cache
        )
    assert "positive" in str(exc_info.value).lower()
