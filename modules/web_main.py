from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from loguru import logger

from .auth import TokenManager
from .config import config
from .snapshots import export_all_tenant_snapshots

app = FastAPI(
    title="PTAF PRO Web API Tools",
    description=(
        "Experimental web UI / API for working with PTAF PRO configuration.\n"
        "Stage 1: initialization – export full snapshots for all tenants."
    ),
    version="0.1.0",
)


@app.on_event("startup")
async def _startup() -> None:
    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)
    logger.info("Application startup complete")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/init/snapshots")
async def init_snapshots():
    """
    Optional HTTP trigger for stage 1 snapshot export.
    In production you will typically run stage 1 via a separate command,
    but this endpoint is handy for debugging.
    """
    tm = TokenManager()
    paths = await export_all_tenant_snapshots(tm)
    return JSONResponse(
        {
            "snapshots_written": len(paths),
            "files": [str(p) for p in paths],
        }
    )


@app.get("/")
async def index():
    return {
        "message": "PTAF PRO web tools – backend is running.",
        "docs": "/docs",
    }
