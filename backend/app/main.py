"""FinAlly FastAPI application.

Wires together the REST API, the SSE price stream, the market data background
task, and a periodic portfolio-snapshot task. Serves the Next.js static export
from ``static/`` when present.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import get_db, init_db
from app.market.factory import create_market_data_source
from app.routes import chat, health, portfolio, stream, watchlist
from app.services.portfolio import record_snapshot
from app.services.watchlist import get_watchlist_tickers
from app.state import AppState

# Load .env from the project root (backend/ -> finally/).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cadence of the portfolio snapshot background task (PLAN.md §7).
_SNAPSHOT_INTERVAL = 30.0

# Static export produced by the Next.js build (Docker copies it here).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


async def _snapshot_loop(state: AppState) -> None:
    """Record a portfolio value snapshot every ``_SNAPSHOT_INTERVAL`` seconds."""
    while True:
        await asyncio.sleep(_SNAPSHOT_INTERVAL)
        try:
            conn = get_db(state.db_path)
            try:
                record_snapshot(conn, state.price_cache)
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the DB, market data source, and background tasks; clean up on exit."""
    state: AppState = app.state.app_state

    init_db(state.db_path)
    logger.info("Database initialized at %s", state.db_path)

    # Begin streaming prices for whatever is on the watchlist at boot.
    conn = get_db(state.db_path)
    try:
        tickers = get_watchlist_tickers(conn)
    finally:
        conn.close()

    source = create_market_data_source(state.price_cache)
    await source.start(tickers)
    state.market_source = source
    logger.info("Market data source started with %d tickers", len(tickers))

    snapshot_task = asyncio.create_task(_snapshot_loop(state), name="snapshot-loop")

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        if state.market_source is not None:
            await state.market_source.stop()
        logger.info("Shutdown complete")


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Build the FastAPI app.

    ``db_path`` overrides the default SQLite location — used by tests to point
    at an isolated database.
    """
    app = FastAPI(title="FinAlly", version="0.1.0", lifespan=lifespan)
    app.state.app_state = AppState(db_path) if db_path else AppState()

    app.include_router(health.router)
    app.include_router(watchlist.router)
    app.include_router(portfolio.router)
    app.include_router(chat.router)
    app.include_router(stream.router)

    # Serve the Next.js static export last so /api/* routes win. Mounting only
    # when the directory exists keeps the dev server alive without a built UI.
    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
        logger.info("Serving static frontend from %s", _STATIC_DIR)
    else:
        logger.info("No static/ directory — running API-only (no frontend build)")

    return app


app = create_app()
