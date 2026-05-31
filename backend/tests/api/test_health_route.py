"""Tests for the /api/health endpoint."""

from __future__ import annotations


def test_health_returns_200_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
