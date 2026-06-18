from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.risk_agent import RiskAgent
from app.agents.schemas import ProjectStatusReport, RiskAssessment
from app.agents.status_agent import StatusAgent
from app.db.session import get_db
from app.services.project_context import ProjectContextService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/projects/{project_key}/status", response_model=ProjectStatusReport)
async def get_project_status(project_key: str, db: AsyncSession = Depends(get_db)) -> ProjectStatusReport:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agent = StatusAgent()
    return await agent.analyze(ctx)


@router.get("/projects/{project_key}/risk", response_model=RiskAssessment)
async def get_project_risk(project_key: str, db: AsyncSession = Depends(get_db)) -> RiskAssessment:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agent = RiskAgent()
    return await agent.analyze(ctx)


@router.get("/projects/{project_key}/analysis")
async def get_full_analysis(project_key: str, db: AsyncSession = Depends(get_db)) -> dict:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    status_agent = StatusAgent()
    risk_agent = RiskAgent()
    status = await status_agent.analyze(ctx)
    risk = await risk_agent.analyze(ctx)

    return {"status": status.model_dump(), "risk": risk.model_dump()}
