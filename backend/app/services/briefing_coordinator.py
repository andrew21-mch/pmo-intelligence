"""PMO briefing orchestration — single project, portfolio rollup, and SSE streaming."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.risk_agent import RiskAgent
from app.agents.schemas import ProjectStatusReport, RaidLogReport, RiskAssessment
from app.agents.status_agent import StatusAgent
from app.graphs.briefing_graph import AGENT_LABELS, briefing_graph
from app.services.project_context import ProjectContext, ProjectContextService

EXPECTED_PIPELINE = [
    {"agent": key, "label": label} for key, label in AGENT_LABELS.items()
]

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
        return self._format_result(ctx, final_state, template)

    async def run_stream(
        self,
        ctx: ProjectContext,
        db: AsyncSession,
        *,
        template: str = "weekly",
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE-friendly events as each LangGraph node completes."""
        config = {"configurable": {"ctx": ctx, "db": db}}
        initial_state: dict[str, Any] = {"template": template, "steps": []}
        accumulated: dict[str, Any] = {"template": template, "steps": []}

        yield {"event": "pipeline_start", "steps": EXPECTED_PIPELINE}

        async for chunk in briefing_graph.astream(
            initial_state,
            config=config,
            stream_mode="updates",
        ):
            for node_name, update in chunk.items():
                accumulated = self._merge_state(accumulated, update)
                for step in update.get("steps", []):
                    yield {
                        "event": "step_complete",
                        "step": step,
                        "snapshot": self._snapshot_for_node(node_name, update),
                    }

        yield {"event": "done", "briefing": self._format_result(ctx, accumulated, template)}

    async def run_portfolio(
        self,
        db: AsyncSession,
        *,
        template: str = "weekly",
    ) -> dict:
        """Lightweight portfolio rollup — status + risk per synced project."""
        service = ProjectContextService(db)
        keys = await service.list_project_keys()
        status_agent = StatusAgent()
        risk_agent = RiskAgent()
        projects: list[dict[str, Any]] = []

        for key in keys:
            ctx = await service.get_by_key(key)
            if ctx is None:
                continue
            status = await status_agent.analyze(ctx)
            risk = await risk_agent.analyze(ctx)
            projects.append(self._portfolio_project_row(status, risk))

        projects.sort(key=self._portfolio_sort_key)
        headline = self._portfolio_headline(projects)

        return {
            "template": template,
            "generated_at": datetime.now(UTC).isoformat(),
            "project_count": len(projects),
            "executive_summary": self._build_portfolio_summary(projects, headline),
            "headline": headline,
            "projects": projects,
            "at_risk_projects": [
                p
                for p in projects
                if p["health"] in ("Red", "Amber") or p["risk_score"] == "High"
            ][:5],
        }

    def _format_result(
        self,
        ctx: ProjectContext,
        state: dict[str, Any],
        template: str,
    ) -> dict:
        status: ProjectStatusReport = state["status"]
        risk: RiskAssessment = state["risk"]
        raid_report: RaidLogReport = state["raid_report"]
        report: dict = state["report"]
        steps = state.get("steps", [])
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

    @staticmethod
    def _merge_state(accumulated: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(accumulated)
        for key, value in update.items():
            if key == "steps":
                merged["steps"] = merged.get("steps", []) + value
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _snapshot_for_node(node_name: str, update: dict[str, Any]) -> dict[str, Any] | None:
        if node_name == "status_agent" and "status" in update:
            status = update["status"]
            return {
                "health": status.health.value,
                "blocked": len(status.blocked_issues),
                "overdue": len(status.delayed_work),
                "summary": status.executive_summary[:240],
            }
        if node_name == "risk_agent" and "risk" in update:
            risk = update["risk"]
            return {
                "risk_score": risk.risk_score.value,
                "signals": len(risk.signals),
                "reasoning": risk.reasoning[:240],
            }
        if node_name == "raid_agent" and "raid_report" in update:
            raid = update["raid_report"]
            return {"entries": len(raid.entries), "summary": raid.summary[:200]}
        if node_name == "rag_agent" and "rag_hits" in update:
            hits = update["rag_hits"]
            return {
                "hits": len(hits),
                "sources": [h.get("title", "doc") for h in hits[:3]],
            }
        if node_name == "report_agent" and "report" in update:
            report = update["report"]
            return {
                "title": report.get("title"),
                "citations": len(report.get("citations", [])),
            }
        return None

    @staticmethod
    def _portfolio_project_row(status: ProjectStatusReport, risk: RiskAssessment) -> dict[str, Any]:
        return {
            "project_key": status.project_key,
            "project_name": status.project_name,
            "health": status.health.value,
            "risk_score": risk.risk_score.value,
            "executive_summary": status.executive_summary,
            "risk_reasoning": risk.reasoning,
            "blocked_count": len(status.blocked_issues),
            "overdue_count": len(status.delayed_work),
            "signal_count": len(risk.signals),
            "top_actions": (status.recommendations[:2] + risk.recommended_actions[:2])[:3],
        }

    @staticmethod
    def _portfolio_sort_key(project: dict[str, Any]) -> tuple[int, int, str]:
        risk_order = {"High": 0, "Medium": 1, "Low": 2}
        health_order = {"Red": 0, "Amber": 1, "Green": 2}
        return (
            risk_order.get(project["risk_score"], 9),
            health_order.get(project["health"], 9),
            project["project_key"],
        )

    @staticmethod
    def _portfolio_headline(projects: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "red": sum(1 for p in projects if p["health"] == "Red"),
            "amber": sum(1 for p in projects if p["health"] == "Amber"),
            "green": sum(1 for p in projects if p["health"] == "Green"),
            "high_risk": sum(1 for p in projects if p["risk_score"] == "High"),
            "medium_risk": sum(1 for p in projects if p["risk_score"] == "Medium"),
            "low_risk": sum(1 for p in projects if p["risk_score"] == "Low"),
        }

    @staticmethod
    def _build_portfolio_summary(
        projects: list[dict[str, Any]],
        headline: dict[str, int],
    ) -> str:
        if not projects:
            return "No synced projects found. Sync Jira or load demo data to run a portfolio briefing."

        parts = [
            f"Portfolio covers {len(projects)} project(s).",
            (
                f"Health: {headline['green']} Green, {headline['amber']} Amber, "
                f"{headline['red']} Red."
            ),
            (
                f"Risk: {headline['high_risk']} High, {headline['medium_risk']} Medium, "
                f"{headline['low_risk']} Low."
            ),
        ]

        at_risk = [
            p
            for p in projects
            if p["health"] in ("Red", "Amber") or p["risk_score"] == "High"
        ][:3]
        if at_risk:
            names = ", ".join(
                f"{p['project_key']} ({p['health']}/{p['risk_score']})" for p in at_risk
            )
            parts.append(f"Priority attention: {names}.")
        else:
            parts.append("No projects flagged for immediate escalation.")

        return " ".join(parts)
