from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from .common import AlertSource, AlertStatus, PaginatedResponse, Severity


class AlertBase(BaseModel):
    title: str
    description: Optional[str] = None
    source: AlertSource
    severity: Severity
    service: str
    raw_payload: Dict[str, Any]

class AlertDetail(AlertBase):
    id: str
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    incident_id: Optional[str] = None

class AlertListResponse(PaginatedResponse[AlertDetail]):
    pass

class AlertStats(BaseModel):
    total_alerts: int
    by_severity: Dict[str, int]
    by_status: Dict[str, int]

class TestAlertRequest(BaseModel):
    source: AlertSource
    payload: Dict[str, Any]

class DismissRequest(BaseModel):
    reason: str
