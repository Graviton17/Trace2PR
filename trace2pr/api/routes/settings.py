"""Settings API routes."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import get_admin_client, supabase_dep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    user_id: str
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    theme: str = "system"
    notifications: dict[str, bool] = {}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class UpdateSettingsRequest(BaseModel):
    theme: str | None = None
    notifications: dict[str, bool] | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get user settings."""
    user_id = user.get("id")

    profile = await db.table("users").select("*").eq("id", user_id).single().execute()

    return SettingsResponse(
        user_id=user_id,
        email=user.get("email"),
        full_name=profile.data.get("full_name") if profile.data else None,
        avatar_url=profile.data.get("avatar_url") if profile.data else None,
        theme=profile.data.get("theme", "system") if profile.data else "system",
        notifications=profile.data.get("notifications", {}) if profile.data else {},
    )


@router.patch("/profile", response_model=SettingsResponse)
async def update_profile(
    req: UpdateProfileRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Update user profile."""
    user_id = user.get("id")

    update_data = {}
    if req.full_name is not None:
        update_data["full_name"] = req.full_name
    if req.avatar_url is not None:
        update_data["avatar_url"] = req.avatar_url

    if update_data:
        update_data["updated_at"] = "now()"
        await db.table("users").update(update_data).eq("id", user_id).execute()

    return await get_settings(db, user)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    req: UpdateSettingsRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Update user settings (theme, notifications)."""
    user_id = user.get("id")

    update_data = {}
    if req.theme is not None:
        update_data["theme"] = req.theme
    if req.notifications is not None:
        update_data["notifications"] = req.notifications

    if update_data:
        update_data["updated_at"] = "now()"
        await db.table("users").update(update_data).eq("id", user_id).execute()

    return await get_settings(db, user)


@router.delete("/account")
async def delete_account(user=Depends(get_current_user)):
    """Delete the user's account.

    Deletes the `auth.users` row via the Supabase Admin API — this is the
    row `public.users` (and everything FK-linked to it: integrations,
    incidents, alerts, etc.) cascades from, so a single admin delete here
    removes all of it. Deleting only `public.users` (as before) would leave
    the underlying auth user — and their ability to log back in — intact.
    """
    user_id = user.get("id")
    admin_client = await get_admin_client()

    try:
        await admin_client.auth.admin.delete_user(user_id)
    except Exception:
        logger.exception("Failed to delete auth user %s during account deletion", user_id)
        raise

    return {"status": "deleted"}
