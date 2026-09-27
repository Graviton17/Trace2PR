"""Webhook receivers for monitoring tools (via Composio or direct)."""
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.config.settings import settings
from trace2pr.db.supabase_client import supabase_dep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================
# Composio Webhook Handler
# =============================================

@router.post("/composio")
async def composio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db=Depends(supabase_dep),
    x_composio_signature: str | None = Header(None),
    x_composio_timestamp: str | None = Header(None),
):
    """Receive webhooks from Composio. Composio forwards events from
    connected apps (Datadog, Sentry, PagerDuty, etc.)."""
    body = await request.body()

    # Verify Composio signature if configured
    if settings.COMPOSIO_API_KEY and x_composio_signature and x_composio_timestamp:
        if not _verify_composio_signature(body, x_composio_signature, x_composio_timestamp):
            raise HTTPException(status_code=401, detail="Invalid Composio signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    log_id = await _log_webhook(db, "composio", payload.get("event_type"), payload, dict(request.headers))
    background_tasks.add_task(_process_composio_webhook, db, payload, log_id)

    return {"status": "received"}


def _verify_composio_signature(payload: bytes, signature: str, timestamp: str) -> bool:
    """Verify Composio webhook signature (HMAC-SHA256, API key as secret)."""
    expected = hmac.new(
        settings.COMPOSIO_API_KEY.encode(),
        f"{timestamp}.{payload.decode()}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


async def _process_composio_webhook(db, payload: dict[str, Any], log_id: str | None):
    """Process Composio webhook payload."""
    event_type = payload.get("event_type")
    connection_id = payload.get("connection_id")
    event_data = payload.get("payload", {})

    response = (
        await db.table("integrations").select("*").eq("composio_connection_id", connection_id).execute()
    )

    if not response.data:
        logger.warning("No integration found for Composio connection_id=%s", connection_id)
        return

    integration = response.data[0]
    user_id = integration["user_id"]
    service = integration["service"]

    if event_type in ["alert.triggered", "incident.created", "alert.fired"]:
        await _create_incident_from_webhook(db, user_id, service, event_data, event_type)
    elif event_type in ["alert.resolved", "incident.resolved"]:
        await _resolve_incident_from_webhook(db, user_id, service, event_data)

    # NOTE: `webhook_logs` has no `connection_id` column — mark the specific
    # log row we created in `_log_webhook` as processed, by its own id.
    if log_id:
        await db.table("webhook_logs").update({"processed": True}).eq("id", log_id).execute()


async def _create_incident_from_webhook(
    db, user_id: str, service: str, event_data: dict[str, Any], event_type: str
):
    """Create incident from webhook event."""
    title = event_data.get("title") or event_data.get("name") or f"{service} Alert"
    severity = _map_severity(event_data.get("severity") or event_data.get("priority") or "medium")
    description = event_data.get("description") or event_data.get("message") or json.dumps(event_data)
    source_incident_id = event_data.get("id") or event_data.get("incident_id") or event_data.get("alert_id")
    service_name = event_data.get("service") or event_data.get("host") or service
    environment = event_data.get("environment") or event_data.get("env") or "production"

    incident_data = {
        "user_id": user_id,
        "title": title,
        "severity": severity,
        "service": service_name,
        "environment": environment,
        "description": description,
        "source": service,
        "source_incident_id": source_incident_id,
        "status": "open",
    }

    result = await db.table("incidents").insert(incident_data).execute()

    if result.data:
        incident = result.data[0]
        await db.table("timeline_events").insert(
            {
                "incident_id": incident["id"],
                "event_type": "incident_created",
                "title": f"Incident created from {service}",
                "detail": f"Auto-created from {event_type} webhook",
                "metadata": {"source": service, "webhook_event": event_type, "raw_data": event_data},
            }
        ).execute()


async def _resolve_incident_from_webhook(db, user_id: str, service: str, event_data: dict[str, Any]):
    """Resolve incident from webhook event."""
    source_incident_id = event_data.get("id") or event_data.get("incident_id") or event_data.get("alert_id")

    if not source_incident_id:
        return

    response = (
        await db.table("incidents")
        .select("*")
        .eq("user_id", user_id)
        .eq("source_incident_id", source_incident_id)
        .execute()
    )

    if response.data:
        incident = response.data[0]
        await db.table("incidents").update(
            {"status": "resolved", "resolved_at": "now()"}
        ).eq("id", incident["id"]).execute()

        await db.table("timeline_events").insert(
            {
                "incident_id": incident["id"],
                "event_type": "incident_resolved",
                "title": f"Incident resolved via {service}",
                "detail": "Auto-resolved from webhook",
                "metadata": {"source": service, "raw_data": event_data},
            }
        ).execute()


async def _log_webhook(
    db, source: str, event_type: str | None, payload: dict[str, Any], headers: dict[str, str]
) -> str | None:
    """Log webhook for debugging. Returns the created log row's id."""
    connection_id = payload.get("connection_id")
    user_id = None
    integration_id = None

    if connection_id:
        response = (
            await db.table("integrations")
            .select("user_id, id")
            .eq("composio_connection_id", connection_id)
            .execute()
        )
        if response.data:
            user_id = response.data[0]["user_id"]
            integration_id = response.data[0]["id"]

    result = (
        await db.table("webhook_logs")
        .insert(
            {
                "user_id": user_id,
                "integration_id": integration_id,
                "source": source,
                "event_type": event_type,
                "payload": payload,
                "headers": headers,
            }
        )
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def _map_severity(severity: str) -> str:
    """Map various severity formats to standard levels."""
    severity = severity.lower()
    if severity in ["critical", "p0", "sev0", "emergency", "fatal"]:
        return "critical"
    elif severity in ["high", "p1", "sev1", "major", "error"]:
        return "high"
    elif severity in ["medium", "p2", "sev2", "warning", "warn"]:
        return "medium"
    elif severity in ["low", "p3", "sev3", "info", "minor"]:
        return "low"
    return "medium"


# =============================================
# Direct Webhook Endpoints (fallback for non-Composio)
# =============================================

async def _find_connected_integration(db, source: str) -> dict[str, Any] | None:
    """Resolve which user a direct (non-Composio) webhook belongs to.

    Direct webhook senders (Datadog, Sentry, etc.) can't carry a Supabase
    auth token, so there's no per-request user context. As a stand-in until
    per-integration webhook URLs/secrets exist, we match the single
    connected integration for that service. This assumes at most one
    connected integration per service across the deployment — fine for a
    single-tenant/dev setup, but a real multi-tenant deployment needs a
    per-integration webhook token embedded in the URL instead."""
    response = (
        await db.table("integrations")
        .select("*")
        .eq("service", source)
        .eq("status", "connected")
        .limit(2)
        .execute()
    )
    rows = response.data or []
    if len(rows) != 1:
        if len(rows) > 1:
            logger.warning(
                "Multiple connected '%s' integrations found; cannot route direct webhook to a user", source
            )
        return None
    return rows[0]


def _verify_shared_secret(body: bytes, provided_signature: str | None, configured_secret: str | None) -> bool:
    """Constant-time compare against a per-integration shared secret, when
    one is configured on `integrations.config.webhook_secret`. If nothing is
    configured we can't verify, so the caller should log and proceed with
    caution rather than reject (most of these tools don't sign requests by
    default without extra setup on both ends)."""
    if not configured_secret or not provided_signature:
        return False
    expected = hmac.new(configured_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided_signature, expected)


@router.post("/datadog")
async def datadog_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db=Depends(supabase_dep),
    x_datadog_signature: str | None = Header(None),
):
    """Direct Datadog webhook endpoint (if not using Composio)."""
    body = await request.body()
    payload = await request.json()

    integration = await _find_connected_integration(db, "datadog")
    configured_secret = (integration or {}).get("config", {}).get("webhook_secret")
    if configured_secret and not _verify_shared_secret(body, x_datadog_signature, configured_secret):
        raise HTTPException(status_code=401, detail="Invalid Datadog webhook signature")
    if not configured_secret:
        logger.info("No webhook_secret configured for datadog integration; accepting unverified")

    await _log_webhook(db, "datadog", payload.get("event_type"), payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, "datadog", payload, integration)

    return {"status": "received"}


@router.post("/sentry")
async def sentry_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(supabase_dep)):
    """Direct Sentry webhook endpoint."""
    payload = await request.json()
    integration = await _find_connected_integration(db, "sentry")
    await _log_webhook(db, "sentry", "event", payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, "sentry", payload, integration)
    return {"status": "received"}


@router.post("/pagerduty")
async def pagerduty_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(supabase_dep)):
    """Direct PagerDuty webhook endpoint."""
    payload = await request.json()
    integration = await _find_connected_integration(db, "pagerduty")
    await _log_webhook(db, "pagerduty", "event", payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, "pagerduty", payload, integration)
    return {"status": "received"}


