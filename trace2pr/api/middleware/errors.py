import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from trace2pr.config.settings import settings

logger = logging.getLogger(__name__)


class IncidentNotFoundError(Exception):
    pass


class IntegrationNotFoundError(Exception):
    pass


class SandboxCreationError(Exception):
    pass


class FixJobNotFoundError(Exception):
    pass


def _problem_response(status: int, title: str, detail: str, instance: str) -> JSONResponse:
    """Build an RFC-7807-style problem+json body."""
    return JSONResponse(
        status_code=status,
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        # Always log the full exception server-side so it's diagnosable.
        logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
        # Never leak internal exception details (stack traces, SQL, secrets)
        # to the client in production; only expose them in local development.
        detail = str(exc) if not settings.is_production else "An unexpected error occurred."
        return _problem_response(500, "Internal Server Error", detail, str(request.url))

    @app.exception_handler(IncidentNotFoundError)
    async def incident_not_found_handler(request: Request, exc: IncidentNotFoundError):
        return _problem_response(
            404, "Incident Not Found", str(exc) or "The requested incident was not found.", str(request.url)
        )

    @app.exception_handler(IntegrationNotFoundError)
    async def integration_not_found_handler(request: Request, exc: IntegrationNotFoundError):
        return _problem_response(
            404, "Integration Not Found", str(exc) or "The requested integration was not found.", str(request.url)
        )

    @app.exception_handler(SandboxCreationError)
    async def sandbox_creation_error_handler(request: Request, exc: SandboxCreationError):
        logger.error("Sandbox creation failed: %s", exc)
        return _problem_response(
            500,
            "Sandbox Creation Error",
            str(exc) or "An error occurred while creating the sandbox.",
            str(request.url),
        )

    @app.exception_handler(FixJobNotFoundError)
    async def fix_job_not_found_handler(request: Request, exc: FixJobNotFoundError):
        return _problem_response(
            404, "Fix Job Not Found", str(exc) or "The requested fix job was not found.", str(request.url)
        )
