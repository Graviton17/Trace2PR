from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SandboxTemplate(BaseModel):
    id: str
    name: str
    description: str
    base_image: str

class SandboxInstance(BaseModel):
    id: str
    template_id: str
    status: str
    created_at: datetime
    expires_at: datetime

class ResourceUsage(BaseModel):
    cpu_percent: float
    memory_mb: float
    disk_mb: float

class CreateSandboxRequest(BaseModel):
    template_id: str
    timeout_seconds: Optional[int] = 3600

class ExecRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: Optional[int] = 30

class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
