from enum import Enum
from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

class AlertSource(str, Enum):
    datadog = "datadog"
    cloudwatch = "cloudwatch"
    sentry = "sentry"
    pagerduty = "pagerduty"
    grafana = "grafana"
    generic = "generic"

class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

class AlertStatus(str, Enum):
    new = "new"
    acknowledged = "acknowledged"
    processing = "processing"
    resolved = "resolved"
    dismissed = "dismissed"

class IncidentStatus(str, Enum): 
    open = "open"
    analyzing = "analyzing"
    fixing = "fixing"
    pr_created = "pr_created"
    resolved = "resolved"
    escalated = "escalated"

class FixStatus(str, Enum): 
    queued = "queued"
    sandbox_creating = "sandbox_creating"
    cloning = "cloning"
    analyzing = "analyzing"
    fixing = "fixing"
    testing = "testing"
    pr_creating = "pr_creating"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class PRStatus(str, Enum): 
    open = "open"
    merged = "merged"
    closed = "closed"
    changes_requested = "changes_requested"

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int
