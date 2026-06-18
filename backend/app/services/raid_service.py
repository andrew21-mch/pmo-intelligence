import json
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import (
    ActionItem,
    MeetingDecision,
    MeetingIntelligenceReport,
    MeetingRecordStored,
    MeetingRisk,
    RaidEntry,
    RaidEntryStored,
    RaidLogReport,
)
from app.models.raid import MeetingRecordModel, RaidEntryModel


class RaidService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_report(self, report: RaidLogReport, *, replace: bool = True) -> list[RaidEntryStored]:
        if replace:
            await self.db.execute(
                delete(RaidEntryModel).where(RaidEntryModel.project_key == report.project_key)
            )

        stored: list[RaidEntryStored] = []
        for entry in report.entries:
            row = RaidEntryModel(
                project_key=report.project_key,
                entry_type=entry.entry_type.value,
                title=entry.title,
                description=entry.description,
                severity=entry.severity.value,
                impact=entry.impact,
                mitigation=entry.mitigation,
                source=entry.source,
                jira_key=entry.jira_key,
            )
            self.db.add(row)
            await self.db.flush()
            stored.append(self._to_schema(row))

        await self.db.commit()
        return stored

    async def list_entries(self, project_key: str) -> list[RaidEntryStored]:
        result = await self.db.execute(
            select(RaidEntryModel)
            .where(RaidEntryModel.project_key == project_key.upper())
            .order_by(RaidEntryModel.created_at.desc())
        )
        return [self._to_schema(row) for row in result.scalars().all()]

    async def delete_entry(self, entry_id: int) -> bool:
        result = await self.db.execute(select(RaidEntryModel).where(RaidEntryModel.id == entry_id))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.commit()
        return True

    @staticmethod
    def _to_schema(row: RaidEntryModel) -> RaidEntryStored:
        from app.agents.schemas import RaidEntryType, RiskLevel

        return RaidEntryStored(
            id=row.id,
            project_key=row.project_key,
            entry_type=RaidEntryType(row.entry_type),
            title=row.title,
            description=row.description,
            severity=RiskLevel(row.severity),
            impact=row.impact,
            mitigation=row.mitigation,
            source=row.source,
            jira_key=row.jira_key,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )


class MeetingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_report(self, report: MeetingIntelligenceReport, transcript: str) -> MeetingRecordStored:
        row = MeetingRecordModel(
            project_key=report.project_key,
            title=report.title,
            transcript=transcript,
            summary=report.summary,
            action_items_json=json.dumps([a.model_dump() for a in report.action_items]),
            decisions_json=json.dumps([d.model_dump() for d in report.decisions]),
            risks_json=json.dumps([r.model_dump() for r in report.risks_identified]),
            jira_tickets_json=json.dumps(report.jira_tickets_created),
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return self._to_schema(row)

    async def list_records(self, project_key: str) -> list[MeetingRecordStored]:
        result = await self.db.execute(
            select(MeetingRecordModel)
            .where(MeetingRecordModel.project_key == project_key.upper())
            .order_by(MeetingRecordModel.created_at.desc())
            .limit(20)
        )
        return [self._to_schema(row) for row in result.scalars().all()]

    @staticmethod
    def _to_schema(row: MeetingRecordModel) -> MeetingRecordStored:
        def parse_actions(raw: str) -> list[ActionItem]:
            return [ActionItem(**item) for item in json.loads(raw or "[]")]

        def parse_decisions(raw: str) -> list[MeetingDecision]:
            return [MeetingDecision(**item) for item in json.loads(raw or "[]")]

        def parse_risks(raw: str) -> list[MeetingRisk]:
            return [MeetingRisk(**item) for item in json.loads(raw or "[]")]

        return MeetingRecordStored(
            id=row.id,
            project_key=row.project_key,
            title=row.title,
            summary=row.summary,
            action_items=parse_actions(row.action_items_json),
            decisions=parse_decisions(row.decisions_json),
            risks_identified=parse_risks(row.risks_json),
            jira_tickets_created=json.loads(row.jira_tickets_json or "[]"),
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
