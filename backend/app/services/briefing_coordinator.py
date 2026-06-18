from sqlalchemy.ext.asyncio import AsyncSession

from app.graphs.briefing_graph import briefing_graph
from app.services.project_context import ProjectContext


class BriefingCoordinator:
    """Runs the PMO briefing pipeline via LangGraph."""

    async def run(
        self,
        ctx: ProjectContext,
        db: AsyncSession,
        *,
        template: str = "weekly",
    ) -> dict:
        final_state = await briefing_graph.ainvoke(
            {"template": template, "steps": []},
            config={"configurable": {"ctx": ctx, "db": db}},
        )

        status = final_state["status"]
        risk = final_state["risk"]
        raid_report = final_state["raid_report"]
        report = final_state["report"]
        steps = final_state.get("steps", [])
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
                "orchestrator": "langgraph",
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
