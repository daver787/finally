"""Tests for app.services.watchlist and app.state.AppState."""

from __future__ import annotations

import pytest

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
from app.services.watchlist import (
    WatchlistError,
    add_ticker,
    get_watchlist,
    remove_ticker,
)
from app.state import AppState


def test_appstate_holds_price_cache_and_source():
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache)
    state = AppState(price_cache=cache, market_source=source, db_path="x")

    assert state.price_cache is cache
    assert state.market_source is source
    assert state.db_path == "x"


def test_get_watchlist_returns_seeded_tickers_with_null_prices(db_conn):
    cache = PriceCache()
    entries = get_watchlist(conn=db_conn, price_cache=cache)

    assert len(entries) == 10
    for entry in entries:
        assert entry["price"] is None
        assert entry["previous_price"] is None
        assert entry["change_percent"] is None
        assert entry["direction"] is None


def test_get_watchlist_enriches_with_cache_prices(db_conn):
    cache = PriceCache()
    cache.update("AAPL", 190.5)
    cache.update("AAPL", 191.0)

    entries = get_watchlist(conn=db_conn, price_cache=cache)
    aapl = next(e for e in entries if e["ticker"] == "AAPL")

    assert aapl["price"] == 191.0
    assert aapl["previous_price"] == 190.5
    assert aapl["direction"] == "up"
    assert aapl["change_percent"] is not None
    assert aapl["change_percent"] > 0


def test_add_ticker_inserts_and_returns_entry(db_conn):
    cache = PriceCache()
    result = add_ticker("PYPL", conn=db_conn, price_cache=cache)

    assert result["ticker"] == "PYPL"
    assert "id" in result
    assert "added_at" in result

    entries = get_watchlist(conn=db_conn, price_cache=cache)
    assert len(entries) == 11
    assert any(e["ticker"] == "PYPL" for e in entries)


def test_add_ticker_duplicate_raises_watchlist_error(db_conn):
    cache = PriceCache()
    add_ticker("PYPL", conn=db_conn, price_cache=cache)

    with pytest.raises(WatchlistError) as exc_info:
        add_ticker("PYPL", conn=db_conn, price_cache=cache)
    assert "PYPL" in str(exc_info.value)


def test_remove_ticker_deletes_row(db_conn):
    cache = PriceCache()
    remove_ticker("AAPL", conn=db_conn)

    entries = get_watchlist(conn=db_conn, price_cache=cache)
    assert len(entries) == 9
    assert not any(e["ticker"] == "AAPL" for e in entries)


def test_remove_ticker_missing_is_noop(db_conn):
    # ZZZZ is not in the seeded watchlist; should silently no-op
    remove_ticker("ZZZZ", conn=db_conn)
    cache = PriceCache()
    entries = get_watchlist(conn=db_conn, price_cache=cache)
    assert len(entries) == 10
