"""Create sample issues in real Jira via API, then sync locally."""

from datetime import UTC, datetime, timedelta

import structlog

from app.integrations.jira.client import JiraClient, JiraClientError
from app.integrations.jira.sync import JiraSyncService
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

SAMPLE_ISSUES = [
    {"summary": "Implement OAuth2 login flow", "type": "Story", "due_offset": -5},
    {"summary": "Add SSO provider integration", "type": "Story", "due_offset": -3},
    {"summary": "Migrate user sessions to new auth", "type": "Story", "due_offset": -1},
    {"summary": "Security penetration testing", "type": "Story", "due_offset": -14},
    {"summary": "Update API documentation", "type": "Task", "due_offset": -7},
    {"summary": "Performance load testing", "type": "Story", "due_offset": -10},
    {"summary": "Deploy to staging environment", "type": "Task", "due_offset": -2},
    {"summary": "Fix login redirect bug", "type": "Bug", "due_offset": None},
    {"summary": "Configure CI/CD pipeline", "type": "Task", "due_offset": None},
    {"summary": "User acceptance testing", "type": "Story", "due_offset": 5},
    {"summary": "Vendor API integration — waiting on procurement", "type": "Story", "due_offset": -21},
    {"summary": "Dashboard analytics widget", "type": "Story", "due_offset": None},
]


async def seed_jira_issues(db: AsyncSession, project_key: str) -> dict:
    client = JiraClient()
    now = datetime.now(UTC)

    projects = await client.get_projects()
    project_keys = [p["key"] for p in projects]
    if project_key.upper() not in project_keys:
        raise JiraClientError(
            f"Project '{project_key}' not found. Create it in Jira first. "
            f"Available projects: {', '.join(project_keys) or 'none'}"
        )

    issue_types = await client.get_issue_types(project_key.upper())
    created: list[str] = []
    errors: list[str] = []

    for item in SAMPLE_ISSUES:
        issue_type = _pick_type(item["type"], issue_types)
        due = None
        if item["due_offset"] is not None:
            due = (now + timedelta(days=item["due_offset"])).strftime("%Y-%m-%d")

        try:
            result = await client.create_issue(
                project_key=project_key.upper(),
                summary=item["summary"],
                issue_type=issue_type,
                due_date=due,
            )
            created.append(result["key"])
        except JiraClientError as exc:
            errors.append(f"{item['summary']}: {exc}")
            logger.warning("jira_seed_issue_failed", summary=item["summary"], error=str(exc))

    sync_service = JiraSyncService(db)
    sync_log = await sync_service.sync_all()

    return {
        "status": "seeded" if created else "failed",
        "project_key": project_key.upper(),
        "issues_created": len(created),
        "issue_keys": created,
        "synced_records": sync_log.records_synced,
        "errors": errors,
        "tip": "Move 2 issues to 'Blocked' status in Jira for better risk demo.",
    }


def _pick_type(preferred: str, available: list[str]) -> str:
    if preferred in available:
        return preferred
    for fallback in ("Task", "Story", "Bug", "Sub-task"):
        if fallback in available:
            return fallback
    return available[0] if available else "Task"
