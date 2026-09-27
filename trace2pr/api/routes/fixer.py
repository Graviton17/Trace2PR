from fastapi import APIRouter, Depends, Path

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.fixer_service import FixerService

from ..schemas.fixer import DiffResponse, FixAttempt, FixJobDetail, TestResults, Transcript

router = APIRouter(prefix="/fixer", tags=["fixer"])


@router.get("/jobs", response_model=list[FixJobDetail])
async def list_jobs(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List fix jobs."""
    return await FixerService(db, user).list_jobs()


@router.get("/jobs/{id}", response_model=FixJobDetail)
async def get_job(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get fix job by ID."""
    return await FixerService(db, user).get_job(id)


@router.post("/jobs/{id}/cancel")
async def cancel_job(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Cancel a running fix job."""
    return await FixerService(db, user).cancel_job(id)


@router.post("/jobs/{id}/retry")
async def retry_job(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Retry a failed/cancelled fix job."""
    return await FixerService(db, user).retry_job(id)


@router.get("/jobs/{id}/attempts", response_model=list[FixAttempt])
async def list_attempts(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List attempts for a job."""
    return await FixerService(db, user).list_attempts(id)


@router.get("/jobs/{id}/attempts/{n}/diff", response_model=DiffResponse)
async def get_attempt_diff(
    id: str = Path(...), n: int = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Get diff for an attempt."""
    return await FixerService(db, user).get_attempt_diff(id, n)


@router.get("/jobs/{id}/attempts/{n}/tests", response_model=TestResults)
async def get_attempt_tests(
    id: str = Path(...), n: int = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Get test results for an attempt."""
    return await FixerService(db, user).get_attempt_tests(id, n)


@router.get("/jobs/{id}/transcript", response_model=Transcript)
async def get_job_transcript(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get the agent transcript for a job."""
    return await FixerService(db, user).get_transcript(id)
