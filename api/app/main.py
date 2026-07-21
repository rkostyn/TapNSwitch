#!/usr/bin/env python3

from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
import re
import time
import os
import json
import uuid

_REQUEST_ID_RE = re.compile(r'^[a-zA-Z0-9\-]{1,64}$')
from app.logger import get_logger, request_id_var
from app.bootstrap.initial_admin import ensure_initial_admin
from app.db.mongo import MongoClient
from app.db.redis import RedisClient
from app.integrations.checkfront.client import CheckfrontApiClient

logger = get_logger(__name__)

# Routes
from app.routes.auth import router as auth_router
from app.routes.throw import router as throw_router
from app.routes.round import router as round_router
from app.routes.match import router as match_router
from app.routes.event import router as event_router
from app.routes.player import router as player_router
from app.routes.checkfront import router as checkfront_router
from app.routes.venue import router as venue_router

# Admin route
from app.routes.admin import router as admin_router, login_router as admin_login_router


async def _checkfront_sync_loop(mongo_client: MongoClient) -> None:
    interval = int(os.getenv("CHECKFRONT_SYNC_INTERVAL_SECONDS", "0") or "0")
    if interval <= 0:
        logger.info(
            "Checkfront background sync disabled (CHECKFRONT_SYNC_INTERVAL_SECONDS=%s)",
            interval,
        )
        return
    if CheckfrontApiClient.from_env() is None:
        logger.warning(
            "Checkfront background sync disabled: set CHECKFRONT_API_URL, "
            "CHECKFRONT_API_KEY, and CHECKFRONT_API_SECRET"
        )
        return

    from app.repositories.event_repository import EventRepository
    from app.services.checkfront_pull import pull_checkfront_bookings

    logger.info("Checkfront background sync enabled every %s seconds", interval)

    while True:
        try:
            await pull_checkfront_bookings(EventRepository(mongo_client))
        except Exception:
            logger.exception("Background Checkfront sync failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up")
    client = MongoClient()
    app.state.mongo_client = client
    redis = RedisClient()
    app.state.redis_client = redis
    indexes_path = os.path.join(os.path.dirname(__file__), "db", "indexes.json")
    with open(indexes_path) as f:
        indexes = json.load(f)
    for index in indexes:
        logger.info("Creating index on %s.%s", index["db"], index["collection"])
        await client.create_index(
            db_name=index["db"],
            collection_name=index["collection"],
            keys=index["keys"],
            unique=index.get("unique", False),
            expire_after_seconds=index.get("expireAfterSeconds")
        )
    await ensure_initial_admin(client)
    sync_task = asyncio.create_task(_checkfront_sync_loop(client))
    logger.info("Startup complete")
    yield
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down")
    await client.close()
    await redis.close()
    logger.info("Shutdown complete")


_is_production = os.getenv("ENV") == "production"

app = FastAPI(
    title=f"{os.getenv('APP_NAME')} {int(time.time())}",
    docs_url=None if _is_production else "/",
    redoc_url=None if _is_production else "/redoc",
    version="1",
    contact={
        "email": "contact@yeetbox.net",
    },
    license_info={
        "name": "GPLv3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
    },
    lifespan=lifespan,
    swagger_ui_parameters = {
        "syntaxHighlight": {
            "theme": "obsidian"
        }
    }
)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    raw_id = request.headers.get("X-Request-ID", "")
    request_id = raw_id if _REQUEST_ID_RE.match(raw_id) else str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/startup-check", include_in_schema=False)
async def startup_check():
    return {"message": "ok"}


@app.get("/healthz", include_in_schema=False)
async def healthz(request: Request):
    logger.debug("Health check requested")
    await request.app.state.mongo_client.ping()
    if not await request.app.state.redis_client.ping():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"message": "ok"}


app.include_router(auth_router)
app.include_router(throw_router)
app.include_router(round_router)
app.include_router(match_router)
app.include_router(event_router)
app.include_router(player_router)
app.include_router(checkfront_router)
app.include_router(venue_router)
app.include_router(admin_login_router)
app.include_router(admin_router)