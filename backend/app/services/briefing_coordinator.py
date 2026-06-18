import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.raid_agent import RaidAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.risk_agent import RiskAgent
from app.agents.status_agent import StatusAgent
from app.services.project_context import ProjectContext
from app.services.rag import RAGService
from app.services.raid_service import RaidService

AGENT_LABELS = {
    "status": "Status Agent",
    "risk": "Risk Agent",
    "raid": "RAID Agent",
    "rag": "RAG Retrieval",
    "reporting": "Reporting Agent",
}


class BriefingCoordinator:
    """Runs the full PMO intelligence pipeline and records per-step latency."""

    async def run(
        self,
        ctx: ProjectContext,
        db: AsyncSession,
        *,
        template: str = "weekly",
    ) -> dict:
        steps: list[dict] = []

        status = await self._run_step(steps, "status", StatusAgent().analyze, ctx)
        risk = await self._run_step(steps, "risk", RiskAgent().analyze, ctx)
        raid_report = await self._run_step(steps, "raid", RaidAgent().analyze, ctx)
        await RaidService(db).save_report(raid_report)

        rag_hits = await self._run_step(
            steps,
            "rag",
            self._fetch_governance_context,
            ctx,
        )

        report = await self._run_step(
            steps,
            "reporting",
            ReportingAgent().generate,
            ctx,
            template,
            db,
            rag_hits=rag_hits,
            status=status,
            risk=risk,
            raid_report=raid_report,
            save_raid=False,
        )

        total_ms = sum(step["duration_ms"] for step in steps)

        return {
            "project_key": ctx.project.key,
            "project_name": ctx.project.name,
            "template": template,
            "generated_at": report["generated_at"],
            "status": status.model_dump(),
            "risk": risk.model_dump(),
            "raid": {
                "entry_count": len(raid_report.entries),
                "summary": raid_report.summary,
            },
            "report": report,
            "pipeline": {
                "total_duration_ms": total_ms,
                "steps": steps,
            },
            "headline": {
                "health": status.health.value,
                "risk_score": risk.risk_score.value,
                "raid_entries": len(raid_report.entries),
                "citations": len(report.get("citations", [])),
            },
        }

    @staticmethod
    async def _fetch_governance_context(ctx: ProjectContext) -> list[dict]:
        rag = RAGService()
        query = f"PMO governance risk escalation procedures for {ctx.project.name}"
        return await rag.search(query, limit=3, project_key=ctx.project.key)

    @staticmethod
    async def _run_step(steps: list[dict], agent: str, fn, *args, **kwargs):
        started = time.perf_counter()
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            steps.append(
                {
                    "agent": agent,
                    "label": AGENT_LABELS.get(agent, agent),
                    "duration_ms": duration_ms,
                    "status": "error",
                    "error": str(exc),
                }
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000)
        steps.append(
            {
                "agent": agent,
                "label": AGENT_LABELS.get(agent, agent),
                "duration_ms": duration_ms,
                "status": "ok",
            }
        )
        return result
