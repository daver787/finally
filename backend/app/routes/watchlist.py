"""Watchlist REST endpoints — GET/POST/DELETE under /api/watchlist."""

from __future__ import annotations

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..market.cache import PriceCache
from ..services.watchlist import (
    WatchlistError,
    add_ticker,
    get_watchlist,
    remove_ticker,
)
from ..state import AppState, get_cache, get_conn, get_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    """Request body for ``POST /api/watchlist``."""

    ticker: Annotated[str, Field(max_length=10)]


@router.get("")
async def list_watchlist(
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> list[dict]:
    """GET /api/watchlist — return all watched tickers with latest prices."""
    return get_watchlist(conn=conn, price_cache=cache)


@router.post("", status_code=201)
async def add_to_watchlist(
    body: AddTickerRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
    state: AppState = Depends(get_state),
) -> dict:
    """POST /api/watchlist — add a ticker. Returns 400 on duplicate."""
    ticker = body.ticker.upper().strip()
    try:
        result = add_ticker(ticker=ticker, conn=conn, price_cache=cache)
    except WatchlistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await state.market_source.add_ticker(ticker)
    return result


@router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(
    ticker: str,
    conn: sqlite3.Connection = Depends(get_conn),
    state: AppState = Depends(get_state),
) -> None:
    """DELETE /api/watchlist/{ticker} — remove a ticker. 204 on success.

    Idempotent: deleting a non-existent ticker still returns 204.
    """
    remove_ticker(ticker=ticker.upper().strip(), conn=conn)
    await state.market_source.remove_ticker(ticker.upper().strip())
    return None
