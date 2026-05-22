"""Tests for the health check route."""


class TestHealth:
    """GET /api/health is the Docker/deployment liveness probe."""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_content_type_json(self, client):
        resp = client.get("/api/health")
        assert resp.headers["content-type"].startswith("application/json")
