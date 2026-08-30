from fastapi import APIRouter

from app.api import (
    calendar,
    chat,
    health,
    location,
    memory,
    proactive,
    runtime,
    system,
    timers,
    tools,
    voice,
    weather,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(calendar.router)
api_router.include_router(chat.router)
api_router.include_router(health.router)
api_router.include_router(location.router)
api_router.include_router(memory.router)
api_router.include_router(runtime.router)
api_router.include_router(system.router)
api_router.include_router(timers.router)
api_router.include_router(proactive.router)
api_router.include_router(voice.router)
api_router.include_router(tools.router)
api_router.include_router(weather.router)
