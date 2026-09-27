from fastapi import APIRouter, Depends

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.knowledge_service import KnowledgeService

from ..schemas.knowledge import (
    FeedbackRequest,
    KBStats,
    PastFix,
    PastIncident,
    SearchRequest,
    SearchResults,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/incidents", response_model=list[PastIncident])
async def list_past_incidents(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List past incidents indexed in the knowledge base."""
    return await KnowledgeService(db, user).list_past_incidents()


@router.get("/fixes", response_model=list[PastFix])
async def list_past_fixes(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List past fixes indexed in the knowledge base."""
    return await KnowledgeService(db, user).list_past_fixes()


@router.post("/search", response_model=SearchResults)
async def search_knowledge(
    req: SearchRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Search the knowledge base (keyword match; see KnowledgeService for
    the current scope vs. planned vector/semantic search)."""
    return await KnowledgeService(db, user).search(req.query, req.limit, req.types)


@router.get("/stats", response_model=KBStats)
async def get_kb_stats(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get knowledge base stats."""
    return await KnowledgeService(db, user).get_stats()


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Submit feedback on a knowledge base item."""
    return await KnowledgeService(db, user).submit_feedback(
        req.item_id, req.item_type, req.helpful, req.comments
    )
