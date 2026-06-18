"""Parse task CSV files and import into Jira or the local database."""

import csv
import io
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.jira.client import JiraClient, JiraClientError
from app.integrations.jira.sync import JiraSyncService
from app.models.jira import JiraIssue, JiraProject

logger = structlog.get_logger(__name__)

MAX_ROWS = 100

COLUMN_ALIASES: dict[str, set[str]] = {
    "summary": {"summary", "title", "name", "task", "subject"},
    "description": {"description", "desc", "details", "body", "notes"},
    "issue_type": {"issue_type", "type", "issuetype", "issue type"},
    "priority": {"priority", "prio"},
    "due_date": {"due_date", "due", "deadline", "due date"},
    "status": {"status", "state"},
    "assignee": {"assignee", "owner", "assigned_to", "assigned to"},
}

SAMPLE_CSV = """summary,description,issue_type,priority,due_date,status,assignee
Implement OAuth2 login flow,Add OAuth2 provider support,Story,High,2026-07-01,To Do,Jordan Dev
Security penetration testing,Schedule vendor pen test,Story,High,2026-06-20,Blocked,Sam QA
Update API documentation,Refresh OpenAPI specs,Task,Medium,,To Do,
Vendor API integration,Waiting on procurement approval,Story,High,2026-06-15,Blocked,
"""


@dataclass
class TaskRow:
    summary: str
    description: str | None = None
    issue_type: str = "Task"
    priority: str | None = None
    due_date: str | None = None
    status: str | None = None
    assignee: str | None = None
    line_number: int = 0


def _normalize_header(name: str) -> str | None:
    key = name.strip().lower().replace("_", " ")
    for field, aliases in COLUMN_ALIASES.items():
        if key in aliases or key.replace(" ", "_") in aliases:
            return field
    return None


def parse_task_csv(content: str) -> tuple[list[TaskRow], list[str]]:
    """Parse CSV text into task rows. Returns (rows, parse_errors)."""
    if not content.strip():
        return [], ["CSV file is empty"]

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return [], ["CSV must include a header row"]

    mapping: dict[str, str] = {}
    for header in reader.fieldnames:
        normalized = _normalize_header(header)
        if normalized:
            mapping[normalized] = header

    if "summary" not in mapping:
        return [], ["CSV must include a 'summary' column (or alias: title, task, name)"]

    rows: list[TaskRow] = []
    errors: list[str] = []

    for line_number, raw in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            errors.append(f"Stopped at row {line_number}: maximum {MAX_ROWS} tasks per import")
            break

        summary = (raw.get(mapping["summary"]) or "").strip()
        if not summary:
            errors.append(f"Row {line_number}: summary is required")
            continue

        due = _clean_due_date(raw.get(mapping["due_date"]) if "due_date" in mapping else None)
        if due == "invalid":
            errors.append(f"Row {line_number}: invalid due_date (use YYYY-MM-DD)")
            continue

        rows.append(
            TaskRow(
                summary=summary,
                description=_optional(raw, mapping, "description"),
                issue_type=_optional(raw, mapping, "issue_type") or "Task",
                priority=_optional(raw, mapping, "priority"),
                due_date=due,
                status=_optional(raw, mapping, "status"),
                assignee=_optional(raw, mapping, "assignee"),
                line_number=line_number,
            )
        )

    return rows, errors


def _optional(raw: dict[str, str | None], mapping: dict[str, str], field: str) -> str | None:
    if field not in mapping:
        return None
    value = (raw.get(mapping[field]) or "").strip()
    return value or None


