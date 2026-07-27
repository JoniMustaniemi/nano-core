from fastapi import APIRouter

from app.api import (
    calendar,
    chat,
    health,
    improvement_plans,
    memory,
    proactive,
    runtime,
    tools,
    voice,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(calendar.router)
api_router.include_router(chat.router)
api_router.include_router(health.router)
api_router.include_router(memory.router)
api_router.include_router(improvement_plans.router)
api_router.include_router(runtime.router)
api_router.include_router(proactive.router)
api_router.include_router(voice.router)
api_router.include_router(tools.router)
