"""Business logic for the /prs endpoints, backed by `pull_requests`.
CI status is fetched live from GitHub (not stored) since it changes
independently of our own records."""
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from supabase import AsyncClient
from trace2pr.integrations.resolver import IntegrationResolver

logger = logging.getLogger(__name__)


def _row_to_pr(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider_pr_id": str(row.get("github_pr_id") or ""),
        "incident_id": row.get("incident_id") or "",
        "title": row["title"],
        "url": row.get("html_url") or "",
        "status": row["status"] if row["status"] in ("open", "merged", "closed") else "open",
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at") or row["created_at"],
        "ci_status": None,
    }


class PRsService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]
        self.user_id_full = user

    async def list_prs(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("pull_requests")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [_row_to_pr(r) for r in (response.data or [])]

    async def get_stats(self) -> dict[str, Any]:
        response = (
            await self.db.table("pull_requests")
            .select("status, created_at, merged_at")
            .eq("user_id", self.user_id)
            .execute()
        )
        rows = response.data or []
        total = len(rows)
        merged = [r for r in rows if r["status"] == "merged" and r.get("merged_at")]

        avg_minutes = 0.0
        if merged:
            from datetime import datetime

            def _parse(ts: str) -> datetime:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))

            total_minutes = sum(
                (_parse(r["merged_at"]) - _parse(r["created_at"])).total_seconds() / 60
                for r in merged
            )
            avg_minutes = total_minutes / len(merged)

        return {
            "total_prs": total,
            "merged_prs": len(merged),
            "average_merge_time_minutes": round(avg_minutes, 1),
        }

    async def _get_row(self, pr_id: str) -> dict[str, Any]:
        response = (
            await self.db.table("pull_requests")
            .select("*")
            .eq("id", pr_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Pull request not found")
        return response.data

    async def get_pr(self, pr_id: str) -> dict[str, Any]:
        return _row_to_pr(await self._get_row(pr_id))

    async def get_ci_status(self, pr_id: str) -> dict[str, Any]:
        row = await self._get_row(pr_id)
        repository = row.get("repository")
        ref = row.get("branch_name")
        if not repository or not ref:
            return {"state": "unknown", "checks": []}

        creds = await IntegrationResolver().resolve("github", self.user_id, self.db)
        token = creds.get("token") if creds else None
        if not token:
            logger.info("No GitHub credentials configured; cannot fetch CI status for PR %s", pr_id)
            return {"state": "unknown", "checks": []}

        url = f"https://api.github.com/repos/{repository}/commits/{ref}/check-runs"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            logger.exception("Failed to fetch CI status from GitHub for PR %s", pr_id)
            return {"state": "unknown", "checks": []}

        checks = [
            {
                "name": run["name"],
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url") or "",
            }
            for run in data.get("check_runs", [])
        ]
        if not checks:
            state = "unknown"
        elif any(c["conclusion"] == "failure" for c in checks):
            state = "failure"
        elif any(c["status"] != "completed" for c in checks):
            state = "pending"
        else:
            state = "success"

        return {"state": state, "checks": checks}
