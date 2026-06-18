from contextlib import asynccontextmanager

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.agents import router as agents_router
from app.api.dev import router as dev_router
from app.api.jira import router as jira_router
from app.api.raid import router as raid_router
from app.config import settings
from app.db.base import Base
from app.db.session import async_session, engine
from app.integrations.jira.sync import JiraSyncService
from app.logging_config import setup_logging
from app.models import raid as raid_models  # noqa: F401 — register tables

logger = structlog.get_logger(__name__)
scheduler = AsyncIOScheduler()


async def scheduled_jira_sync() -> None:
    async with async_session() as db:
        try:
            service = JiraSyncService(db)
            await service.sync_all()
        except Exception as exc:
            logger.error("scheduled_sync_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.jira_base_url and settings.jira_api_token:
        scheduler.add_job(
            scheduled_jira_sync,
            "interval",
            minutes=settings.jira_sync_interval_minutes,
            id="jira_sync",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("scheduler_started", interval_minutes=settings.jira_sync_interval_minutes)

    yield

    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="PMO Intelligence Platform",
    description="AI-powered PMO intelligence with Jira integration and multi-agent orchestration",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jira_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(raid_router, prefix="/api")
app.include_router(dev_router, prefix="/api")


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "jira_configured": bool(settings.jira_base_url and settings.jira_api_token),
    }
