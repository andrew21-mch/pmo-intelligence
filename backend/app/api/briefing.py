from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.briefing_coordinator import BriefingCoordinator
from app.services.project_context import ProjectContextService

router = APIRouter(prefix="/agents", tags=["briefing"])


class BriefingRequest(BaseModel):
    template: str = "weekly"


class PipelineStep(BaseModel):
    agent: str
    label: str
    duration_ms: int
    status: str
    error: str | None = None


class BriefingHeadline(BaseModel):
    health: str
    risk_score: str
    raid_entries: int
    citations: int


class BriefingResponse(BaseModel):
    project_key: str
    project_name: str
    template: str
    generated_at: str
    status: dict
    risk: dict
    raid: dict
    report: dict
    pipeline: dict
    headline: BriefingHeadline


@router.post("/projects/{project_key}/briefing", response_model=BriefingResponse)
async def generate_briefing(
    project_key: str,
    body: BriefingRequest,
    db: AsyncSession = Depends(get_db),
) -> BriefingResponse:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    coordinator = BriefingCoordinator()
    result = await coordinator.run(ctx, db, template=body.template)
    return BriefingResponse(**result)
