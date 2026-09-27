from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .common import IncidentStatus, Severity


class IncidentBase(BaseModel):
    title: str
    description: str
    severity: Severity
    service: str

class IncidentDetail(IncidentBase):
    id: str
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    alert_ids: List[str]
    report_id: Optional[str] = None
    fix_job_id: Optional[str] = None
    pr_id: Optional[str] = None

class CreateIncidentRequest(IncidentBase):
    alert_ids: List[str] = []

class UpdateIncidentRequest(BaseModel):
    status: Optional[IncidentStatus] = None
    severity: Optional[Severity] = None

class FixRequest(BaseModel):
    instructions: Optional[str] = None

class TimelineEvent(BaseModel):
    id: str
    incident_id: str
    event_type: str
    message: str
    created_at: datetime
    metadata: Dict[str, Any] = {}

class TimelineResponse(BaseModel):
    events: List[TimelineEvent]
