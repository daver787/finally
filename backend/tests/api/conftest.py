"""Shared fixtures for API route tests.

Route handlers depend on three things via ``app.state``:
  * a SQLite connection (per-request, from ``get_conn``)
  * the shared ``PriceCache``
  * the ``AppState`` (for the market source on watchlist add/remove)

These fixtures build a FastAPI app pointed at an isolated temp-file database
with a pre-populated, DETERMINISTIC price cache.

The real ``lifespan`` in ``app.main`` starts a live ``SimulatorDataSource``
(which continuously mutates the price cache — confirmed: AAPL drifts within a
second) and a 30s snapshot loop. That would make trade prices non-deterministic
across tests. So the ``client`` fixture swaps in a no-op lifespan that only runs
``init_db`` and leaves ``market_source`` as ``None``. The pre-filled cache then
holds fixed prices for the whole test.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.main import create_app
from app.market.cache import PriceCache

# Seed prices used to populate the test cache. Mirrors app/market/seed_prices.py
# so trades against the default watchlist have a known price.
TEST_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Path to an isolated, freshly initialized SQLite database file.

    A temp file (not ``:memory:``) is required because route handlers open a
    new connection per request — an in-memory DB would not be shared between
    them. ``init_db`` creates the schema and seeds the default user/watchlist.
    """
    path = tmp_path / "finally_test.db"
    init_db(path)
    return path


@pytest.fixture
def price_cache() -> PriceCache:
    """A PriceCache pre-populated with deterministic prices for the seed tickers.

    Two updates per ticker so ``previous_price`` differs from ``price`` and
    direction/change_percent are meaningful.
    """
    cache = PriceCache()
    for ticker, price in TEST_PRICES.items():
        cache.update(ticker, price)
        cache.update(ticker, price)  # second tick: prev == price, direction flat
    return cache


@asynccontextmanager
async def _test_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """A no-op lifespan for tests: init the DB, skip the simulator/snapshot loop."""
    init_db(app.state.app_state.db_path)
    yield


@pytest.fixture
def client(db_path: Path, price_cache: PriceCache) -> Iterator[TestClient]:
    """A TestClient for an app wired to the isolated DB and pre-filled cache.

    The real lifespan is replaced with ``_test_lifespan`` so the live market
    simulator never runs and the cache holds fixed prices. ``market_source``
    stays ``None`` — watchlist add/remove routes already guard on it.
    """
    app = create_app(db_path=db_path)
    app.router.lifespan_context = _test_lifespan
    app.state.app_state.price_cache = price_cache

    # raise_server_exceptions=True surfaces handler bugs as test failures.
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """A direct SQLite connection to the test DB for asserting on persisted state.

    Use this to verify rows after exercising the API (e.g. that a trade wrote a
    ``trades`` row, that a sold-out position has ``quantity = 0``).
    """
    connection = get_db(db_path)
    try:
        yield connection
    finally:
        connection.close()
