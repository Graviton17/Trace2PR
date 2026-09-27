"""Business logic for the /fixer endpoints, backed by `fix_jobs` and
`fix_attempts`. Job creation happens from IncidentsService.trigger_fix();
actually running the fix-generation agent (sandbox + LLM loop) is the next
phase of the pipeline (see project design doc) — jobs otherwise sit in
`queued`/`failed` state, and cancel/retry below just flip status so the
API contract is real once the agent is wired in."""
from typing import Any

from fastapi import HTTPException

from supabase import AsyncClient

_CANCELLABLE_STATUSES = {
    "queued",
    "sandbox_creating",
    "cloning",
    "analyzing",
    "fixing",
    "testing",
    "pr_creating",
}


def _row_to_job(row: dict[str, Any], attempts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "incident_id": row["incident_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at") or row["created_at"],
        "attempts": attempts or [],
    }


def _row_to_attempt(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["fix_job_id"],
        "attempt_number": row["attempt_number"],
        "status": row["status"],
        "created_at": row["created_at"],
        "diff": row.get("diff"),
        "tests": row.get("test_results"),
    }


class FixerService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def _get_job_row(self, job_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("fix_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Fix job not found")
        return response.data

    async def _get_attempts(self, job_id: str) -> list[dict[str, Any]]:
        response = (
            await self.db.table("fix_attempts")
            .select("*")
            .eq("fix_job_id", job_id)
            .order("attempt_number")
            .execute()
        )
        return [_row_to_attempt(a) for a in (response.data or [])]

    async def list_jobs(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("fix_jobs")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        jobs = response.data or []
        return [_row_to_job(job, await self._get_attempts(job["id"])) for job in jobs]

    async def get_job(self, job_id: str) -> dict[str, Any]:
        row = await self._get_job_row(job_id)
        return _row_to_job(row, await self._get_attempts(job_id))

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        row = await self._get_job_row(job_id)
        if row["status"] not in _CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=409, detail=f"Cannot cancel a job in status '{row['status']}'"
            )
        await self.db.table("fix_jobs").update({"status": "cancelled"}).eq("id", job_id).execute()
        return {"id": job_id, "status": "cancelled"}

    async def retry_job(self, job_id: str) -> dict[str, Any]:
        row = await self._get_job_row(job_id)
        if row["status"] not in ("failed", "cancelled"):
            raise HTTPException(
                status_code=409, detail=f"Cannot retry a job in status '{row['status']}'"
            )
        await self.db.table("fix_jobs").update({"status": "queued"}).eq("id", job_id).execute()
        return {"id": job_id, "status": "queued"}

    async def list_attempts(self, job_id: str) -> list[dict[str, Any]]:
        await self._get_job_row(job_id)
        return await self._get_attempts(job_id)

    async def _get_attempt_row(self, job_id: str, attempt_number: int) -> dict[str, Any]:
        await self._get_job_row(job_id)
        response = (
            await self.db.table("fix_attempts")
            .select("*")
            .eq("fix_job_id", job_id)
            .eq("attempt_number", attempt_number)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Fix attempt not found")
        return response.data

    async def get_attempt_diff(self, job_id: str, attempt_number: int) -> dict[str, Any]:
        row = await self._get_attempt_row(job_id, attempt_number)
        if not row.get("diff"):
            raise HTTPException(status_code=404, detail="No diff recorded for this attempt yet")
        return row["diff"]

    async def get_attempt_tests(self, job_id: str, attempt_number: int) -> dict[str, Any]:
        row = await self._get_attempt_row(job_id, attempt_number)
        if not row.get("test_results"):
            raise HTTPException(status_code=404, detail="No test results recorded for this attempt yet")
        return row["test_results"]

    async def get_transcript(self, job_id: str) -> dict[str, Any]:
        row = await self._get_job_row(job_id)
        return {"job_id": job_id, "turns": row.get("transcript") or []}
