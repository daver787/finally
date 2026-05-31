"""Watchlist service — DB CRUD and price enrichment."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from ..db.schema import DEFAULT_USER_ID
from ..market.cache import PriceCache

logger = logging.getLogger(__name__)


class WatchlistError(Exception):
    """Raised on invalid watchlist operations (e.g., duplicate ticker)."""


def get_watchlist(conn: sqlite3.Connection, price_cache: PriceCache) -> list[dict]:
    """Return all watchlist entries for the default user, enriched with live prices.

    If :class:`PriceCache` has no price for a ticker yet, price-related fields
    are ``None`` — the caller (route layer) renders these as placeholders.
    """
    rows = conn.execute(
        "SELECT id, ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (DEFAULT_USER_ID,),
    ).fetchall()

    result: list[dict] = []
    for row in rows:
        ticker = row["ticker"]
        update = price_cache.get(ticker)
        result.append(
            {
                "id": row["id"],
                "ticker": ticker,
                "added_at": row["added_at"],
                "price": update.price if update else None,
                "previous_price": update.previous_price if update else None,
                "change_percent": update.change_percent if update else None,
                "direction": update.direction if update else None,
            }
        )
    return result


def add_ticker(ticker: str, conn: sqlite3.Connection, price_cache: PriceCache) -> dict:
    """Add a ticker to the watchlist.

    Trusts that the caller (route layer) has already normalized ``ticker`` via
    ``.upper().strip()``. Raises :class:`WatchlistError` on a duplicate add
    (UNIQUE(user_id, ticker)).
    """
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (entry_id, DEFAULT_USER_ID, ticker, now),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise WatchlistError(f"Ticker {ticker!r} already in watchlist") from exc

    logger.info("Added %s to watchlist", ticker)
    # `price_cache` is part of the signature so the route layer can pass it
    # through and we can extend enrichment in future plans. Currently the cache
    # is not mutated here — market_source.add_ticker handles cache priming.
    _ = price_cache
    return {"id": entry_id, "ticker": ticker, "added_at": now}


def remove_ticker(ticker: str, conn: sqlite3.Connection) -> None:
    """Delete a ticker from the watchlist.

    No-op if the ticker is not present (deleting zero rows does not raise).
    """
    conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, ticker),
    )
    conn.commit()
    logger.info("Removed %s from watchlist", ticker)
