"""Business logic for the /knowledge endpoints, backed by `knowledge_base`
and `knowledge_feedback`.

`knowledge_base.embedding` (pgvector) exists in the schema for future
semantic search, but nothing in this codebase generates embeddings yet
(that requires an embedding-model call on ingest, which isn't wired up).
Until that lands, search falls back to Postgres ILIKE text matching over
title/content — real results, just not semantic ones."""
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from supabase import AsyncClient


def _row_to_past_incident(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "resolution_summary": row["content"],
        "created_at": row["created_at"],
        "similarity_score": row.get("similarity_score"),
    }


def _row_to_past_fix(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "description": row["title"],
        "diff_summary": row["content"],
        "created_at": row["created_at"],
        "similarity_score": row.get("similarity_score"),
    }


class KnowledgeService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def list_past_incidents(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("knowledge_base")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("source_type", "incident")
            .order("created_at", desc=True)
            .execute()
        )
        return [_row_to_past_incident(r) for r in (response.data or [])]

    async def list_past_fixes(self) -> list[dict[str, Any]]:
        response = (
            await self.db.table("knowledge_base")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("source_type", "pr")
            .order("created_at", desc=True)
            .execute()
        )
        return [_row_to_past_fix(r) for r in (response.data or [])]

    async def search(self, query: str, limit: int, types: list[str]) -> dict[str, Any]:
        results: dict[str, Any] = {"incidents": [], "fixes": []}
        like = f"%{query}%"

        if "incidents" in types:
            resp = (
                await self.db.table("knowledge_base")
                .select("*")
                .eq("user_id", self.user_id)
                .eq("source_type", "incident")
                .or_(f"title.ilike.{like},content.ilike.{like}")
                .limit(limit)
                .execute()
            )
            results["incidents"] = [_row_to_past_incident(r) for r in (resp.data or [])]

        if "fixes" in types:
            resp = (
                await self.db.table("knowledge_base")
                .select("*")
                .eq("user_id", self.user_id)
                .eq("source_type", "pr")
                .or_(f"title.ilike.{like},content.ilike.{like}")
                .limit(limit)
                .execute()
            )
            results["fixes"] = [_row_to_past_fix(r) for r in (resp.data or [])]

        return results

    async def get_stats(self) -> dict[str, Any]:
        incidents_resp = (
            await self.db.table("knowledge_base")
            .select("id", count="exact")
            .eq("user_id", self.user_id)
            .eq("source_type", "incident")
            .execute()
        )
        fixes_resp = (
            await self.db.table("knowledge_base")
            .select("id", count="exact")
            .eq("user_id", self.user_id)
            .eq("source_type", "pr")
            .execute()
        )
        latest_resp = (
            await self.db.table("knowledge_base")
            .select("updated_at")
            .eq("user_id", self.user_id)
            .order("updated_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return {
            "total_incidents_indexed": incidents_resp.count or 0,
            "total_fixes_indexed": fixes_resp.count or 0,
            "last_updated": latest_resp.data["updated_at"] if latest_resp.data else datetime.utcnow(),
        }

    async def submit_feedback(self, item_id: str, item_type: str, helpful: bool, comments: str | None):
        item_resp = (
            await self.db.table("knowledge_base")
            .select("id")
            .eq("id", item_id)
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        if not item_resp.data:
            raise HTTPException(status_code=404, detail="Knowledge base item not found")

        await self.db.table("knowledge_feedback").insert(
            {
                "user_id": self.user_id,
                "item_id": item_id,
                "item_type": item_type,
                "helpful": helpful,
                "comments": comments,
            }
        ).execute()
        return {"status": "recorded"}
