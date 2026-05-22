"""Shared application state and FastAPI dependencies.

The app holds a single ``PriceCache`` and one ``MarketDataSource`` for the
process lifetime. Routes access them — and a fresh DB connection — through the
dependency functions here.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

from app.db import DEFAULT_DB_PATH, get_db
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource


class AppState:
    """Process-wide singletons wired up at startup.

    ``db_path`` is stored so tests can point the app at an isolated database.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path: str | Path = db_path
        self.price_cache: PriceCache = PriceCache()
        self.market_source: MarketDataSource | None = None


def get_state(request: Request) -> AppState:
    """FastAPI dependency: the AppState attached to the running app."""
    return request.app.state.app_state


def get_cache(request: Request) -> PriceCache:
    """FastAPI dependency: the shared price cache."""
    return request.app.state.app_state.price_cache


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: a per-request SQLite connection, closed on teardown."""
    conn = get_db(request.app.state.app_state.db_path)
    try:
        yield conn
    finally:
        conn.close()
