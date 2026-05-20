"""Tests for SSE streaming endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import APIRouter

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


def _make_request(disconnect_after: int = 1) -> MagicMock:
    """Return a mock Request that disconnects after `disconnect_after` is_disconnected() calls."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    call_count = 0

    async def is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count > disconnect_after

    request.is_disconnected = is_disconnected
    return request


@pytest.mark.asyncio
class TestCreateStreamRouter:
    """Tests for the create_stream_router factory."""

    async def test_returns_api_router(self):
        cache = PriceCache()
        router = create_stream_router(cache)
        assert isinstance(router, APIRouter)

    async def test_returns_fresh_instance_each_call(self):
        """Each call must return a new router so tests don't share state."""
        cache = PriceCache()
        router1 = create_stream_router(cache)
        router2 = create_stream_router(cache)
        assert router1 is not router2

    async def test_router_has_prices_route(self):
        cache = PriceCache()
        router = create_stream_router(cache)
        paths = [route.path for route in router.routes]
        assert any("/prices" in p for p in paths)


@pytest.mark.asyncio
class TestGenerateEvents:
    """Tests for the _generate_events async generator."""

    async def test_first_event_is_retry_directive(self):
        """The very first yielded value must be the SSE retry directive."""
        cache = PriceCache()
        request = _make_request(disconnect_after=0)  # disconnect immediately after retry
        gen = _generate_events(cache, request, interval=0.01)
        first = await gen.__anext__()
        assert first == "retry: 1000\n\n"

    async def test_sends_price_data_event(self):
        """When cache has prices and version changes, a data event is sent."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)

        # Allow 1 full iteration (disconnect on 2nd is_disconnected call)
        request = _make_request(disconnect_after=1)
        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        data_events = [e for e in events if e.startswith("data: ")]
        assert len(data_events) == 1

        payload = json.loads(data_events[0][len("data: "):].strip())
        assert "AAPL" in payload
        assert payload["AAPL"]["price"] == 190.50
        assert payload["AAPL"]["ticker"] == "AAPL"
        assert "direction" in payload["AAPL"]

    async def test_stops_on_immediate_disconnect(self):
        """Generator must exit cleanly when the client disconnects at once."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.is_disconnected = AsyncMock(return_value=True)

        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        # Only the retry directive; disconnected before the first data event
        assert events == ["retry: 1000\n\n"]

    async def test_empty_cache_sends_no_data_event(self):
        """When the cache is empty the generator yields no data events."""
        cache = PriceCache()  # empty

        # Allow 2 full iterations before disconnecting
        request = _make_request(disconnect_after=2)
        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        assert "retry: 1000\n\n" in events
        data_events = [e for e in events if e.startswith("data: ")]
        assert len(data_events) == 0

    async def test_no_duplicate_events_when_version_unchanged(self):
        """Data events are only sent when the cache version changes."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)  # version = 1; won't change during test

        # Allow 3 full iterations (version stays the same after the first send)
        request = _make_request(disconnect_after=3)
        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        data_events = [e for e in events if e.startswith("data: ")]
        assert len(data_events) == 1  # Only one send despite multiple iterations

    async def test_data_event_format_is_valid_sse(self):
        """Data events must conform to SSE text/event-stream format."""
        cache = PriceCache()
        cache.update("TSLA", 250.00)

        request = _make_request(disconnect_after=1)
        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        data_events = [e for e in events if e.startswith("data: ")]
        assert len(data_events) == 1
        # SSE format: "data: <payload>\n\n"
        assert data_events[0].endswith("\n\n")
        json_str = data_events[0][len("data: "):].rstrip("\n")
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    async def test_multiple_tickers_in_single_event(self):
        """All cached tickers are included in a single data event."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        cache.update("MSFT", 420.00)

        request = _make_request(disconnect_after=1)
        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        data_events = [e for e in events if e.startswith("data: ")]
        assert len(data_events) == 1
        payload = json.loads(data_events[0][len("data: "):].strip())
        assert set(payload.keys()) == {"AAPL", "GOOGL", "MSFT"}
