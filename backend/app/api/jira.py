from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.jira.client import JiraClientError
from app.integrations.jira.sync import JiraSyncService
from app.models.jira import JiraEpic, JiraIssue, JiraProject, JiraSprint, SyncLog

router = APIRouter(prefix="/jira", tags=["jira"])


class SyncResponse(BaseModel):
    id: int
    status: str
    message: str | None
    records_synced: int


class ProjectSummary(BaseModel):
    key: str
    name: str
    issue_count: int
    epic_count: int
    sprint_count: int


class DashboardStats(BaseModel):
    projects: int
    issues: int
    epics: int
    sprints: int
    last_sync: SyncResponse | None


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(db: AsyncSession = Depends(get_db)) -> SyncResponse:
    service = JiraSyncService(db)
    try:
        log = await service.sync_all()
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SyncResponse(
        id=log.id,
        status=log.status,
        message=log.message,
        records_synced=log.records_synced,
    )


@router.get("/sync/logs", response_model=list[SyncResponse])
async def list_sync_logs(db: AsyncSession = Depends(get_db)) -> list[SyncResponse]:
    result = await db.execute(select(SyncLog).order_by(SyncLog.started_at.desc()).limit(20))
    logs = result.scalars().all()
    return [
        SyncResponse(id=log.id, status=log.status, message=log.message, records_synced=log.records_synced)
        for log in logs
    ]


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectSummary]:
    result = await db.execute(select(JiraProject))
    projects = result.scalars().all()
    summaries: list[ProjectSummary] = []

    for project in projects:
        issue_count = await db.scalar(
            select(func.count()).select_from(JiraIssue).where(JiraIssue.project_id == project.id)
        )
        epic_count = await db.scalar(
            select(func.count()).select_from(JiraEpic).where(JiraEpic.project_id == project.id)
        )
        sprint_count = await db.scalar(
            select(func.count()).select_from(JiraSprint).where(JiraSprint.project_id == project.id)
        )
        summaries.append(
            ProjectSummary(
                key=project.key,
                name=project.name,
                issue_count=issue_count or 0,
                epic_count=epic_count or 0,
                sprint_count=sprint_count or 0,
            )
        )

    return summaries


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    projects = await db.scalar(select(func.count()).select_from(JiraProject)) or 0
    issues = await db.scalar(select(func.count()).select_from(JiraIssue)) or 0
    epics = await db.scalar(select(func.count()).select_from(JiraEpic)) or 0
    sprints = await db.scalar(select(func.count()).select_from(JiraSprint)) or 0

    result = await db.execute(select(SyncLog).order_by(SyncLog.started_at.desc()).limit(1))
    last = result.scalar_one_or_none()
    last_sync = (
        SyncResponse(id=last.id, status=last.status, message=last.message, records_synced=last.records_synced)
        if last
        else None
    )

    return DashboardStats(
        projects=projects,
        issues=issues,
        epics=epics,
        sprints=sprints,
        last_sync=last_sync,
    )
