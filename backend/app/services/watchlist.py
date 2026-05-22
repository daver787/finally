"""Watchlist business logic: read, add, remove tickers."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db.schema import DEFAULT_USER_ID
from app.market.cache import PriceCache


class WatchlistError(Exception):
    """Raised on watchlist validation failures (duplicate, not found)."""


class TickerNotFound(WatchlistError):
    """Raised when removing a ticker that is not on the watchlist."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_watchlist(conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return the watchlist enriched with live prices from the cache.

    Each entry: ``{ticker, price, prev_price, change_pct}``. Tickers without a
    cached price yet (just added) report nulls until the next stream tick.
    """
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (user_id,),
    ).fetchall()

    result: list[dict] = []
    for row in rows:
        ticker = row["ticker"]
        update = cache.get(ticker)
        if update is None:
            result.append(
                {"ticker": ticker, "price": None, "prev_price": None, "change_pct": None}
            )
        else:
            result.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "prev_price": update.previous_price,
                    "change_pct": update.change_percent,
                }
            )
    return result


def add_ticker(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Add a ticker to the watchlist. Commits on success.

    Raises ``WatchlistError`` if the ticker is already present or invalid.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise WatchlistError("Ticker must not be empty")

    existing = conn.execute(
        "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    if existing is not None:
        raise WatchlistError(f"{ticker} is already on the watchlist")

    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, ticker, _utc_now_iso()),
    )
    conn.commit()


def remove_ticker(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Remove a ticker from the watchlist. Commits on success.

    Raises ``TickerNotFound`` if the ticker is not on the watchlist.
    """
    ticker = ticker.upper().strip()
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    if cur.rowcount == 0:
        raise TickerNotFound(f"{ticker} is not on the watchlist")
    conn.commit()


def get_watchlist_tickers(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Return just the list of ticker symbols on the watchlist."""
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (user_id,),
    ).fetchall()
    return [r["ticker"] for r in rows]
