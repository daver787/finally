"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe for Docker and load balancers.

    Returns 200 ``{"status": "ok"}`` whenever the server is running.
    """
    return {"status": "ok"}
