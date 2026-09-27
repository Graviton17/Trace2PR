"""Business logic for the /incidents endpoints, backed by the `incidents`,
`alerts`, `timeline_events`, `analysis_jobs`/`analysis_reports`, `fix_jobs`
and `pull_requests` tables."""
import logging
from typing import Any

from fastapi import HTTPException

from supabase import AsyncClient

logger = logging.getLogger(__name__)


async def _latest_id(db: AsyncClient, table: str, incident_id: str, id_col: str = "id") -> str | None:
    response = (
        await db.table(table)
        .select(id_col)
        .eq("incident_id", incident_id)
        .order("created_at", desc=True)
        .limit(1)
        .maybe_single()
        .execute()
    )
    return response.data.get(id_col) if response.data else None


class IncidentsService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def _hydrate(self, row: dict[str, Any]) -> dict[str, Any]:
        incident_id = row["id"]
        alerts_resp = (
            await self.db.table("alerts").select("id").eq("incident_id", incident_id).execute()
        )
        alert_ids = [a["id"] for a in (alerts_resp.data or [])]

        report_id = await _latest_id(self.db, "analysis_reports", incident_id)
        fix_job_id = await _latest_id(self.db, "fix_jobs", incident_id)
        pr_id = await _latest_id(self.db, "pull_requests", incident_id)

        return {
            "id": incident_id,
            "title": row["title"],
            "description": row.get("description") or "",
            "severity": row["severity"],
            "service": row.get("service") or "",
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row.get("updated_at") or row["created_at"],
            "alert_ids": alert_ids,
            "report_id": report_id,
            "fix_job_id": fix_job_id,
            "pr_id": pr_id,
        }

    async def list_incidents(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("incidents")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [await self._hydrate(row) for row in (response.data or [])]

    async def _get_row(self, incident_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("incidents")
            .select("*")
            .eq("id", incident_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Incident not found")
        return response.data

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        row = await self._get_row(incident_id)
        return await self._hydrate(row)

    async def create_incident(self, req) -> dict[str, Any]:
        insert_data = {
            "user_id": self.user_id,
            "title": req.title,
            "description": req.description,
            "severity": req.severity.value,
            "service": req.service,
            "status": "open",
            "source": "manual",
        }
        response = await self.db.table("incidents").insert(insert_data).execute()
        incident = response.data[0]

        if req.alert_ids:
            await (
                self.db.table("alerts")
                .update({"incident_id": incident["id"]})
                .in_("id", req.alert_ids)
                .eq("user_id", self.user_id)
                .execute()
            )

        await self.db.table("timeline_events").insert(
            {
                "incident_id": incident["id"],
                "event_type": "incident_created",
                "title": "Incident created",
                "detail": "Created manually via API",
            }
        ).execute()

        return await self._hydrate(incident)

    async def update_incident(self, incident_id: str, req) -> dict[str, Any]:
        await self._get_row(incident_id)  # 404s if missing / not owned
        update_data: dict[str, Any] = {}
        if req.status is not None:
            update_data["status"] = req.status.value
            if req.status.value == "resolved":
                update_data["resolved_at"] = "now()"
        if req.severity is not None:
            update_data["severity"] = req.severity.value

        if update_data:
            await self.db.table("incidents").update(update_data).eq("id", incident_id).execute()
            await self.db.table("timeline_events").insert(
                {
                    "incident_id": incident_id,
                    "event_type": "incident_updated",
                    "title": "Incident updated",
                    "detail": f"Fields changed: {', '.join(update_data.keys())}",
                }
            ).execute()

        return await self.get_incident(incident_id)

    async def trigger_analysis(self, incident_id: str) -> dict[str, Any]:
        """Creates a queued analysis job. Executing the actual root-cause
        analysis (log/trace correlation, LLM reasoning) is the next phase of
        the pipeline per the project's design doc and isn't implemented yet —
        this wires up the job bookkeeping so the frontend/API contract is
        real and the agent loop can be dropped in without another API
        change."""
        await self._get_row(incident_id)
        response = (
            await self.db.table("analysis_jobs")
            .insert({"user_id": self.user_id, "incident_id": incident_id, "status": "queued"})
            .execute()
        )
        job = response.data[0]

        await self.db.table("incidents").update({"status": "analyzing"}).eq("id", incident_id).execute()
        await self.db.table("timeline_events").insert(
            {
                "incident_id": incident_id,
                "event_type": "analysis_started",
                "title": "Analysis queued",
                "metadata": {"analysis_job_id": job["id"]},
            }
        ).execute()

        return {"job_id": job["id"], "status": job["status"]}

    async def trigger_fix(self, incident_id: str, instructions: str | None) -> dict[str, Any]:
        """See `trigger_analysis` docstring — same scope note applies to the
        fix-generation agent loop."""
        await self._get_row(incident_id)
        response = (
            await self.db.table("fix_jobs")
            .insert(
                {
                    "user_id": self.user_id,
                    "incident_id": incident_id,
                    "status": "queued",
                    "instructions": instructions,
                }
            )
            .execute()
        )
        job = response.data[0]

        await self.db.table("incidents").update({"status": "fixing"}).eq("id", incident_id).execute()
        await self.db.table("timeline_events").insert(
            {
                "incident_id": incident_id,
                "event_type": "fix_generated",
                "title": "Fix job queued",
                "metadata": {"fix_job_id": job["id"]},
            }
        ).execute()

        return {"job_id": job["id"], "status": job["status"]}

    async def get_timeline(self, incident_id: str) -> dict[str, Any]:
        await self._get_row(incident_id)
        response = (
            await self.db.table("timeline_events")
            .select("*")
            .eq("incident_id", incident_id)
            .order("created_at")
            .execute()
        )
        events = [
            {
                "id": e["id"],
                "incident_id": incident_id,
                "event_type": e["event_type"],
                "message": e.get("detail") or e["title"],
                "created_at": e["created_at"],
                "metadata": e.get("metadata") or {},
            }
            for e in (response.data or [])
        ]
        return {"events": events}

    async def get_similar_incidents(self, incident_id: str) -> list[dict[str, Any]]:
        """Naive similarity by matching service + severity, most recent
        first. A proper implementation would use the knowledge_base's vector
        embeddings — see knowledge_service for the current keyword-search
        stand-in for that."""
        row = await self._get_row(incident_id)
        response = (
            await self.db.table("incidents")
            .select("id, title, status, severity, service, created_at")
            .eq("user_id", self.user_id)
            .eq("service", row.get("service"))
            .neq("id", incident_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        return response.data or []