def _clean_due_date(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "invalid"


class CsvImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def import_tasks(
        self,
        *,
        project_key: str,
        content: str,
        push_to_jira: bool = True,
    ) -> dict:
        project_key = project_key.upper()
        rows, parse_errors = parse_task_csv(content)
        if not rows and parse_errors:
            return self._result(project_key, mode="none", parse_errors=parse_errors)

        use_jira = push_to_jira and self._jira_configured()
        if push_to_jira and not use_jira:
            return self._result(
                project_key,
                mode="none",
                parse_errors=parse_errors
                + ["Jira is not configured. Import locally or add Jira credentials to .env"],
            )

        if use_jira:
            return await self._import_to_jira(project_key, rows, parse_errors)
        return await self._import_local(project_key, rows, parse_errors)

    @staticmethod
    def _jira_configured() -> bool:
        try:
            JiraClient()
            return True
        except JiraClientError:
            return False

    async def _import_to_jira(
        self,
        project_key: str,
        rows: list[TaskRow],
        parse_errors: list[str],
    ) -> dict:
        client = JiraClient()
        projects = await client.get_projects()
        project_keys = [p["key"] for p in projects]
        if project_key not in project_keys:
            raise JiraClientError(
                f"Project '{project_key}' not found in Jira. Available: {', '.join(project_keys) or 'none'}"
            )

        issue_types = await client.get_issue_types(project_key)
        created_keys: list[str] = []
        errors = list(parse_errors)

        for row in rows:
            issue_type = _pick_issue_type(row.issue_type, issue_types)
            try:
                result = await client.create_issue(
                    project_key=project_key,
                    summary=row.summary[:255],
                    issue_type=issue_type,
                    due_date=row.due_date,
                    description=row.description,
                    priority=row.priority,
                )
                created_keys.append(result["key"])
            except JiraClientError as exc:
                errors.append(f"Row {row.line_number} ({row.summary[:40]}…): {exc}")
                logger.warning("csv_jira_row_failed", row=row.line_number, error=str(exc))

        synced_records = 0
        if created_keys:
            sync_log = await JiraSyncService(self.db).sync_all()
            synced_records = sync_log.records_synced

        return self._result(
            project_key,
            mode="jira",
            total_rows=len(rows),
            created=len(created_keys),
            failed=len(rows) - len(created_keys),
            issue_keys=created_keys,
            errors=errors,
            synced_records=synced_records,
            parse_errors=parse_errors,
        )

    async def _import_local(
        self,
        project_key: str,
        rows: list[TaskRow],
        parse_errors: list[str],
    ) -> dict:
        result = await self.db.execute(select(JiraProject).where(JiraProject.key == project_key))
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(
                f"Project '{project_key}' not found locally. Load demo data, sync Jira, or pick an existing project."
            )

        next_num = await self._next_issue_number(project)
        created_keys: list[str] = []
        now = datetime.now(UTC)

        for i, row in enumerate(rows):
            issue_num = next_num + i
            key = f"{project_key}-{issue_num}"
            jira_id = f"csv-{uuid.uuid4().hex[:10]}"
            due_dt = None
            if row.due_date:
                due_dt = datetime.strptime(row.due_date, "%Y-%m-%d").replace(tzinfo=UTC)

            self.db.add(
                JiraIssue(
                    jira_id=jira_id,
                    project_id=project.id,
                    key=key,
                    summary=row.summary[:512],
                    issue_type=row.issue_type,
                    status=row.status or "To Do",
                    assignee=row.assignee,
                    priority=row.priority or "Medium",
                    due_date=due_dt,
                    synced_at=now,
                )
            )
            created_keys.append(key)

        await self.db.commit()

        return self._result(
            project_key,
            mode="local",
            total_rows=len(rows),
            created=len(created_keys),
            failed=0,
            issue_keys=created_keys,
            errors=list(parse_errors),
            parse_errors=parse_errors,
        )

    async def _next_issue_number(self, project: JiraProject) -> int:
        result = await self.db.execute(select(JiraIssue.key).where(JiraIssue.project_id == project.id))
        max_num = 0
        pattern = re.compile(rf"^{re.escape(project.key)}-(\d+)$")
        for key in result.scalars():
            match = pattern.match(key)
            if match:
                max_num = max(max_num, int(match.group(1)))
        return max_num + 1

    @staticmethod
    def _result(
        *,
        project_key: str,
        mode: str,
        total_rows: int = 0,
        created: int = 0,
        failed: int = 0,
        issue_keys: list[str] | None = None,
        errors: list[str] | None = None,
        synced_records: int | None = None,
        parse_errors: list[str] | None = None,
    ) -> dict:
        return {
            "mode": mode,
            "project_key": project_key,
            "total_rows": total_rows,
            "created": created,
            "failed": failed,
            "issue_keys": issue_keys or [],
            "errors": (parse_errors or []) + (errors or []),
            "synced_records": synced_records,
        }


def _pick_issue_type(preferred: str, available: list[str]) -> str:
    if preferred in available:
        return preferred
    for fallback in ("Task", "Story", "Bug", "Sub-task"):
        if fallback in available:
            return fallback
    return available[0] if available else "Task"
