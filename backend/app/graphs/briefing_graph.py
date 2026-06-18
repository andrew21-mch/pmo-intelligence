"""LangGraph orchestration for the PMO Briefing pipeline."""

import time
from typing import Annotated, Any, TypedDict

import operator
from langgraph.graph import END, START, StateGraph

from app.agents.raid_agent import RaidAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.risk_agent import RiskAgent
from app.agents.schemas import ProjectStatusReport, RaidLogReport, RiskAssessment
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


class BriefingState(TypedDict, total=False):
    template: str
    steps: Annotated[list[dict[str, Any]], operator.add]
    status: ProjectStatusReport
    risk: RiskAssessment
    raid_report: RaidLogReport
    rag_hits: list[dict]
    report: dict


def _configurable(config: dict) -> dict:
    return config.get("configurable", {})


def _record_step(agent: str, duration_ms: int, *, status: str = "ok", error: str | None = None) -> dict:
    step: dict[str, Any] = {
        "agent": agent,
        "label": AGENT_LABELS[agent],
        "duration_ms": duration_ms,
        "status": status,
    }
    if error:
        step["error"] = error
    return step


async def status_node(state: BriefingState, config: dict) -> dict:
    ctx: ProjectContext = _configurable(config)["ctx"]
    started = time.perf_counter()
    status = await StatusAgent().analyze(ctx)
    duration_ms = round((time.perf_counter() - started) * 1000)
    return {"status": status, "steps": [_record_step("status", duration_ms)]}


async def risk_node(state: BriefingState, config: dict) -> dict:
    ctx: ProjectContext = _configurable(config)["ctx"]
    started = time.perf_counter()
    risk = await RiskAgent().analyze(ctx)
    duration_ms = round((time.perf_counter() - started) * 1000)
    return {"risk": risk, "steps": [_record_step("risk", duration_ms)]}


async def raid_node(state: BriefingState, config: dict) -> dict:
    ctx: ProjectContext = _configurable(config)["ctx"]
    db = _configurable(config)["db"]
    started = time.perf_counter()
    raid_report = await RaidAgent().analyze(ctx)
    await RaidService(db).save_report(raid_report)
    duration_ms = round((time.perf_counter() - started) * 1000)
    return {"raid_report": raid_report, "steps": [_record_step("raid", duration_ms)]}


async def rag_node(state: BriefingState, config: dict) -> dict:
    ctx: ProjectContext = _configurable(config)["ctx"]
    started = time.perf_counter()
    rag = RAGService()
    query = f"PMO governance risk escalation procedures for {ctx.project.name}"
    rag_hits = await rag.search(query, limit=3, project_key=ctx.project.key)
    duration_ms = round((time.perf_counter() - started) * 1000)
    return {"rag_hits": rag_hits, "steps": [_record_step("rag", duration_ms)]}


async def reporting_node(state: BriefingState, config: dict) -> dict:
    ctx: ProjectContext = _configurable(config)["ctx"]
    db = _configurable(config)["db"]
    started = time.perf_counter()
    report = await ReportingAgent().generate(
        ctx,
        state["template"],
        db,
        rag_hits=state.get("rag_hits"),
        status=state.get("status"),
        risk=state.get("risk"),
        raid_report=state.get("raid_report"),
        save_raid=False,
    )
    duration_ms = round((time.perf_counter() - started) * 1000)
    return {"report": report, "steps": [_record_step("reporting", duration_ms)]}


def build_briefing_graph():
    """Compile the LangGraph pipeline: status → risk → raid → rag → reporting."""
    graph = StateGraph(BriefingState)

    graph.add_node("status_agent", status_node)
    graph.add_node("risk_agent", risk_node)
    graph.add_node("raid_agent", raid_node)
    graph.add_node("rag_agent", rag_node)
    graph.add_node("report_agent", reporting_node)

    graph.add_edge(START, "status_agent")
    graph.add_edge("status_agent", "risk_agent")
    graph.add_edge("risk_agent", "raid_agent")
    graph.add_edge("raid_agent", "rag_agent")
    graph.add_edge("rag_agent", "report_agent")
    graph.add_edge("report_agent", END)

    return graph.compile()


briefing_graph = build_briefing_graph()
