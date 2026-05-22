"""SQLite schema definitions for FinAlly.

All tables carry a ``user_id`` column defaulting to ``"default"`` so the
single-user app can grow into multi-user support without a migration.
"""

# Each statement uses IF NOT EXISTS so init_db is safe to call repeatedly.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users_profile (
        id           TEXT PRIMARY KEY,
        cash_balance REAL NOT NULL DEFAULT 10000.0,
        created_at   TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id       TEXT PRIMARY KEY,
        user_id  TEXT NOT NULL DEFAULT 'default',
        ticker   TEXT NOT NULL,
        added_at TEXT NOT NULL,
        UNIQUE (user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL DEFAULT 'default',
        ticker     TEXT NOT NULL,
        quantity   REAL NOT NULL,
        avg_cost   REAL NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (user_id, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL DEFAULT 'default',
        ticker      TEXT NOT NULL,
        side        TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
        quantity    REAL NOT NULL,
        price       REAL NOT NULL,
        executed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id          TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL DEFAULT 'default',
        total_value REAL NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL DEFAULT 'default',
        role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content    TEXT NOT NULL,
        actions    TEXT,
        created_at TEXT NOT NULL
    )
    """,
)

# Indexes for the common access patterns (history queries ordered by time).
INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_trades_user_time "
    "ON trades (user_id, executed_at)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_user_time "
    "ON portfolio_snapshots (user_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_user_time "
    "ON chat_messages (user_id, created_at)",
)

# Default identity and seed values.
DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

DEFAULT_WATCHLIST: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)
