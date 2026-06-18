from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.integrations.jira.client import JiraClient, JiraClientError
from app.services.jira_seed import seed_jira_issues
from app.services.seed import seed_demo_data

router = APIRouter(prefix="/dev", tags=["dev"])


class JiraSeedRequest(BaseModel):
    project_key: str


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)) -> dict:
    """Seed local demo data (no Jira needed)."""
    if settings.app_env == "production":
        return {"status": "forbidden", "message": "Seed disabled in production"}
    return await seed_demo_data(db)


@router.get("/jira/projects")
async def list_jira_projects() -> dict:
    """List Jira projects available for seeding."""
    try:
        client = JiraClient()
        projects = await client.get_projects()
        return {
            "projects": [{"key": p["key"], "name": p["name"]} for p in projects],
        }
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/seed-jira")
async def seed_jira(
    body: JiraSeedRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create sample issues in your real Jira project, then sync."""
    if settings.app_env == "production":
        return {"status": "forbidden", "message": "Seed disabled in production"}

    try:
        return await seed_jira_issues(db, body.project_key)
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
