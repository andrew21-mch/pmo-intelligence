import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


class PortfolioProjectRow(BaseModel):
    project_key: str
    project_name: str
    health: str
    risk_score: str
    executive_summary: str
    risk_reasoning: str
    blocked_count: int
    overdue_count: int
    signal_count: int
    top_actions: list[str]


class PortfolioHeadline(BaseModel):
    red: int
    amber: int
    green: int
    high_risk: int
    medium_risk: int
    low_risk: int


class PortfolioBriefingResponse(BaseModel):
    template: str
    generated_at: str
    project_count: int
    executive_summary: str
    headline: PortfolioHeadline
    projects: list[PortfolioProjectRow]
    at_risk_projects: list[PortfolioProjectRow]


def _sse_payload(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


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


@router.post("/projects/{project_key}/briefing/stream")
async def stream_briefing(
    project_key: str,
    body: BriefingRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    coordinator = BriefingCoordinator()

    async def event_generator():
        try:
            async for event in coordinator.run_stream(ctx, db, template=body.template):
                yield _sse_payload(event)
        except Exception as exc:
            yield _sse_payload({"event": "error", "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/portfolio/briefing", response_model=PortfolioBriefingResponse)
async def generate_portfolio_briefing(
    body: BriefingRequest,
    db: AsyncSession = Depends(get_db),
) -> PortfolioBriefingResponse:
    coordinator = BriefingCoordinator()
    result = await coordinator.run_portfolio(db, template=body.template)
    if result["project_count"] == 0:
        raise HTTPException(
            status_code=404,
            detail="No synced projects found. Sync Jira or load demo data first.",
        )
    return PortfolioBriefingResponse(**result)
