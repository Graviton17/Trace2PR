"""Authentication API routes for Supabase Auth (OAuth only)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from supabase import AsyncClient
from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep

router = APIRouter(prefix="/auth", tags=["auth"])


class OAuthRequest(BaseModel):
    provider: str  # 'github' or 'google'
    redirect_url: str | None = None


class AuthResponse(BaseModel):
    user: dict | None = None
    session: dict | None = None
    message: str


@router.post("/oauth", response_model=AuthResponse)
async def oauth_sign_in(req: OAuthRequest, db: AsyncClient = Depends(supabase_dep)):
    """Initiate OAuth flow with GitHub or Google."""
    provider = req.provider.lower()
    if provider not in ["github", "google"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'github' or 'google'")

    try:
        redirect_url = req.redirect_url or "http://localhost:5173/auth/callback"

        res = await db.auth.sign_in_with_oauth(
            {
                "provider": provider,
                "options": {
                    "redirect_to": redirect_url,
                    "scopes": "user:email" if provider == "github" else "email profile",
                },
            }
        )

        return AuthResponse(
            message=f"OAuth URL generated for {provider}",
            user={"oauth_url": res.url if hasattr(res, "url") else None},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/signout", response_model=AuthResponse)
async def sign_out(db: AsyncClient = Depends(supabase_dep), user: dict = Depends(get_current_user)):
    """Sign out the current user.

    NOTE: this must be the *user's own* session being revoked, not a no-op
    on the service-role client (which has no session to sign out of).
    `auth.admin.sign_out` takes the user's access token explicitly and
    revokes that specific session server-side.
    """
    try:
        await db.auth.admin.sign_out(user["access_token"])
        return AuthResponse(message="Signed out successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/user", response_model=AuthResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return AuthResponse(user=user, message="User retrieved successfully")


@router.post("/refresh", response_model=AuthResponse)
async def refresh_session(request: Request, db: AsyncClient = Depends(supabase_dep)):
    """Refresh access token using refresh token."""
    try:
        body = await request.json()
        refresh_token = body.get("refresh_token")

        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")

        res = await db.auth.refresh_session(refresh_token)

        if res.session:
            return AuthResponse(
                session=res.session.model_dump() if hasattr(res.session, "model_dump") else res.session,
                user=res.user.model_dump() if res.user and hasattr(res.user, "model_dump") else res.user,
                message="Session refreshed",
            )
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get("/providers")
async def list_oauth_providers():
    """List available OAuth providers."""
    return {
        "providers": [
            {"id": "github", "name": "GitHub", "icon": "github"},
            {"id": "google", "name": "Google", "icon": "google"},
        ]
    }
