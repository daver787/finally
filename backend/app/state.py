"""Process-wide application state and FastAPI dependency functions."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Request

from .market.cache import PriceCache
from .market.interface import MarketDataSource


@dataclass
class AppState:
    """Container for process-wide singletons.

    One instance is created at startup and attached to ``app.state.app_state``.
    Routes access it via FastAPI dependency injection
    (:func:`get_state`, :func:`get_cache`, :func:`get_conn`).
    """

    price_cache: PriceCache
    market_source: MarketDataSource
    db_path: str


def get_state(request: Request) -> AppState:
    """FastAPI dependency: return the process-wide :class:`AppState`."""
    return request.app.state.app_state


def get_cache(state: AppState = Depends(get_state)) -> PriceCache:
    """FastAPI dependency: return the shared :class:`PriceCache`."""
    return state.price_cache


def get_conn(
    state: AppState = Depends(get_state),
) -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a fresh SQLite connection per request.

    The connection's row_factory is set to :class:`sqlite3.Row` so callers can
    use both index and name access on rows. Closed automatically after the
    request completes.

    ``check_same_thread=False`` is required because FastAPI dispatches sync
    route handlers on its own thread pool, and the generator that yields the
    connection may run on a different thread than the handler body. A fresh
    connection per request still gives us per-request isolation; we never
    share the same connection across requests.
    """
    conn = sqlite3.connect(state.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
