"""Database subsystem for FinAlly.

Public API:
    get_db          - Open a sqlite3 connection (row_factory=Row, FK enforced)
    init_db         - Create schema + seed default data (lazy, idempotent)
    init_db_conn    - Same, on an already-open connection (for in-memory tests)
    DEFAULT_DB_PATH - Default location of the SQLite file (db/finally.db)
"""

from .init_db import DEFAULT_DB_PATH, get_db, init_db, init_db_conn
from .schema import DEFAULT_CASH_BALANCE, DEFAULT_USER_ID, DEFAULT_WATCHLIST

__all__ = [
    "get_db",
    "init_db",
    "init_db_conn",
    "DEFAULT_DB_PATH",
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_USER_ID",
    "DEFAULT_WATCHLIST",
]
