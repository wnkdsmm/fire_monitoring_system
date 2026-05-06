import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.api import router as api_router
from app.routes.pages import router as pages_router
from app.runtime_invalidation import warmup_runtime_caches
from config.db import check_connection, get_db_info
from config.paths import STATIC_DIR

logger = logging.getLogger(__name__)

if int(os.environ.get("WEB_CONCURRENCY", 1)) > 1:
    import warnings

    warnings.warn(
        "job_store is in-memory and not shared across workers. "
        "Set WEB_CONCURRENCY=1 or migrate to a shared backend.",
        RuntimeWarning,
        stacklevel=2,
    )


def create_app() -> FastAPI:
    application = FastAPI(title="Fire Data Pipeline")
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(api_router)
    application.include_router(pages_router)
    return application

app = create_app()

@app.on_event("startup")
async def startup_event() -> None:
    success, message = check_connection()
    if success:
        logger.info("[OK] %s (%s)", message, get_db_info())
        asyncio.create_task(
            asyncio.to_thread(warmup_runtime_caches, lambda w: logger.warning("[WARN] %s", w))
        )
    else:
        logger.error("[ERROR] %s", message)
        logger.error("  Проверьте настройки DATABASE_URL в файле .env")