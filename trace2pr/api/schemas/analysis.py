from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    service: str

class CommitInfo(BaseModel):
    sha: str
    author: str
    message: str
    date: str

class SuspectedFile(BaseModel):
    path: str
    reason: str
    confidence_score: float

class Evidence(BaseModel):
    logs: List[LogEntry] = []
    commits: List[CommitInfo] = []
    traces: List[Dict[str, Any]] = []

class DiagnosticReport(BaseModel):
    id: str
    incident_id: str
    summary: str
    root_cause_hypothesis: str
    suspected_files: List[SuspectedFile]
    evidence: Evidence
    created_at: datetime

class AnalysisJob(BaseModel):
    id: str
    incident_id: str
    status: str
    created_at: datetime
    report: Optional[DiagnosticReport] = None
