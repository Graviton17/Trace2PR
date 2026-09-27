"""WebSocket endpoints for live sandbox terminal output."""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from trace2pr.config.settings import settings
from trace2pr.db.supabase_client import get_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> dict | None:
    """WebSockets from browsers can't set an Authorization header, so the
    access token is passed as a query param instead (?token=...)."""
    if not token:
        return None
    try:
        admin_client = await get_admin_client()
        res = await admin_client.auth.get_user(token)
    except Exception:
        logger.debug("WebSocket token validation failed", exc_info=True)
        return None
    if not res.user:
        return None
    return {"id": res.user.id}


@router.websocket("/ws/sandbox/{sandbox_id}/terminal")
async def sandbox_terminal(websocket: WebSocket, sandbox_id: str, token: str | None = Query(None)):
    """Streams command execution output for a sandbox instance over a
    WebSocket. Protocol: client sends `{"command": "..."}` JSON messages;
    server streams back `{"stream": "stdout"|"stderr", "data": "..."}` as
    output arrives, then `{"event": "exit", "exit_code": N}` when the
    command completes."""
    await websocket.accept()

    user = await _authenticate_ws(websocket, token)
    if not user:
        await websocket.send_json({"event": "error", "message": "Unauthorized"})
        await websocket.close(code=4401)
        return

    try:
        from e2b.exceptions import SandboxException
        from e2b_code_interpreter import AsyncSandbox

        try:
            sbx = await AsyncSandbox.connect(sandbox_id, api_key=settings.E2B_API_KEY)
            info = await sbx.get_info(api_key=settings.E2B_API_KEY)
            if info.metadata.get("user_id") != user["id"]:
                await websocket.send_json({"event": "error", "message": "Sandbox not found"})
                await websocket.close(code=4404)
                return
        except SandboxException:
            await websocket.send_json({"event": "error", "message": "Sandbox not found"})
            await websocket.close(code=4404)
            return

        while True:
            message = await websocket.receive_json()
            command = message.get("command")
            if not command:
                continue

            async def on_stdout(data: str):
                await websocket.send_json({"stream": "stdout", "data": data})

            async def on_stderr(data: str):
                await websocket.send_json({"stream": "stderr", "data": data})

            try:
                result = await sbx.commands.run(
                    command, on_stdout=on_stdout, on_stderr=on_stderr, timeout=300
                )
                exit_code = result.exit_code
            except SandboxException as exc:
                exit_code = getattr(exc, "exit_code", -1)

            await websocket.send_json({"event": "exit", "exit_code": exit_code})

    except WebSocketDisconnect:
        logger.debug("Sandbox terminal WebSocket disconnected for sandbox %s", sandbox_id)
    except Exception:
        logger.exception("Error in sandbox terminal WebSocket for sandbox %s", sandbox_id)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011)
