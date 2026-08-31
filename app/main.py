from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import ApiKeyAuthMiddleware
from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.config import get_settings
from app.deploy.update import record_session_baseline
from app.memory.db import create_db_and_tables
from app.runtime.activity import activity
from app.runtime.boot_state import boot_store
from app.runtime.status_copy import BOOT_DETAIL, BOOT_SOURCE, BOOT_TITLE, choose_standby_greeting
from app.scheduler.jobs import register_jobs, scheduler
from app.voice.listener import start_voice_listener, stop_voice_listener
from app.voice.mode import get_voice_mode_enabled, init_voice_mode_from_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    record_session_baseline()
    boot_store.record_boot()
    register_jobs()
    scheduler.start()
    init_voice_mode_from_settings()
    if get_voice_mode_enabled():
        start_voice_listener()
    activity.log(
        title=BOOT_TITLE,
        detail=BOOT_DETAIL,
        source=BOOT_SOURCE,
    )
    activity.standby(
        title=choose_standby_greeting(),
        detail=None,
        source="system.idle",
    )
    yield
    stop_voice_listener()
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(ApiKeyAuthMiddleware)
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(api_router)
