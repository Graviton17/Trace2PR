"""Business logic for the /sandbox endpoints, backed by the real E2B SDK
(e2b-code-interpreter). Sandbox instances live in E2B, not our own DB;
we scope them to the current user via E2B sandbox metadata and log each
command execution to the `sandbox_executions` table for audit history."""
import logging
from datetime import datetime, timedelta
from typing import Any

from e2b.exceptions import SandboxException
from e2b.sandbox.sandbox_api import SandboxQuery
from e2b_code_interpreter import AsyncSandbox
from fastapi import HTTPException

from supabase import AsyncClient
from trace2pr.api.middleware.errors import SandboxCreationError
from trace2pr.config.settings import settings

logger = logging.getLogger(__name__)

# E2B doesn't expose a "list available templates" API in this SDK; templates
# are provisioned per-account via the E2B dashboard/CLI. We surface the
# default template plus any explicitly configured here so the endpoint
# returns real, usable IDs rather than fabricated ones.
_KNOWN_TEMPLATES = [
    {
        "id": "base",
        "name": "Base",
        "description": "Default E2B sandbox: Debian + common CLI tooling.",
        "base_image": "e2b.dev/base",
    },
]


def _info_to_instance(info) -> dict[str, Any]:
    return {
        "id": info.sandbox_id,
        "template_id": info.template_id,
        "status": info.state.value if hasattr(info.state, "value") else str(info.state),
        "created_at": info.started_at,
        "expires_at": info.end_at,
    }


async def _list_user_sandboxes(user_id: str) -> list:
    """Drains the E2B list paginator (which uses has_next/next_items, not
    async-for) into a flat list of SandboxInfo scoped to this user."""
    paginator = AsyncSandbox.list(
        query=SandboxQuery(metadata={"user_id": user_id}), api_key=settings.E2B_API_KEY
    )
    infos = []
    while True:
        page = await paginator.next_items()
        infos.extend(page)
        if not paginator.has_next:
            break
    return infos


class SandboxService:
    def __init__(self, db: AsyncClient, user: dict):
        self.db = db
        self.user_id = user["id"]

    async def list_instances(self) -> list[dict[str, Any]]:
        try:
            infos = await _list_user_sandboxes(self.user_id)
        except SandboxException:
            logger.exception("Failed to list E2B sandboxes for user %s", self.user_id)
            return []
        return [_info_to_instance(info) for info in infos]

    async def _connect(self, instance_id: str) -> AsyncSandbox:
        try:
            sbx = await AsyncSandbox.connect(instance_id, api_key=settings.E2B_API_KEY)
        except SandboxException as e:
            raise HTTPException(status_code=404, detail="Sandbox instance not found") from e

        info = await sbx.get_info(api_key=settings.E2B_API_KEY)
        if info.metadata.get("user_id") != self.user_id:
            raise HTTPException(status_code=404, detail="Sandbox instance not found")
        return sbx

    async def get_instance(self, instance_id: str) -> dict[str, Any]:
        sbx = await self._connect(instance_id)
        info = await sbx.get_info(api_key=settings.E2B_API_KEY)
        return _info_to_instance(info)

    async def create_instance(self, template_id: str, timeout_seconds: int) -> dict[str, Any]:
        try:
            sbx = await AsyncSandbox.create(
                template=template_id,
                timeout=timeout_seconds,
                metadata={"user_id": self.user_id},
                api_key=settings.E2B_API_KEY,
            )
        except SandboxException as e:
            raise SandboxCreationError(str(e)) from e

        return {
            "id": sbx.sandbox_id,
            "template_id": template_id,
            "status": "running",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=timeout_seconds),
        }

    async def delete_instance(self, instance_id: str) -> dict[str, Any]:
        sbx = await self._connect(instance_id)
        await sbx.kill()
        return {"id": instance_id, "status": "deleted"}

    async def get_instance_logs(self, instance_id: str) -> dict[str, Any]:
        """We don't (yet) stream E2B's own process logs; this returns our
        own execution audit trail for the instance instead, which is what
        actually persists past the sandbox's lifetime."""
        await self._connect(instance_id)  # 404s / ownership check
        response = (
            await self.db.table("sandbox_executions")
            .select("*")
            .eq("e2b_sandbox_id", instance_id)
            .eq("user_id", self.user_id)
            .order("started_at")
            .execute()
        )
        return {"executions": response.data or []}

    async def execute_command(
        self, instance_id: str, command: str, cwd: str | None, timeout: int
    ) -> dict[str, Any]:
        sbx = await self._connect(instance_id)

        insert_resp = (
            await self.db.table("sandbox_executions")
            .insert(
                {
                    "user_id": self.user_id,
                    "e2b_sandbox_id": instance_id,
                    "command": command,
                    "status": "running",
                }
            )
            .execute()
        )
        execution_id = insert_resp.data[0]["id"]

        try:
            result = await sbx.commands.run(command, cwd=cwd, timeout=timeout)
            exit_code, stdout, stderr = result.exit_code, result.stdout, result.stderr
        except SandboxException as exc:
            # CommandExitException carries stdout/stderr/exit_code for
            # commands that ran but returned non-zero; anything else is a
            # genuine sandbox-level failure.
            exit_code = getattr(exc, "exit_code", -1)
            stdout = getattr(exc, "stdout", "")
            stderr = getattr(exc, "stderr", str(exc))

        await self.db.table("sandbox_executions").update(
            {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", execution_id).execute()

        return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

    async def list_templates(self) -> list[dict[str, Any]]:
        return _KNOWN_TEMPLATES

    async def get_usage(self) -> list[dict[str, Any]]:
        usage = []
        try:
            infos = await _list_user_sandboxes(self.user_id)
            for info in infos:
                sbx = await AsyncSandbox.connect(info.sandbox_id, api_key=settings.E2B_API_KEY)
                sandbox_metrics = await sbx.get_metrics(api_key=settings.E2B_API_KEY)
                if sandbox_metrics:
                    latest = sandbox_metrics[-1]
                    usage.append(
                        {
                            "cpu_percent": latest.cpu_used_pct,
                            "memory_mb": latest.mem_used / (1024 * 1024),
                            "disk_mb": latest.disk_used / (1024 * 1024),
                        }
                    )
        except SandboxException:
            logger.exception("Failed to fetch sandbox usage metrics for user %s", self.user_id)
        return usage
