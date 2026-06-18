from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jira import JiraEpic, JiraIssue, JiraProject, JiraSprint


@dataclass
class ProjectContext:
    project: JiraProject
    issues: list[JiraIssue] = field(default_factory=list)
    epics: list[JiraEpic] = field(default_factory=list)
    sprints: list[JiraSprint] = field(default_factory=list)


DONE_STATUSES = {"done", "closed", "resolved", "complete", "completed"}
BLOCKED_STATUSES = {"blocked", "on hold", "impediment"}


def is_done(status: str | None) -> bool:
    return (status or "").lower() in DONE_STATUSES


def is_blocked(status: str | None) -> bool:
    normalized = (status or "").lower()
    return any(token in normalized for token in BLOCKED_STATUSES)


class ProjectContextService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_key(self, project_key: str) -> ProjectContext | None:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(JiraProject)
            .where(JiraProject.key == project_key.upper())
            .options(
                selectinload(JiraProject.issues),
                selectinload(JiraProject.epics),
                selectinload(JiraProject.sprints),
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            return None

        return ProjectContext(
            project=project,
            issues=list(project.issues),
            epics=list(project.epics),
            sprints=list(project.sprints),
        )

    async def list_project_keys(self) -> list[str]:
        from sqlalchemy import select

        result = await self.db.execute(select(JiraProject.key))
        return list(result.scalars().all())


def open_issues(ctx: ProjectContext) -> list[JiraIssue]:
    return [issue for issue in ctx.issues if not is_done(issue.status)]


def overdue_issues(ctx: ProjectContext, now: datetime) -> list[tuple[JiraIssue, int]]:
    items: list[tuple[JiraIssue, int]] = []
    for issue in open_issues(ctx):
        if issue.due_date and issue.due_date.replace(tzinfo=None) < now.replace(tzinfo=None):
            days = (now.replace(tzinfo=None) - issue.due_date.replace(tzinfo=None)).days
            items.append((issue, days))
    return sorted(items, key=lambda x: x[1], reverse=True)


def blocked_issues(ctx: ProjectContext) -> list[JiraIssue]:
    return [issue for issue in open_issues(ctx) if is_blocked(issue.status)]


def assignee_workload(ctx: ProjectContext) -> dict[str, int]:
    workload: dict[str, int] = {}
    for issue in open_issues(ctx):
        name = issue.assignee or "Unassigned"
        workload[name] = workload.get(name, 0) + 1
    return workload


def active_sprints(ctx: ProjectContext) -> list[JiraSprint]:
    return [s for s in ctx.sprints if (s.state or "").lower() == "active"]
