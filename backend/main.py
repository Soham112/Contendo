import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

import logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())

from config import features, security
from config.startup import validate_environment

validate_environment()
from memory.feedback_store import init_db
from memory.hierarchy_store import init_db as init_hierarchy_db
from memory.retrieval_stats_store import flush_pending_retrievals, init_retrieval_stats_db
from memory.usage_store import set_main_loop
from memory.schema_check import verify_schema
from memory.source_store import start_sweeper
from starlette.concurrency import run_in_threadpool
from fastapi import Request
from fastapi.responses import JSONResponse
from publishing import worker as publish_worker
from routers import (
    account, admin, analytics, billing, feedback, generate, generate_stream, history, ideas, ingest, library, obsidian,
    profile, onboarding, publishing, stats,
)


logger = logging.getLogger(__name__)


def _log_security_mode() -> None:
    """Log which auth mode is active. security.current() raises on an unsafe
    combination (ALLOW_DEV_AUTH=1 with ENVIRONMENT=production), which aborts startup."""
    settings = security.current()
    environment = settings.environment or "(unset)"
    if settings.allow_dev_auth:
        logger.warning(
            "AUTH MODE: dev. ALLOW_DEV_AUTH=1, so requests without a valid token act as "
            "the local dev user. Never set this on a deployed server. ENVIRONMENT=%s",
            environment,
        )
    else:
        logger.info(
            "AUTH MODE: strict. Every request needs a valid Supabase token. ENVIRONMENT=%s",
            environment,
        )
    logger.info(
        "Admin user IDs configured: %d. Local-path Obsidian ingest: %s.",
        len(settings.admin_user_ids),
        "ENABLED (ALLOW_LOCAL_PATH_INGEST=1)" if settings.allow_local_path_ingest else "disabled",
    )


def _log_pipeline_variant() -> None:
    """Log which pipeline /generate runs. features.pipeline_variant() raises on
    an unknown PIPELINE_VARIANT, which aborts startup."""
    logger.info("PIPELINE VARIANT: %s (%s; default %s).", features.pipeline_variant(),
                features.PIPELINE_VARIANT_ENV, features.DEFAULT_PIPELINE_VARIANT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_security_mode()
    _log_pipeline_variant()
    await run_in_threadpool(verify_schema)
    init_db()
    init_hierarchy_db()
    init_retrieval_stats_db()
    # Agents running in run_in_threadpool workers schedule usage logs onto this loop.
    set_main_loop(asyncio.get_running_loop())
    # Sends due publish jobs. None when PUBLISHING_PROVIDER is unset; raises
    # (aborting startup) when it is set but misconfigured.
    publish_task = publish_worker.start()
    # Removes sources an ingest left 'pending' when the process died mid-write.
    sweeper_task = start_sweeper()
    yield
    sweeper_task.cancel()
    if publish_task is not None:
        publish_task.cancel()
    # Retrieval stats are written in the background; finish them before exit.
    await run_in_threadpool(flush_pending_retrievals)
    set_main_loop(None)


app = FastAPI(title="Contendo API", lifespan=lifespan)

# CORS: always allow localhost dev origins; add FRONTEND_ORIGIN in production.
# Vercel preview deployments are matched by regex (allow_origins does not glob).
_cors_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
]
_frontend_origin = os.environ.get("FRONTEND_ORIGIN", "").strip()
if _frontend_origin and _frontend_origin not in _cors_origins:
    _cors_origins.append(_frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from postgrest.exceptions import APIError as DatabaseAPIError


@app.exception_handler(DatabaseAPIError)
async def database_error(request: Request, exc: DatabaseAPIError):
    logger.error("Database request failed: %s %s", request.method, request.url.path,
                 exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=503, content={"detail": "We couldn't load your account data. Please try again shortly. If this continues, contact contendoai@gmail.com."})


app.include_router(onboarding.router)
app.include_router(account.router)
app.include_router(billing.router)
app.include_router(publishing.router)
app.include_router(ingest.router)
app.include_router(obsidian.router)
app.include_router(generate.router)
app.include_router(generate_stream.router)
app.include_router(history.router)
app.include_router(library.router)
app.include_router(ideas.router)
app.include_router(stats.router)
app.include_router(profile.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(analytics.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
