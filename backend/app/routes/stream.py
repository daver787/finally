"""SSE streaming route for live price updates.

Unlike the generic stream in ``app.market.stream`` (which pushes every cached
ticker), this route restricts the payload to tickers on the user's watchlist,
per PLAN.md §6. Positions removed from the watchlist stop receiving updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.services.watchlist import get_watchlist_tickers
from app.state import AppState, get_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])

# How often the stream re-reads the watchlist and pushes prices.
_STREAM_INTERVAL = 0.5


@router.get("/prices")
async def stream_prices(
    request: Request,
    state: AppState = Depends(get_state),
) -> StreamingResponse:
    """SSE endpoint pushing watchlist price updates every ~500ms.

    Each event payload is a JSON object keyed by ticker:

        data: {"AAPL": {"ticker": "AAPL", "price": 190.5, "prev_price": 190.4,
                        "change_pct": 0.05, "timestamp": 1700000000.0}, ...}
    """
    return StreamingResponse(
        _generate(request, state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate(request: Request, state: AppState) -> AsyncGenerator[str, None]:
    """Yield SSE events for the watchlist's live prices until the client leaves."""
    yield "retry: 1000\n\n"

    cache = state.price_cache
    client = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client)

    try:
        while True:
            if await request.is_disconnected():
                break

            # Re-read the watchlist each tick so adds/removes take effect live.
            conn = get_db(state.db_path)
            try:
                tickers = get_watchlist_tickers(conn)
            finally:
                conn.close()

            payload: dict[str, dict] = {}
            for ticker in tickers:
                update = cache.get(ticker)
                if update is None:
                    continue
                payload[ticker] = {
                    "ticker": update.ticker,
                    "price": update.price,
                    "prev_price": update.previous_price,
                    "change_pct": update.change_percent,
                    "timestamp": update.timestamp,
                }

            if payload:
                yield f"data: {json.dumps(payload)}\n\n"

            await asyncio.sleep(_STREAM_INTERVAL)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("SSE client disconnected: %s", client)
