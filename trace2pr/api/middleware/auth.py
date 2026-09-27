"""Authentication middleware for FastAPI with Supabase."""
import logging

from fastapi import Depends, HTTPException, Request

from supabase import AsyncClient
from trace2pr.db.supabase_client import get_admin_client, get_user_client

logger = logging.getLogger(__name__)


async def get_optional_user(request: Request) -> dict | None:
    """Get current user from Authorization header (optional)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    try:
        admin_client = await get_admin_client()
        res = await admin_client.auth.get_user(token)

        if res.user:
            user_data = res.user.model_dump() if hasattr(res.user, "model_dump") else res.user
            return {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "user_metadata": user_data.get("user_metadata", {}),
                "app_metadata": user_data.get("app_metadata", {}),
                "access_token": token,  # Included so downstream deps can build a user-scoped client
            }
        return None
    except Exception:
        logger.debug("Token validation failed", exc_info=True)
        return None


async def get_current_user(request: Request) -> dict:
    """Get current user from Authorization header (required)."""
    user = await get_optional_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


async def get_user_supabase(user: dict = Depends(get_current_user)) -> AsyncClient:
    """Get user-scoped Supabase client for RLS enforcement."""
    access_token = user.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="No access token")
    return await get_user_client(access_token)


# Backward compatibility
async def supabase_admin_dep() -> AsyncClient:
    """FastAPI dependency for admin client."""
    return await get_admin_client()
