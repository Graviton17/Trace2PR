"""Integrations API routes using Composio for OAuth."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.config.settings import settings
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.integrations.composio_service import COMPOSIO_APP_MAP, composio_service
from trace2pr.integrations.resolver import IntegrationResolver
from trace2pr.integrations.verifiers import get_verifier

router = APIRouter(prefix="/integrations", tags=["integrations"])


# =============================================
# Schemas
# =============================================

from enum import Enum


class IntegrationCategory(str, Enum):
    observability = "observability"
    incident = "incident"
    vcs = "vcs"
    cloud = "cloud"


class Integration(BaseModel):
    id: str
    user_id: str
    service: str
    category: str
    status: str
    config: dict
    composio_connection_id: str | None = None
    composio_entity_id: str | None = None
    verified_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationCatalogItem(BaseModel):
    id: str
    name: str
    category: str
    description: str
    logo_url: str | None = None
    oauth_supported: bool = True
    required_fields: list[str] = []


class ConnectIntegrationRequest(BaseModel):
    service: str
    category: IntegrationCategory
    config: dict | None = {}


class ConnectIntegrationResponse(BaseModel):
    success: bool
    redirect_url: str | None = None
    connection_id: str | None = None
    entity_id: str | None = None
    error: str | None = None


class IntegrationStatusResponse(BaseModel):
    connected: bool
    connection_id: str | None = None
    status: str | None = None
    auth_config: dict | None = None
    error: str | None = None


# =============================================
# Integration Catalog
# =============================================

INTEGRATION_CATALOG = [
    IntegrationCatalogItem(
        id="datadog",
        name="Datadog",
        category="observability",
        description="Fetch APM traces, metrics, and logs for root cause analysis.",
        logo_url="https://cdn.sanity.io/images/.../datadog-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
    IntegrationCatalogItem(
        id="sentry",
        name="Sentry",
        category="observability",
        description="Pull detailed error stack traces and crash reports.",
        logo_url="https://cdn.sanity.io/images/.../sentry-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
    IntegrationCatalogItem(
        id="cloudwatch",
        name="AWS CloudWatch",
        category="cloud",
        description="Access AWS infrastructure metrics and CloudWatch logs.",
        logo_url="https://cdn.sanity.io/images/.../aws-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
    IntegrationCatalogItem(
        id="pagerduty",
        name="PagerDuty",
        category="incident",
        description="Sync incident states and acknowledge alerts automatically.",
        logo_url="https://cdn.sanity.io/images/.../pagerduty-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
    IntegrationCatalogItem(
        id="grafana",
        name="Grafana",
        category="observability",
        description="Query metrics, logs, and traces from Grafana Cloud or self-hosted.",
        logo_url="https://cdn.sanity.io/images/.../grafana-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
    IntegrationCatalogItem(
        id="github",
        name="GitHub",
        category="vcs",
        description="Create pull requests and read repository source code.",
        logo_url="https://cdn.sanity.io/images/.../github-logo.svg",
        oauth_supported=True,
        required_fields=[],
    ),
]


# =============================================
# Routes
# =============================================

@router.get("/catalog", response_model=list[IntegrationCatalogItem])
async def get_integration_catalog():
    """Get list of available integrations."""
    return INTEGRATION_CATALOG


@router.get("", response_model=list[Integration])
async def list_integrations(
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """List configured integrations for the current user."""
    response = await db.table("integrations").select("*").eq("user_id", user.get("id")).execute()
    return response.data


@router.post("/connect", response_model=ConnectIntegrationResponse)
async def connect_integration(
    req: ConnectIntegrationRequest,
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Initiate OAuth connection for an integration via Composio."""
    user_id = user.get("id")
    service = req.service.lower()

    # Validate service
    if service not in COMPOSIO_APP_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")

    # Check if already connected
    existing = await db.table("integrations").select("*").eq("user_id", user_id).eq("service", service).execute()
    if existing.data and existing.data[0].get("status") == "connected":
        return ConnectIntegrationResponse(
            success=False,
            error=f"{service} is already connected. Disconnect first to reconnect."
        )

    # Initiate Composio OAuth flow
    redirect_url = f"{settings.FRONTEND_URL}/dashboard/integrations/callback?service={service}"
    result = await composio_service.initiate_connection(
        user_id=user_id,
        service=service,
        redirect_url=redirect_url,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Failed to initiate connection")

    # Create pending integration record
    integration_data = {
        "user_id": user_id,
        "service": service,
        "category": req.category.value,
        "status": "pending",
        "config": req.config or {},
        "composio_connection_id": result.connection_id,
        "composio_entity_id": result.entity_id,
    }

    await db.table("integrations").upsert(
        integration_data,
        on_conflict="user_id,service"
    ).execute()

    return ConnectIntegrationResponse(
        success=True,
        redirect_url=result.redirect_url,
        connection_id=result.connection_id,
        entity_id=result.entity_id,
    )


@router.get("/{service}/status", response_model=IntegrationStatusResponse)
async def get_integration_status(
    service: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Get connection status for an integration."""
    user_id = user.get("id")
    service = service.lower()

    # Get integration record
    response = await db.table("integrations").select("*").eq("user_id", user_id).eq("service", service).execute()
    
    if not response.data:
        return IntegrationStatusResponse(connected=False)

    integration = response.data[0]
    entity_id = integration.get("composio_entity_id")

    if not entity_id:
        return IntegrationStatusResponse(connected=False)

    # Check status via Composio
    status = await composio_service.get_connection_status(entity_id, service)
    
    # Update local status if changed
    if status.get("connected") != (integration.get("status") == "connected"):
        new_status = "connected" if status.get("connected") else "error"
        await db.table("integrations").update({
            "status": new_status,
            "verified_at": datetime.utcnow().isoformat() if status.get("connected") else None,
            "error_message": status.get("error"),
        }).eq("id", integration["id"]).execute()

    return IntegrationStatusResponse(
        connected=status.get("connected", False),
        connection_id=integration.get("composio_connection_id"),
        status=status.get("status"),
        auth_config=status.get("auth_config"),
        error=status.get("error"),
    )


@router.post("/{service}/verify", response_model=IntegrationStatusResponse)
async def verify_integration(
    service: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Re-verify an integration's connection.

    For services connected via Composio OAuth this delegates to the
    Composio-backed status check (same as GET /{service}/status). For
    services configured with direct API credentials (vault-stored or via
    env fallback — see IntegrationResolver) this makes a real live call
    against that service's API via the matching verifier in
    `trace2pr.integrations.verifiers`, which previously existed in the
    codebase but was never wired into any route."""
    user_id = user.get("id")
    service = service.lower()

    response = (
        await db.table("integrations").select("*").eq("user_id", user_id).eq("service", service).execute()
    )
    integration = response.data[0] if response.data else None

    if integration and integration.get("composio_entity_id"):
        return await get_integration_status(service, db, user)

    creds = await IntegrationResolver().resolve(service, user_id, db)
    if not creds:
        return IntegrationStatusResponse(
            connected=False, error="No credentials configured for this integration"
        )

    try:
        verifier = get_verifier(service)
    except ValueError:
        return IntegrationStatusResponse(connected=False, error=f"No verifier available for '{service}'")

    result = await verifier.verify(creds)

    if integration:
        await db.table("integrations").update(
            {
                "status": "connected" if result.success else "error",
                "verified_at": datetime.utcnow().isoformat() if result.success else None,
                "error_message": None if result.success else result.message,
            }
        ).eq("id", integration["id"]).execute()
    else:
        await db.table("integrations").upsert(
            {
                "user_id": user_id,
                "service": service,
                "category": "observability",
                "status": "connected" if result.success else "error",
                "config": {},
                "verified_at": datetime.utcnow().isoformat() if result.success else None,
                "error_message": None if result.success else result.message,
            },
            on_conflict="user_id,service",
        ).execute()

    return IntegrationStatusResponse(connected=result.success, status=result.message, error=None if result.success else result.message)


@router.delete("/{service}")
async def remove_integration(
    service: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Remove/disconnect an integration."""
    user_id = user.get("id")
    service = service.lower()

    # Get integration record
    response = await db.table("integrations").select("*").eq("user_id", user_id).eq("service", service).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration = response.data[0]
    entity_id = integration.get("composio_entity_id")

    # Disconnect via Composio
    if entity_id:
        await composio_service.disconnect(entity_id, service)

    # Delete local record
    await db.table("integrations").delete().eq("user_id", user_id).eq("service", service).execute()

    return {"status": "removed", "service": service}


@router.get("/{service}/callback")
async def oauth_callback(
    service: str = Path(...),
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db=Depends(supabase_dep),
):
    """Handle OAuth callback from Composio."""
    service = service.lower()
    
    if error:
        # Redirect to frontend with error
        frontend_url = f"{settings.FRONTEND_URL}/dashboard/integrations?error={error}&service={service}"
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=frontend_url)

    # Composio handles the token exchange internally
    # The connection should now be active
    # We just need to update the status
    
    # In a real implementation, you'd get the user_id from the state parameter
    # For now, redirect to frontend to trigger status check
    frontend_url = f"{settings.FRONTEND_URL}/dashboard/integrations?connected={service}"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=frontend_url)