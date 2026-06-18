"""Health checks for platform integrations."""

import asyncio
from datetime import UTC, datetime

import httpx
import structlog
from qdrant_client import QdrantClient
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.graphs.briefing_graph import AGENT_LABELS, briefing_graph

logger = structlog.get_logger(__name__)

EXPECTED_GRAPH_NODES = {"status_agent", "risk_agent", "raid_agent", "rag_agent", "report_agent"}


async def get_integrations_status() -> dict:
    checks = [
        await _check_postgres(),
        _check_langgraph(),
        await _check_ollama(),
        _check_qdrant(),
        await _check_jira(),
    ]

    statuses = {c["id"]: c["status"] for c in checks}
    if statuses.get("postgres") == "down":
        overall = "unhealthy"
    elif all(c["status"] in ("healthy", "not_configured") for c in checks):
        overall = "healthy"
    else:
        overall = "degraded"

    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "overall": overall,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "integrations": checks,
    }


async def _check_postgres() -> dict:
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return _item("postgres", "PostgreSQL", "healthy", "Database connected")
    except TimeoutError:
        return _item("postgres", "PostgreSQL", "degraded", "Connection pool busy — retry shortly")
    except Exception as exc:
        err = str(exc)
        if "QueuePool" in err or "connection timed out" in err.lower():
            return _item("postgres", "PostgreSQL", "degraded", "Connection pool busy — agents may be running")
        logger.warning("postgres_health_failed", error=err)
        return _item("postgres", "PostgreSQL", "down", err)


def _check_langgraph() -> dict:
    try:
        nodes = set(briefing_graph.get_graph().nodes.keys()) - {"__start__", "__end__"}
        missing = EXPECTED_GRAPH_NODES - nodes
        if missing:
            return _item(
                "langgraph",
                "LangGraph",
                "degraded",
                f"Missing nodes: {', '.join(sorted(missing))}",
                {"nodes": sorted(nodes), "pipeline": list(AGENT_LABELS.values())},
            )
        return _item(
            "langgraph",
            "LangGraph",
            "healthy",
            f"Briefing graph ready ({len(EXPECTED_GRAPH_NODES)} agents)",
            {
                "nodes": sorted(EXPECTED_GRAPH_NODES),
                "pipeline": " → ".join(AGENT_LABELS[k] for k in ("status", "risk", "raid", "rag", "reporting")),
            },
        )
    except Exception as exc:
        return _item("langgraph", "LangGraph", "down", str(exc))


async def _check_ollama() -> dict:
    if settings.llm_provider != "ollama":
        return _item(
            "ollama",
            "Ollama",
            "not_configured",
            f"Using {settings.llm_provider} instead",
            {"provider": settings.llm_provider, "model": settings.llm_model},
        )

    base = settings.ollama_base_url.replace("/v1", "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base}/api/tags")
        if response.status_code >= 400:
            return _item("ollama", "Ollama", "down", f"HTTP {response.status_code}")

        models = [m.get("name", "").split(":")[0] for m in response.json().get("models", [])]
        chat_model = settings.ollama_model.split(":")[0]
        embed_model = settings.ollama_embed_model.split(":")[0]
        has_chat = chat_model in models
        has_embed = embed_model in models

        if has_chat and has_embed:
            return _item(
                "ollama",
                "Ollama",
                "healthy",
                f"Models ready: {settings.ollama_model}, {settings.ollama_embed_model}",
                {"models_installed": models, "chat_model": settings.ollama_model, "embed_model": settings.ollama_embed_model},
            )
        missing = []
        if not has_chat:
            missing.append(settings.ollama_model)
        if not has_embed:
            missing.append(settings.ollama_embed_model)
        return _item(
            "ollama",
            "Ollama",
            "degraded",
            f"Connected — pull missing: {', '.join(missing)}",
            {
                "models_installed": models,
                "missing": missing,
                "pull_hint": f"docker exec portfolio_ollama_1 ollama pull {settings.ollama_model}",
            },
        )
    except Exception as exc:
        return _item("ollama", "Ollama", "down", f"Unreachable — agents use rule-based fallback ({exc})")


def _check_qdrant() -> dict:
    try:
        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        collections = [c.name for c in client.get_collections().collections]
        in_collection = settings.qdrant_collection in collections
        return _item(
            "qdrant",
            "Qdrant",
            "healthy",
            f"Vector DB connected · collection '{settings.qdrant_collection}' "
            + ("ready" if in_collection else "will be created on first upload"),
            {"collections": collections, "target_collection": settings.qdrant_collection},
        )
    except Exception as exc:
        return _item("qdrant", "Qdrant", "down", str(exc))


async def _check_jira() -> dict:
    configured = bool(settings.jira_base_url and settings.jira_api_token)
    if not configured:
        return _item(
            "jira",
            "Jira Cloud",
            "not_configured",
            "Add credentials to .env or use Load Demo Data",
            {"base_url": settings.jira_base_url or None},
        )

    try:
        from app.integrations.jira.client import JiraClient

        client = JiraClient()
        projects = await client.get_projects()
        return _item(
            "jira",
            "Jira Cloud",
            "healthy",
            f"Connected · {len(projects)} project(s) visible",
            {"base_url": settings.jira_base_url, "project_count": len(projects)},
        )
    except Exception as exc:
        return _item(
            "jira",
            "Jira Cloud",
            "degraded",
            f"Configured but auth failed — check token ({exc})",
            {"base_url": settings.jira_base_url},
        )


def _item(
    id_: str,
    name: str,
    status: str,
    message: str,
    details: dict | None = None,
) -> dict:
    return {
        "id": id_,
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }
