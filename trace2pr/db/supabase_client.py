"""Supabase client management with admin and user-scoped clients."""
import logging

from supabase import AsyncClient, acreate_client, create_client
from trace2pr.config.settings import settings

logger = logging.getLogger(__name__)

# Admin client (service role) - for backend operations
_admin_client: AsyncClient | None = None

# Sync admin client for migrations/scripts
_sync_admin_client = None


async def get_admin_client() -> AsyncClient:
    """Get admin client with service role key for backend operations."""
    global _admin_client
    if _admin_client is None:
        _admin_client = await acreate_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _admin_client


def get_sync_admin_client():
    """Get synchronous admin client for migrations/scripts."""
    global _sync_admin_client
    if _sync_admin_client is None:
        _sync_admin_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _sync_admin_client


async def get_user_client(access_token: str, refresh_token: str = "") -> AsyncClient:
    """Create a user-scoped client with the user's access token, so RLS
    policies are enforced as that user rather than as the service role."""
    client = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    try:
        await client.auth.set_session(access_token, refresh_token)
    except Exception:
        logger.exception("Failed to set session on user-scoped Supabase client")
        raise
    return client


async def close_supabase() -> None:
    """Close all clients."""
    global _admin_client, _sync_admin_client
    _admin_client = None
    _sync_admin_client = None


# Backward compatibility
async def get_supabase() -> AsyncClient:
    """Get admin client (backward compatible)."""
    return await get_admin_client()


async def supabase_dep() -> AsyncClient:
    """FastAPI dependency for admin client."""
    return await get_admin_client()


async def supabase_user_dep(access_token: str) -> AsyncClient:
    """FastAPI dependency for user-scoped client."""
    return await get_user_client(access_token)
