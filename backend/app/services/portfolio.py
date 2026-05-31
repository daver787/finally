"""Portfolio service — trade execution, live valuation, snapshot recording."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from ..db.schema import DEFAULT_USER_ID
from ..market.cache import PriceCache

logger = logging.getLogger(__name__)


class TradeError(Exception):
    """Raised on invalid trade attempts (insufficient cash/shares, unknown price, invalid input)."""


def _compute_total_value(conn: sqlite3.Connection, price_cache: PriceCache) -> float:
    """Return cash + Σ(qty × current_price) summed across positions with quantity > 0.

    Positions whose ticker has no current price in the cache are skipped (treated
    as zero contribution rather than blocking the snapshot). This is acceptable
    because the next price tick will refresh the valuation; we never want a
    transient cache miss to break trade execution or the snapshot loop.
    """
    cash_row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    cash = float(cash_row["cash_balance"]) if cash_row is not None else 0.0

    rows = conn.execute(
        "SELECT ticker, quantity FROM positions WHERE user_id = ? AND quantity > 0",
        (DEFAULT_USER_ID,),
    ).fetchall()

    positions_value = 0.0
    for row in rows:
        ticker = row["ticker"]
        qty = float(row["quantity"])
        live = price_cache.get_price(ticker)
        if live is not None:
            positions_value += live * qty
    return cash + positions_value


def execute_trade(
    *,
    ticker: str,
    side: str,
    quantity: float,
    conn: sqlite3.Connection,
    price_cache: PriceCache,
) -> dict:
    """Execute a market order against the user's portfolio.

    Atomically (single ``conn.commit``): updates cash_balance, upserts the
    position row, appends a trades row, and writes a portfolio_snapshots row.
    The cash update happens BEFORE total_value is computed so the snapshot
    reflects post-trade state (see RESEARCH.md anti-pattern: "Computing
    total_value BEFORE updating cash").

    Selling a position to zero quantity does NOT delete the positions row —
    per PLAN.md §7, the row is preserved (quantity=0) to keep trade history
    context and avoid disappearing rows mid-session.
    """
    if side not in ("buy", "sell"):
        raise TradeError(f"invalid side {side!r}")
    if quantity <= 0:
        raise TradeError("quantity must be positive")

    price = price_cache.get_price(ticker)
    if price is None:
        raise TradeError(f"no price available for {ticker}")

    notional = price * quantity
    now = datetime.now(timezone.utc).isoformat()

    cash_row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    cash = float(cash_row["cash_balance"]) if cash_row is not None else 0.0

    pos_row = conn.execute(
        "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, ticker),
    ).fetchone()
    if pos_row is not None:
        cur_qty = float(pos_row["quantity"])
        cur_cost = float(pos_row["avg_cost"])
    else:
        cur_qty = 0.0
        cur_cost = 0.0

    if side == "buy":
        if cash < notional:
            raise TradeError(
                f"insufficient cash: need ${notional:.2f}, have ${cash:.2f}"
            )
        new_qty = cur_qty + quantity
        # Weighted average cost across all buys; ``new_qty`` is guaranteed > 0
        # because ``quantity > 0`` and ``cur_qty >= 0``.
        new_avg_cost = ((cur_qty * cur_cost) + (quantity * price)) / new_qty
        new_cash = cash - notional
    else:  # sell
        if cur_qty < quantity:
            raise TradeError(
                f"insufficient shares: need {quantity}, have {cur_qty}"
            )
        new_qty = cur_qty - quantity
        # Selling does not change cost basis — only the buying side does.
        new_avg_cost = cur_cost
        new_cash = cash + notional

    # 1) Update cash FIRST so total_value reflects the post-trade balance.
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (new_cash, DEFAULT_USER_ID),
    )

    # 2) Upsert the position row. NEVER DELETE — per PLAN.md §7, full-sell
    # leaves the row with quantity=0 so trade history context is preserved.
    if pos_row is not None:
        conn.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
            "WHERE user_id = ? AND ticker = ?",
            (new_qty, new_avg_cost, now, DEFAULT_USER_ID, ticker),
        )
    else:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, new_qty, new_avg_cost, now),
        )

    # 3) Append trades log (append-only audit trail — never UPDATE/DELETE).
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, side, quantity, price, now),
    )

    # 4) Snapshot total portfolio value AFTER the cash + position writes above.
    total_value = _compute_total_value(conn, price_cache)
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), DEFAULT_USER_ID, total_value, now),
    )

    conn.commit()
    logger.info(
        "Trade: %s %s %.4f @ $%.2f (cash=$%.2f, total=$%.2f)",
        side,
        ticker,
        quantity,
        price,
        new_cash,
        total_value,
    )
    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "cash_balance": new_cash,
        "total_value": total_value,
    }


def build_portfolio_summary(
    *, conn: sqlite3.Connection, price_cache: PriceCache
) -> dict:
    """Build a live portfolio snapshot dict.

    Returns ``cash_balance``, ``total_value`` (cash + sum of position
    quantity × current_price), and a list of position dicts with
    unrealized P&L computed against the live PriceCache. Positions with
    no current price are still included but have ``None`` for
    current_price / unrealized_pnl / pnl_percent so the frontend can
    render them as pending.
    """
    cash_row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    cash = float(cash_row["cash_balance"]) if cash_row is not None else 0.0

    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions "
        "WHERE user_id = ? AND quantity > 0 ORDER BY ticker",
        (DEFAULT_USER_ID,),
    ).fetchall()

    positions: list[dict] = []
    positions_value = 0.0
    for row in rows:
        ticker = row["ticker"]
        qty = float(row["quantity"])
        cost = float(row["avg_cost"])
        current_price = price_cache.get_price(ticker)
        if current_price is None:
            positions.append(
                {
                    "ticker": ticker,
                    "quantity": qty,
                    "avg_cost": cost,
                    "current_price": None,
                    "unrealized_pnl": None,
                    "pnl_percent": None,
                }
            )
            continue
        unrealized_pnl = (current_price - cost) * qty
        pnl_percent = ((current_price - cost) / cost) * 100 if cost > 0 else 0.0
        positions_value += current_price * qty
        positions.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": cost,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "pnl_percent": pnl_percent,
            }
        )

    return {
        "cash_balance": cash,
        "total_value": cash + positions_value,
        "positions": positions,
    }


def record_snapshot(
    *, conn: sqlite3.Connection, price_cache: PriceCache
) -> dict:
    """Write a portfolio_snapshots row for the current cash + live position value."""
    total_value = _compute_total_value(conn, price_cache)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), DEFAULT_USER_ID, total_value, now),
    )
    conn.commit()
    logger.debug("Snapshot recorded: total=$%.2f", total_value)
    return {"total_value": total_value, "recorded_at": now}