@router.post("/grafana")
async def grafana_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(supabase_dep)):
    """Direct Grafana webhook endpoint."""
    payload = await request.json()
    integration = await _find_connected_integration(db, "grafana")
    await _log_webhook(db, "grafana", "alert", payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, "grafana", payload, integration)
    return {"status": "received"}


@router.post("/cloudwatch")
async def cloudwatch_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(supabase_dep)):
    """Direct AWS CloudWatch/SNS webhook endpoint."""
    payload = await request.json()
    integration = await _find_connected_integration(db, "cloudwatch")
    await _log_webhook(db, "cloudwatch", "alarm", payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, "cloudwatch", payload, integration)
    return {"status": "received"}


@router.post("/generic")
async def generic_webhook(request: Request, background_tasks: BackgroundTasks, db=Depends(supabase_dep)):
    """Generic webhook endpoint for custom integrations."""
    payload = await request.json()
    source = payload.get("source", "generic")
    integration = await _find_connected_integration(db, source)
    await _log_webhook(db, source, "custom", payload, dict(request.headers))
    background_tasks.add_task(_process_direct_webhook, db, source, payload, integration)
    return {"status": "received"}


async def _process_direct_webhook(db, source: str, payload: dict[str, Any], integration: dict[str, Any] | None):
    """Process a direct (non-Composio) webhook by creating/resolving an
    incident for whichever user owns the matched integration. If we
    couldn't uniquely resolve an owning user, we only log it (see
    `_find_connected_integration`)."""
    if not integration:
        logger.info("Direct '%s' webhook received but no owning user could be resolved; logged only", source)
        return

    user_id = integration["user_id"]
    event_type = payload.get("event_type") or payload.get("event") or ""
    if any(k in str(event_type).lower() for k in ("resolved", "recovered", "ok")):
        await _resolve_incident_from_webhook(db, user_id, source, payload)
    else:
        await _create_incident_from_webhook(db, user_id, source, payload, str(event_type) or "webhook")


# =============================================
# Webhook Management
# =============================================

@router.get("/logs")
async def get_webhook_logs(
    limit: int = 50,
    offset: int = 0,
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Get webhook logs for debugging."""
    response = (
        await db.table("webhook_logs")
        .select("*")
        .eq("user_id", user.get("id"))
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data
