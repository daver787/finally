"""Health check route."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for Docker/deployment."""
    return {"status": "ok"}
