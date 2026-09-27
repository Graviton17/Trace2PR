from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .common import FixStatus


class FileDiff(BaseModel):
    file_path: str
    diff: str
    additions: int
    deletions: int

class DiffResponse(BaseModel):
    files: List[FileDiff]
    total_additions: int
    total_deletions: int

class TestFailure(BaseModel):
    test_name: str
    file_path: str
    error_message: str

class TestResults(BaseModel):
    passed: int
    failed: int
    skipped: int
    failures: List[TestFailure]

class FixAttempt(BaseModel):
    id: str
    job_id: str
    attempt_number: int
    status: str
    created_at: datetime
    diff: Optional[DiffResponse] = None
    tests: Optional[TestResults] = None

class FixJobDetail(BaseModel):
    id: str
    incident_id: str
    status: FixStatus
    created_at: datetime
    updated_at: datetime
    attempts: List[FixAttempt] = []

class TranscriptTurn(BaseModel):
    role: str
    content: str
    timestamp: datetime
    tool_calls: Optional[List[Dict[str, Any]]] = None

class Transcript(BaseModel):
    job_id: str
    turns: List[TranscriptTurn]
