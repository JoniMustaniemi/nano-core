from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.memory import router as memory_router
from app.api.runtime import router as runtime_router
from app.api.voice import router as voice_router
from app.config import get_settings
from app.memory.db import create_db_and_tables
from app.scheduler.jobs import register_jobs, scheduler
from app.web.home import router as home_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    register_jobs()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "web" / "static"),
    name="static",
)
app.include_router(home_router)
app.include_router(health_router)
app.include_router(memory_router)
app.include_router(runtime_router)
app.include_router(voice_router)
app.include_router(chat_router, prefix="/chat", tags=["chat"])
