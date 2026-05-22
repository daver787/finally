"""Tests for the SSE price stream route.

GET /api/stream/prices is a long-lived text/event-stream. Tests use a
streaming request and close it immediately after inspecting the headers /
first event so the generator does not run forever.
"""

import json


class TestStreamPrices:
    """GET /api/stream/prices pushes watchlist price updates over SSE."""

    def test_content_type_is_event_stream(self, client):
        with client.stream("GET", "/api/stream/prices") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

    def test_no_cache_header_set(self, client):
        with client.stream("GET", "/api/stream/prices") as resp:
            assert resp.headers.get("cache-control") == "no-cache"

    def test_first_chunk_contains_price_data(self, client):
        # The stream emits a `retry:` line then a `data:` JSON payload keyed by
        # ticker. Pull lines until the first data event, then stop.
        with client.stream("GET", "/api/stream/prices") as resp:
            data_payload = None
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    data_payload = json.loads(line[len("data:"):].strip())
                    break
            assert data_payload is not None
            assert "AAPL" in data_payload
            assert data_payload["AAPL"]["price"] == 190.0
