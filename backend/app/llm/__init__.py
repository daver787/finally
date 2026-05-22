"""LLM chat integration for FinAlly.

Exposes the structured-output schema and the ``handle_chat`` entry point used
by the ``POST /api/chat`` route.
"""

from .schema import ChatResponse, TradeAction, WatchlistChange

__all__ = ["ChatResponse", "TradeAction", "WatchlistChange", "handle_chat"]


def __getattr__(name: str):  # pragma: no cover - thin lazy import shim
    # ``chat`` imports litellm, which is heavy; defer until actually used.
    if name == "handle_chat":
        from .chat import handle_chat

        return handle_chat
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
