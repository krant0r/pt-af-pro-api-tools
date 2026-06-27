from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from .auth import TokenManager
from .config import config
from .web_routes import router

app = FastAPI(
    title="PTAF PRO Web API Tools",
    description="Experimental web UI / API for working with PTAF PRO configuration.",
    version="0.3.0",
)

# Подключение маршрутов
app.include_router(router)

# Глобальный менеджер токенов
token_manager = TokenManager()


@app.on_event("startup")
async def startup():
    config.reload_from_sources()
    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)
    logger.info("Application startup complete")