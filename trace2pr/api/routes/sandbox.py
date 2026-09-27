from fastapi import APIRouter, Depends, Path

from trace2pr.api.middleware.auth import get_current_user
from trace2pr.db.supabase_client import supabase_dep
from trace2pr.services.sandbox_service import SandboxService

from ..schemas.sandbox import (
    CreateSandboxRequest,
    ExecRequest,
    ExecResult,
    ResourceUsage,
    SandboxInstance,
    SandboxTemplate,
)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@router.get("/instances", response_model=list[SandboxInstance])
async def list_instances(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List sandbox instances belonging to the current user."""
    return await SandboxService(db, user).list_instances()


@router.get("/instances/{id}", response_model=SandboxInstance)
async def get_instance(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Get instance by ID."""
    return await SandboxService(db, user).get_instance(id)


@router.post("/instances", response_model=SandboxInstance)
async def create_instance(
    req: CreateSandboxRequest, db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Create a new sandbox instance via E2B."""
    return await SandboxService(db, user).create_instance(req.template_id, req.timeout_seconds or 3600)


@router.delete("/instances/{id}")
async def delete_instance(id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Delete (kill) a sandbox instance."""
    return await SandboxService(db, user).delete_instance(id)


@router.get("/instances/{id}/logs")
async def get_instance_logs(
    id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Execution audit trail for an instance."""
    return await SandboxService(db, user).get_instance_logs(id)


@router.post("/instances/{id}/exec", response_model=ExecResult)
async def execute_command(
    req: ExecRequest, id: str = Path(...), db=Depends(supabase_dep), user=Depends(get_current_user)
):
    """Execute a command in a sandbox instance."""
    return await SandboxService(db, user).execute_command(id, req.command, req.cwd, req.timeout or 30)


@router.get("/templates", response_model=list[SandboxTemplate])
async def list_templates(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """List available sandbox templates."""
    return await SandboxService(db, user).list_templates()


@router.get("/usage", response_model=list[ResourceUsage])
async def get_usage(db=Depends(supabase_dep), user=Depends(get_current_user)):
    """Overall resource usage across the user's active sandboxes."""
    return await SandboxService(db, user).get_usage()
