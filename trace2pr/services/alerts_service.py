"""Business logic for the /alerts endpoints, backed by the `alerts` table
(see supabase/migrations/001_initial_schema.sql)."""
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from supabase import AsyncClient
from trace2pr.services.pagination import build_paginated_response, paginate_range


def _row_to_alert_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Map a DB row onto the AlertDetail schema shape. The schema's
    `raw_payload` corresponds to the DB's `payload` column."""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "source": row["source"],
        "severity": row["severity"],
        "service": row.get("service") or "",
        "raw_payload": row.get("payload") or {},
        "status": row.get("status", "new"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at") or row["created_at"],
        "incident_id": row.get("incident_id"),
    }


class AlertsService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def list_alerts(
        self,
        *,
        source: str | None,
        severity: str | None,
        status: str | None,
        service: str | None,
        since: datetime | None,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        query = self.db.table("alerts").select("*", count="exact").eq("user_id", self.user_id)
        if source:
            query = query.eq("source", source)
        if severity:
            query = query.eq("severity", severity)
        if status:
            query = query.eq("status", status)
        if service:
            query = query.eq("service", service)
        if since:
            query = query.gte("fired_at", since.isoformat())

        start, end = paginate_range(page, per_page)
        response = await query.order("fired_at", desc=True).range(start, end).execute()

        items = [_row_to_alert_detail(row) for row in (response.data or [])]
        total = response.count if response.count is not None else len(items)
        return build_paginated_response(items, total, page, per_page)

    async def get_alert_stats(self, *, since: datetime | None) -> dict[str, Any]:
        query = self.db.table("alerts").select("severity, status").eq("user_id", self.user_id)
        if since:
            query = query.gte("fired_at", since.isoformat())
        response = await query.execute()
        rows = response.data or []

        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for row in rows:
            by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + 1
            status = row.get("status", "new")
            by_status[status] = by_status.get(status, 0) + 1

        return {"total_alerts": len(rows), "by_severity": by_severity, "by_status": by_status}

    async def get_alert(self, alert_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Alert not found")
        return _row_to_alert_detail(response.data)

    async def dismiss_alert(self, alert_id: str, reason: str) -> dict[str, Any]:
        response = (
            await self.db.table("alerts")
            .update(
                {
                    "status": "dismissed",
                    "dismiss_reason": reason,
                    "dismissed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", alert_id)
            .eq("user_id", self.user_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "dismissed", "alert_id": alert_id}

    async def bulk_dismiss(self, alert_ids: list[str]) -> dict[str, Any]:
        if not alert_ids:
            return {"status": "dismissed", "count": 0}
        response = (
            await self.db.table("alerts")
            .update({"status": "dismissed", "dismissed_at": datetime.utcnow().isoformat()})
            .eq("user_id", self.user_id)
            .in_("id", alert_ids)
            .execute()
        )
        return {"status": "dismissed", "count": len(response.data or [])}
