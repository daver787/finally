"""FastAPI application factory for FinAlly."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import pathlib
import sqlite3
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db.init_db import init_db
from .db.schema import DEFAULT_USER_ID
from .market import PriceCache, create_market_data_source, create_stream_router
from .routes import chat, health, portfolio, watchlist
from .state import AppState

logger = logging.getLogger(__name__)

# Default cadence for the portfolio snapshot loop (seconds).
SNAPSHOT_INTERVAL_SECONDS: float = 30.0


def _load_watchlist_tickers(db_path: str) -> list[str]:
    """Read the seeded watchlist tickers from the DB.

    Used during lifespan startup to tell the market source which tickers to
    track. Returns an empty list if the watchlist is empty.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (DEFAULT_USER_ID,),
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


async def _snapshot_loop(
    db_path: str,
    price_cache: PriceCache,
    interval: float = SNAPSHOT_INTERVAL_SECONDS,
) -> None:
    """Write a portfolio_snapshots row every ``interval`` seconds.

    Per-iteration sqlite3 connection (never reused, always closed via
    ``contextlib.closing``) bounds fd usage to 1 even if an exception is
    raised mid-snapshot — see RESEARCH.md Pitfall 7. Per-iteration exceptions
    are logged and swallowed so a single bad snapshot never kills the loop;
    only :class:`asyncio.CancelledError` propagates so the lifespan can
    cancel the task at shutdown.
    """
    # Local import avoids a top-level cycle (services.portfolio -> market ->
    # main is fine because the import lands once the module is loaded).
    from .services.portfolio import record_snapshot

    def _do_snapshot() -> None:
        # Runs in a thread-pool worker so SQLite blocking never freezes the
        # event loop (asyncio.to_thread below). Each call opens + closes its
        # own connection to bound fd usage to 1 per iteration.
        with contextlib.closing(
            sqlite3.connect(db_path, check_same_thread=False)
        ) as conn:
            conn.row_factory = sqlite3.Row
            record_snapshot(conn=conn, price_cache=price_cache)

    while True:
        try:
            await asyncio.sleep(interval)
            await asyncio.to_thread(_do_snapshot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("snapshot_loop iteration failed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Sets up the lifespan context (DB init, market source, AppState), registers
    all routes, and returns the configured ``FastAPI`` instance. Each call
    creates a fresh :class:`PriceCache` so tests can spin up isolated apps.
    """
    load_dotenv()

    # Hoist PriceCache to create_app scope so it can be shared between the
    # lifespan (which starts the market source) and the SSE router
    # (which reads from the cache). Each create_app() call gets a fresh cache.
    price_cache = PriceCache()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- startup ---
        _project_root = pathlib.Path(__file__).parent.parent.parent
        _default_db = str(_project_root / "db" / "finally.db")
        db_path = os.environ.get("DB_PATH", _default_db)
        market_source = create_market_data_source(price_cache)
        app.state.app_state = AppState(
            price_cache=price_cache,
            market_source=market_source,
            db_path=db_path,
        )
        init_db(db_path)
        watchlist_tickers = _load_watchlist_tickers(db_path)
        await market_source.start(watchlist_tickers)
        logger.info("FinAlly backend started — %d tickers", len(watchlist_tickers))

        # Write an initial portfolio_snapshots row BEFORE the loop's first
        # sleep — anchors the P&L chart at t=0 so the frontend has at least
        # one data point even if the user never trades (RESEARCH.md Pitfall 4).
        from .services.portfolio import record_snapshot

        def _initial_snapshot() -> None:
            with contextlib.closing(
                sqlite3.connect(db_path, check_same_thread=False)
            ) as conn:
                conn.row_factory = sqlite3.Row
                record_snapshot(conn=conn, price_cache=price_cache)

        await asyncio.to_thread(_initial_snapshot)
        logger.info("Initial portfolio snapshot written")

        # Spawn the 30s snapshot background task.
        snapshot_task = asyncio.create_task(_snapshot_loop(db_path, price_cache))

        try:
            yield
        finally:
            # --- shutdown ---
            # Cancel the snapshot loop FIRST so it stops opening sqlite
            # connections before the market source's shutdown work.
            snapshot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await snapshot_task
            await market_source.stop()
            logger.info("FinAlly backend stopped")

    app = FastAPI(title="FinAlly", lifespan=lifespan)

    # Allow the Next.js dev server (port 3000) to connect cross-origin in development.
    # In production the frontend is served from the same FastAPI origin so CORS is moot.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes MUST be registered before the static mount so /api/* is not shadowed.
    app.include_router(health.router, prefix="/api")
    app.include_router(watchlist.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    # create_stream_router already uses prefix="/api/stream"; do not add another prefix
    app.include_router(create_stream_router(price_cache))

    # Serve the Next.js static export. html=True makes FastAPI serve index.html
    # for unknown paths (SPA fallback). check_dir=False so missing static/ in
    # test environments does not raise at import time.
    _static_dir = pathlib.Path(__file__).parent.parent / "static"
    if _static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")

    return app


app = create_app()
