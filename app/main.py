from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.config import get_settings
from app.memory.db import create_db_and_tables
from app.scheduler.jobs import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)
app.include_router(chat_router, prefix="/chat", tags=["chat"])
