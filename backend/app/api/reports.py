from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reporting_agent import ReportingAgent
from app.db.session import get_db
from app.services.pdf_export import html_to_pdf, safe_filename
from app.services.project_context import ProjectContextService

router = APIRouter(prefix="/agents", tags=["reports"])


class ReportRequest(BaseModel):
    template: str = "weekly"  # weekly | monthly | steering_committee


class PdfExportRequest(BaseModel):
    html: str
    title: str


class ExecutiveReport(BaseModel):
    template: str
    project_key: str
    project_name: str
    title: str
    generated_at: str
    markdown: str
    html: str
    health: str
    risk_score: str
    citations: list[dict]


@router.post("/projects/{project_key}/reports/generate", response_model=ExecutiveReport)
async def generate_report(
    project_key: str,
    body: ReportRequest,
    db: AsyncSession = Depends(get_db),
) -> ExecutiveReport:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agent = ReportingAgent()
    result = await agent.generate(ctx, body.template, db)
    return ExecutiveReport(**result)


@router.get("/projects/{project_key}/reports/preview", response_class=HTMLResponse)
async def preview_report(
    project_key: str,
    template: str = "weekly",
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agent = ReportingAgent()
    result = await agent.generate(ctx, template, db)
    return HTMLResponse(content=result["html"])


@router.post("/reports/pdf")
async def export_report_pdf(body: PdfExportRequest) -> Response:
    if not body.html.strip():
        raise HTTPException(status_code=400, detail="Report HTML is required")

    try:
        pdf_bytes = html_to_pdf(body.html)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{safe_filename(body.title)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
