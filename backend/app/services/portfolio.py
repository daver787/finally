"""Portfolio business logic: valuation, trade execution, history.

These functions operate on an open sqlite3 connection and the shared price
cache. They are deliberately framework-agnostic so the LLM chat endpoint can
reuse the exact same trade path as the REST API.

Trades raise ``TradeError`` on validation failure; route handlers translate
that into an HTTP 400.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db.schema import DEFAULT_USER_ID
from app.market.cache import PriceCache


class TradeError(Exception):
    """Raised when a trade fails validation (insufficient cash/shares, etc.)."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_cash_balance(conn: sqlite3.Connection, user_id: str) -> float:
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        raise TradeError("User profile not found")
    return float(row["cash_balance"])


def get_portfolio(conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> dict:
    """Build the full portfolio snapshot for the API response.

    Positions with ``quantity == 0`` are excluded — they are kept in the DB for
    trade-history context but are not live holdings.
    """
    cash_balance = _get_cash_balance(conn, user_id)

    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions "
        "WHERE user_id = ? AND quantity > 0 ORDER BY ticker",
        (user_id,),
    ).fetchall()

    positions: list[dict] = []
    total_unrealized_pnl = 0.0
    positions_value = 0.0

    for row in rows:
        ticker = row["ticker"]
        quantity = float(row["quantity"])
        avg_cost = float(row["avg_cost"])
        current_price = cache.get_price(ticker)
        # If the price is unknown (ticker not streaming), fall back to avg_cost
        # so P&L shows zero rather than a misleading value.
        effective_price = current_price if current_price is not None else avg_cost

        market_value = quantity * effective_price
        cost_basis = quantity * avg_cost
        unrealized_pnl = market_value - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        positions.append(
            {
                "ticker": ticker,
                "quantity": round(quantity, 6),
                "avg_cost": round(avg_cost, 4),
                "current_price": round(effective_price, 4),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )
        total_unrealized_pnl += unrealized_pnl
        positions_value += market_value

    return {
        "cash_balance": round(cash_balance, 2),
        "total_value": round(cash_balance + positions_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "positions": positions,
    }


def compute_total_value(conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> float:
    """Compute total portfolio value (cash + market value of all holdings)."""
    cash_balance = _get_cash_balance(conn, user_id)
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND quantity > 0",
        (user_id,),
    ).fetchall()
    positions_value = 0.0
    for row in rows:
        ticker = row["ticker"]
        quantity = float(row["quantity"])
        price = cache.get_price(ticker)
        positions_value += quantity * (price if price is not None else float(row["avg_cost"]))
    return round(cash_balance + positions_value, 2)


def record_snapshot(conn: sqlite3.Connection, cache: PriceCache, user_id: str = DEFAULT_USER_ID) -> float:
    """Insert a portfolio_snapshots row with the current total value.

    Returns the recorded total value. Caller is responsible for committing.
    """
    total_value = compute_total_value(conn, cache, user_id)
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, total_value, _utc_now_iso()),
    )
    return total_value


def get_history(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return portfolio value snapshots ordered oldest-first (for the P&L chart)."""
    rows = conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots "
        "WHERE user_id = ? ORDER BY recorded_at ASC",
        (user_id,),
    ).fetchall()
    return [
        {"total_value": round(float(r["total_value"]), 2), "recorded_at": r["recorded_at"]}
        for r in rows
    ]


def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    quantity: float,
    side: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Execute a market order. Commits the transaction on success.

    Buy: validates sufficient cash, debits cash, upserts the position with a
    weighted-average cost, appends a trade, records a snapshot.

    Sell: validates sufficient shares, credits cash, reduces the position
    quantity (to 0 on a full sell — the row is never deleted), appends a trade,
    records a snapshot.

    Raises ``TradeError`` on any validation failure. The transaction is rolled
    back so the database is left untouched.
    """
    ticker = ticker.upper().strip()
    side = side.lower().strip()

    if side not in ("buy", "sell"):
        raise TradeError(f"Invalid side '{side}' — must be 'buy' or 'sell'")
    if quantity <= 0:
        raise TradeError("Quantity must be positive")

    price = cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No market price available for {ticker}")

    try:
        cash_balance = _get_cash_balance(conn, user_id)
        cost = price * quantity

        position = conn.execute(
            "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()

        now = _utc_now_iso()

        if side == "buy":
            if cost > cash_balance:
                raise TradeError(
                    f"Insufficient cash: need ${cost:,.2f}, have ${cash_balance:,.2f}"
                )
            new_cash = cash_balance - cost

            if position is None:
                conn.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), user_id, ticker, quantity, price, now),
                )
            else:
                old_qty = float(position["quantity"])
                old_cost = float(position["avg_cost"])
                new_qty = old_qty + quantity
                # Weighted-average cost. Guard against a zeroed-out position.
                new_avg_cost = (
                    ((old_qty * old_cost) + cost) / new_qty if new_qty > 0 else price
                )
                conn.execute(
                    "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                    "WHERE id = ?",
                    (new_qty, new_avg_cost, now, position["id"]),
                )
        else:  # sell
            held = float(position["quantity"]) if position else 0.0
            if quantity > held:
                raise TradeError(
                    f"Insufficient shares: trying to sell {quantity} of {ticker}, hold {held}"
                )
            new_cash = cash_balance + cost
            new_qty = held - quantity
            # avg_cost is preserved on a partial sell; on a full sell the row
            # stays with quantity=0 (avg_cost retained for trade-history context).
            conn.execute(
                "UPDATE positions SET quantity = ?, updated_at = ? WHERE id = ?",
                (new_qty, now, position["id"]),
            )

        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_cash, user_id),
        )
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, side, quantity, price, now),
        )
        record_snapshot(conn, cache, user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": round(price, 4),
        "executed_at": now,
    }
