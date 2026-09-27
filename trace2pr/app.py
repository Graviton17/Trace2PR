import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from trace2pr.api.middleware.errors import register_error_handlers
from trace2pr.api.routes import (
    alerts,
    analysis,
    auth,
    events,
    fixer,
    health,
    incidents,
    integrations,
    knowledge,
    prs,
    sandbox,
    webhooks,
)
from trace2pr.api.routes import settings as settings_router
from trace2pr.config.logging_config import configure_logging
from trace2pr.config.settings import settings
from trace2pr.db.supabase_client import close_supabase, get_supabase

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_supabase()
    logger.info("Trace2PR API starting up (environment=%s)", settings.ENVIRONMENT)
    yield
    await close_supabase()
    logger.info("Trace2PR API shut down")


app = FastAPI(
    title="Trace2PR API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    """Attaches a request ID to every request/response and logs basic timing.
    This is the minimum viable observability layer for an API that will run
    behind a load balancer / APM in production."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%.1fms) [%s]",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


register_error_handlers(app)

# NOTE: each router already declares its own resource prefix (e.g. "/alerts",
# "/incidents"). We only add the shared "/api" prefix here — previously this
# was duplicated (e.g. "/api/alerts" + "/alerts" -> "/api/alerts/alerts"),
# which broke every endpoint in the API.
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(incidents.router, prefix="/api", tags=["incidents"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
app.include_router(sandbox.router, prefix="/api", tags=["sandbox"])
app.include_router(fixer.router, prefix="/api", tags=["fixer"])
app.include_router(prs.router, prefix="/api", tags=["prs"])
app.include_router(knowledge.router, prefix="/api", tags=["knowledge"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(integrations.router, prefix="/api", tags=["integrations"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
