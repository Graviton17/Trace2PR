from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class IntegrationCategory(str, Enum):
    monitoring = "monitoring"
    vcs = "vcs"
    ticketing = "ticketing"
    communication = "communication"

class Integration(BaseModel):
    id: str
    service: str
    category: IntegrationCategory
    is_active: bool
    created_at: datetime
    updated_at: datetime

class AddIntegrationRequest(BaseModel):
    service: str
    category: IntegrationCategory
    config: Optional[Dict[str, Any]] = None
    credentials: Dict[str, str]

class VerifyResult(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
