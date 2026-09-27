from fastapi import APIRouter, Depends, Path

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.prs_service import PRsService

from ..schemas.prs import CIStatus, PRDetail, PRStats

router = APIRouter(prefix="/prs", tags=["prs"])


@router.get("", response_model=list[PRDetail])
async def list_prs(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List PRs."""
    return await PRsService(db, user).list_prs()


@router.get("/stats", response_model=PRStats)
async def get_pr_stats(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get PR statistics."""
    return await PRsService(db, user).get_stats()


@router.get("/{pr_id}", response_model=PRDetail)
async def get_pr(pr_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get PR by ID."""
    return await PRsService(db, user).get_pr(pr_id)


@router.get("/{pr_id}/ci-status", response_model=CIStatus)
async def get_pr_ci_status(
    pr_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Get live CI status for a PR from GitHub."""
    return await PRsService(db, user).get_ci_status(pr_id)
