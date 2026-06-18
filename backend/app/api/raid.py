from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.meeting_agent import MeetingAgent, SAMPLE_TRANSCRIPT
from app.agents.raid_agent import RaidAgent
from app.agents.schemas import MeetingIntelligenceReport, MeetingRecordStored, RaidEntryStored, RaidLogReport
from app.db.session import get_db
from app.services.project_context import ProjectContextService
from app.services.raid_service import MeetingService, RaidService

router = APIRouter(prefix="/agents", tags=["agents"])


class MeetingAnalyzeRequest(BaseModel):
    transcript: str = Field(default="", description="Meeting transcript text")
    title: str = "Meeting Analysis"
    create_jira_tickets: bool = False
    save: bool = True


@router.post("/projects/{project_key}/raid/generate", response_model=RaidLogReport)
async def generate_raid(project_key: str, db: AsyncSession = Depends(get_db)) -> RaidLogReport:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agent = RaidAgent()
    report = await agent.analyze(ctx)
    raid_service = RaidService(db)
    await raid_service.save_report(report)
    return report


@router.get("/projects/{project_key}/raid", response_model=list[RaidEntryStored])
async def list_raid(project_key: str, db: AsyncSession = Depends(get_db)) -> list[RaidEntryStored]:
    return await RaidService(db).list_entries(project_key)


@router.delete("/raid/{entry_id}")
async def delete_raid_entry(entry_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    deleted = await RaidService(db).delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="RAID entry not found")
    return {"status": "deleted", "id": entry_id}


@router.post("/projects/{project_key}/meetings/analyze", response_model=MeetingIntelligenceReport)
async def analyze_meeting(
    project_key: str,
    body: MeetingAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> MeetingIntelligenceReport:
    ctx_service = ProjectContextService(db)
    ctx = await ctx_service.get_by_key(project_key)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    transcript = body.transcript.strip() or SAMPLE_TRANSCRIPT
    agent = MeetingAgent()
    report = await agent.analyze(
        project_key=ctx.project.key,
        transcript=transcript,
        title=body.title,
        create_jira_tickets=body.create_jira_tickets,
    )

    if body.save:
        await MeetingService(db).save_report(report, transcript)

    return report


@router.get("/projects/{project_key}/meetings", response_model=list[MeetingRecordStored])
async def list_meetings(project_key: str, db: AsyncSession = Depends(get_db)) -> list[MeetingRecordStored]:
    return await MeetingService(db).list_records(project_key)


@router.get("/meetings/sample-transcript")
async def get_sample_transcript() -> dict:
    return {"transcript": SAMPLE_TRANSCRIPT}
