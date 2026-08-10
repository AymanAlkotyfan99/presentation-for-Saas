import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from sqlalchemy import text

from api.lifespan import app_lifespan
from api.middlewares import SessionAuthMiddleware, UserConfigEnvUpdateMiddleware
from api.operation_security import (
    OperationSecurityMiddleware,
    healthcheck_operation_controls,
)
from api.v1.async_tasks.router import API_V1_ASYNC_TASKS_ROUTER
from api.v1.auth.router import API_V1_AUTH_ROUTER
from api.v1.admin.router import API_V1_ADMIN_ROUTER
from api.v1.mock.router import API_V1_MOCK_ROUTER
from api.v1.ppt.router import API_V1_PPT_ROUTER
from api.v1.webhook.router import API_V1_WEBHOOK_ROUTER
from modules.workspaces.api import WORKSPACES_ROUTER
from utils.get_env import (
    get_app_data_directory_env,
    get_sentry_dsn_env,
    get_sentry_send_default_pii_env,
    get_sentry_traces_sample_rate_env,
)
from utils.mime_types import init_sandbox_safe_mimetypes
from utils.path_helpers import get_resource_path
from utils.sentry_config import (
    parse_sentry_sample_rate,
    parse_sentry_send_default_pii,
)
from services.database import async_session_maker
from utils.architecture_flags import (
    LegacyV1ReadDisabledError,
    LegacyV1WriteDisabledError,
)
from utils.api_errors import StableAPIError


init_sandbox_safe_mimetypes()


def _maybe_init_sentry() -> None:
    sentry_dsn = get_sentry_dsn_env()
    if not sentry_dsn:
        return

    try:
        import sentry_sdk
    except Exception:
        # Sentry SDK is optional in some runtime targets.
        return

    traces_sample_rate = get_sentry_traces_sample_rate_env()
    send_default_pii = get_sentry_send_default_pii_env()
    parsed_sample_rate = parse_sentry_sample_rate(traces_sample_rate)
    parsed_send_default_pii = parse_sentry_send_default_pii(send_default_pii)

    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=parsed_send_default_pii,
        traces_sample_rate=parsed_sample_rate,
    )


_maybe_init_sentry()

app = FastAPI(lifespan=app_lifespan)


@app.exception_handler(StableAPIError)
async def stable_api_error(_request: Request, exc: StableAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.response_body(),
        headers=exc.headers,
    )


@app.exception_handler(LegacyV1ReadDisabledError)
async def legacy_v1_read_disabled(_request: Request, exc: LegacyV1ReadDisabledError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(LegacyV1WriteDisabledError)
async def legacy_v1_write_disabled(_request: Request, exc: LegacyV1WriteDisabledError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

# Routers
app.include_router(API_V1_PPT_ROUTER)
app.include_router(API_V1_WEBHOOK_ROUTER)
app.include_router(API_V1_MOCK_ROUTER)
app.include_router(API_V1_AUTH_ROUTER)
app.include_router(API_V1_ADMIN_ROUTER)
app.include_router(API_V1_ASYNC_TASKS_ROUTER)
app.include_router(WORKSPACES_ROUTER)

# Mount app_data and static assets (direct FastAPI access; nginx also serves /static in Docker).
app_data_dir = get_app_data_directory_env()
if app_data_dir:
    os.makedirs(app_data_dir, exist_ok=True)
    app.mount("/app_data", StaticFiles(directory=app_data_dir), name="app_data")

static_dir = get_resource_path("static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Electron serves Next.js and FastAPI from separate loopback ports. When its
# runtime Next.js origin is available, use that exact origin so credentialed
# requests remain standards-compliant. Docker stays same-origin behind nginx;
# the wildcard fallback preserves standalone FastAPI development behavior.
next_public_origin = (os.getenv("NEXT_PUBLIC_URL") or "").strip().rstrip("/")
origins = [next_public_origin] if next_public_origin else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(UserConfigEnvUpdateMiddleware)
app.add_middleware(OperationSecurityMiddleware)
app.add_middleware(SessionAuthMiddleware)


@app.get("/api/v1/health/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/api/v1/health/ready", include_in_schema=False)
async def readiness():
    checks = {"database": False, "operation_controls": False}
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    checks["operation_controls"] = await healthcheck_operation_controls()
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.middleware("http")
async def static_icon_fallback_middleware(request: Request, call_next):
    """Serve placeholder when icon paths are missing (e.g. renamed Phosphor icons)."""
    response = await call_next(request)
    if response.status_code != 404:
        return response
    path = request.url.path
    if not path.startswith("/static/icons/"):
        return response
    placeholder = get_resource_path("static/icons/placeholder.svg")
    if not os.path.isfile(placeholder):
        return response
    return FileResponse(placeholder, media_type="image/svg+xml")
