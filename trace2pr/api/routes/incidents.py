from fastapi import APIRouter, Depends, Path

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.incidents_service import IncidentsService

from ..schemas.incidents import (
    CreateIncidentRequest,
    FixRequest,
    IncidentDetail,
    TimelineResponse,
    UpdateIncidentRequest,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentDetail])
async def list_incidents(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List incidents."""
    return await IncidentsService(db, user).list_incidents()


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Incident detail, hydrated with related alert/report/fix/PR ids."""
    return await IncidentsService(db, user).get_incident(incident_id)


@router.post("", response_model=IncidentDetail)
async def create_incident(
    req: CreateIncidentRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Create an incident, optionally attaching existing alerts to it."""
    return await IncidentsService(db, user).create_incident(req)


@router.patch("/{incident_id}", response_model=IncidentDetail)
async def update_incident(
    req: UpdateIncidentRequest,
    incident_id: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Update incident status/severity."""
    return await IncidentsService(db, user).update_incident(incident_id, req)


@router.post("/{incident_id}/analyze")
async def analyze_incident(
    incident_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Queue the analysis pipeline for this incident. See
    IncidentsService.trigger_analysis for the current scope of what this
    does (job bookkeeping; the reasoning agent itself is the next phase)."""
    return await IncidentsService(db, user).trigger_analysis(incident_id)


@router.post("/{incident_id}/fix")
async def fix_incident(
    req: FixRequest,
    incident_id: str = Path(...),
    db=Depends(supabase_dep),
    user=Depends(get_current_user),
):
    """Queue the fix-generation pipeline for this incident."""
    return await IncidentsService(db, user).trigger_fix(incident_id, req.instructions)


@router.get("/{incident_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    incident_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Timeline events for an incident."""
    return await IncidentsService(db, user).get_timeline(incident_id)


@router.get("/{incident_id}/similar")
async def get_similar_incidents(
    incident_id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Similar past incidents (same service, most recent first)."""
    return await IncidentsService(db, user).get_similar_incidents(incident_id)
