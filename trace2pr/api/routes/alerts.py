from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.alerts_service import AlertsService

from ..schemas.alerts import AlertDetail, AlertListResponse, AlertStats, DismissRequest
from ..schemas.common import AlertSource, AlertStatus, Severity

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    source: AlertSource | None = None,
    severity: Severity | None = None,
    status: AlertStatus | None = None,
    service: str | None = None,
    since: datetime | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """List alerts with filtering options."""
    svc = AlertsService(db, user)
    return await svc.list_alerts(
        source=source.value if source else None,
        severity=severity.value if severity else None,
        status=status.value if status else None,
        service=service,
        since=since,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    since: datetime | None = None,
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Alert statistics by timeframe."""
    svc = AlertsService(db, user)
    return await svc.get_alert_stats(since=since)


@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert(
    alert_id: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Get alert details."""
    svc = AlertsService(db, user)
    return await svc.get_alert(alert_id)


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(
    req: DismissRequest,
    alert_id: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Dismiss an alert."""
    svc = AlertsService(db, user)
    return await svc.dismiss_alert(alert_id, req.reason)


@router.post("/bulk-dismiss")
async def bulk_dismiss_alerts(
    alert_ids: list[str],
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Dismiss multiple alerts."""
    svc = AlertsService(db, user)
    return await svc.bulk_dismiss(alert_ids)
