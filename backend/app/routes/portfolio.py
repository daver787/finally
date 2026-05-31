"""Portfolio REST endpoints — GET /, POST /trade, GET /history under /api/portfolio."""

from __future__ import annotations

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db.schema import DEFAULT_USER_ID
from ..market.cache import PriceCache
from ..state import get_cache, get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    """Request body for POST /api/portfolio/trade."""

    ticker: Annotated[str, Field(max_length=10)]
    side: Annotated[str, Field(pattern="^(buy|sell)$")]
    quantity: Annotated[float, Field(gt=0)]


@router.get("")
def get_portfolio(
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """GET /api/portfolio — return cash, total value, and live position valuation.

    Sync handler so FastAPI runs it in a thread-pool worker. Calling a
    blocking SQLite function from an ``async def`` handler would freeze the
    event loop on any lock contention.
    """
    from ..services.portfolio import build_portfolio_summary

    return build_portfolio_summary(conn=conn, price_cache=cache)


@router.post("/trade")
def execute_trade_endpoint(
    body: TradeRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """POST /api/portfolio/trade — execute a market order at current PriceCache price.

    Sync handler (thread-pool) so multi-step SQLite writes never block the
    event loop. Pydantic validates side/quantity before the service sees the
    request (422 on violation). TradeError maps to 400.
    """
    from ..services.portfolio import TradeError, execute_trade

    ticker = body.ticker.upper().strip()
    try:
        return execute_trade(
            ticker=ticker,
            side=body.side,
            quantity=body.quantity,
            conn=conn,
            price_cache=cache,
        )
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history")
def get_history(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    """GET /api/portfolio/history — chronological portfolio_snapshots for the P&L chart."""
    rows = conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots "
        "WHERE user_id = ? ORDER BY recorded_at ASC LIMIT 1000",
        (DEFAULT_USER_ID,),
    ).fetchall()
    return [
        {"total_value": float(r["total_value"]), "recorded_at": r["recorded_at"]}
        for r in rows
    ]
