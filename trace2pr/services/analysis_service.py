"""Business logic for the /analysis endpoints, backed by the
`analysis_jobs` and `analysis_reports` tables.

Job *creation* happens from IncidentsService.trigger_analysis(); this
service covers reading job/report state back out. Actually running the
root-cause analysis (correlating logs/traces, producing the report) is the
reasoning-agent work called out as still being designed in the project
notes — jobs sit in `queued` until that lands."""
from typing import Any

from fastapi import HTTPException

from supabase import AsyncClient


def _row_to_report(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "summary": row["summary"],
        "root_cause_hypothesis": row.get("root_cause_hypothesis") or "",
        "suspected_files": row.get("suspected_files") or [],
        "evidence": row.get("evidence") or {"logs": [], "commits": [], "traces": []},
        "created_at": row["created_at"],
    }


class AnalysisService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def get_job(self, job_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("analysis_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        job = response.data

        report = None
        report_resp = (
            await self.db.table("analysis_reports")
            .select("*")
            .eq("analysis_job_id", job_id)
            .maybe_single()
            .execute()
        )
        if report_resp.data:
            report = _row_to_report(report_resp.data)

        return {
            "id": job["id"],
            "incident_id": job["incident_id"],
            "status": job["status"],
            "created_at": job["created_at"],
            "report": report,
        }

    async def list_reports(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("analysis_reports")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [_row_to_report(row) for row in (response.data or [])]

    async def get_report(self, report_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("analysis_reports")
            .select("*")
            .eq("id", report_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Analysis report not found")
        return _row_to_report(response.data)
