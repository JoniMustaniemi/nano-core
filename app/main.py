from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.config import get_settings
from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.proactive.registry import register_builtin_delivery_handlers
from app.runtime.activity import activity
from app.runtime.status_copy import BOOT_DETAIL, BOOT_SOURCE, BOOT_TITLE, choose_standby_greeting
from app.scheduler.jobs import register_jobs, scheduler
from app.web.home import router as home_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    improvement_plans.restore_stale_implementing_plans()
    register_builtin_delivery_handlers()
    register_jobs()
    scheduler.start()
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
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "web" / "static"),
    name="static",
)
app.include_router(home_router)
app.include_router(api_router)
