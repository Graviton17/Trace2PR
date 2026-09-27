"""Health check routes with dependency verification."""
import logging
from typing import Any

import httpx
from fastapi import APIRouter

from trace2pr.config.settings import settings
from trace2pr.db.supabase_client import get_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def check_supabase() -> dict[str, Any]:
    """Check Supabase connection."""
    try:
        client = await get_admin_client()
        await client.table("users").select("id").limit(1).execute()
        return {"status": "ok", "details": "Connected"}
    except Exception as e:
        logger.warning("Supabase health check failed: %s", e)
        return {"status": "error", "details": str(e)}


async def check_redis() -> dict[str, Any]:
    """Check Redis connection."""
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return {"status": "ok", "details": "Connected"}
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return {"status": "error", "details": str(e)}


async def check_e2b() -> dict[str, Any]:
    """Check E2B API availability."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://api.e2b.dev/health",
                headers={"Authorization": f"Bearer {settings.E2B_API_KEY}"},
            )
        if response.status_code == 200:
            return {"status": "ok", "details": "API reachable"}
        return {"status": "degraded", "details": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.warning("E2B health check failed: %s", e)
        return {"status": "error", "details": str(e)}


async def check_composio() -> dict[str, Any]:
    """Check Composio API availability."""
    if not settings.COMPOSIO_API_KEY:
        return {"status": "not_configured", "details": "COMPOSIO_API_KEY not set"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.COMPOSIO_BASE_URL}/apps",
                headers={"x-api-key": settings.COMPOSIO_API_KEY},
            )
        if response.status_code == 200:
            return {"status": "ok", "details": "API reachable"}
        return {"status": "degraded", "details": f"HTTP {response.status_code}"}
    except Exception as e:
        logger.warning("Composio health check failed: %s", e)
        return {"status": "error", "details": str(e)}


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check overall health of the service. Returns status of Supabase,
    Redis, E2B, Composio."""
    supabase = await check_supabase()
    redis = await check_redis()
    e2b = await check_e2b()
    composio = await check_composio()

    all_ok = all(
        check["status"] in ("ok", "not_configured") for check in [supabase, redis, e2b, composio]
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "supabase": supabase,
        "redis": redis,
        "e2b": e2b,
        "composio": composio,
    }


@router.get("/health/ready")
async def readiness_probe() -> dict[str, str]:
    """Readiness probe for orchestration."""
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """Liveness probe for orchestration."""
    return {"status": "alive"}


@router.get("/version")
async def get_version() -> dict[str, str]:
    """Returns API version."""
    return {"version": "1.0.0"}
