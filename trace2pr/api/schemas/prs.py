from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .common import PRStatus


class CICheck(BaseModel):
    name: str
    status: str
    conclusion: Optional[str] = None
    url: str

class CIStatus(BaseModel):
    state: str
    checks: List[CICheck]

class PRDetail(BaseModel):
    id: str
    provider_pr_id: str
    incident_id: str
    title: str
    url: str
    status: PRStatus
    created_at: datetime
    updated_at: datetime
    ci_status: Optional[CIStatus] = None

class PRStats(BaseModel):
    total_prs: int
    merged_prs: int
    average_merge_time_minutes: float
