from fastapi import APIRouter, Depends, Path

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.analysis_service import AnalysisService

from ..schemas.analysis import AnalysisJob, DiagnosticReport

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/reports", response_model=list[DiagnosticReport])
async def list_reports(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List all diagnostic reports."""
    return await AnalysisService(db, user).list_reports()


@router.get("/reports/{report_id}", response_model=DiagnosticReport)
async def get_report(
    report_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Get a single diagnostic report."""
    return await AnalysisService(db, user).get_report(report_id)


@router.get("/jobs/{job_id}", response_model=AnalysisJob)
async def get_job_status(
    job_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Get status of an analysis job."""
    return await AnalysisService(db, user).get_job(job_id)
