from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.jira.client import JiraClient, JiraClientError
from app.models.jira import JiraEpic, JiraIssue, JiraProject, JiraSprint, SyncLog

logger = structlog.get_logger(__name__)


class JiraSyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def sync_all(self) -> SyncLog:
        log = SyncLog(source="jira", status="running")
        self.db.add(log)
        await self.db.flush()

        try:
            client = JiraClient()
            projects = await client.get_projects()
            total_records = 0

            for project_data in projects:
                count = await self._sync_project(client, project_data)
                total_records += count

            log.status = "success"
            log.records_synced = total_records
            log.message = f"Synced {len(projects)} projects, {total_records} records"
            log.completed_at = datetime.now(UTC)
            await self.db.commit()
            logger.info("jira_sync_complete", projects=len(projects), records=total_records)
            return log

        except JiraClientError as exc:
            log.status = "failed"
            log.message = str(exc)
            log.completed_at = datetime.now(UTC)
            await self.db.commit()
            logger.error("jira_sync_failed", error=str(exc))
            raise

    async def _sync_project(self, client: JiraClient, project_data: dict) -> int:
        jira_id = project_data["id"]
        key = project_data["key"]

        result = await self.db.execute(select(JiraProject).where(JiraProject.jira_id == jira_id))
        project = result.scalar_one_or_none()

        if project is None:
            project = JiraProject(jira_id=jira_id, key=key, name=project_data["name"])
            self.db.add(project)
        else:
            project.name = project_data["name"]
            project.key = key

        project.project_type = project_data.get("projectTypeKey")
        lead = project_data.get("lead") or {}
        project.lead_display_name = lead.get("displayName")
        project.synced_at = datetime.now(UTC)
        await self.db.flush()

        count = 1
        count += await self._sync_issues(client, project, key, issue_type="Epic", model=JiraEpic)
        count += await self._sync_issues(client, project, key, exclude_type="Epic", model=JiraIssue)
        count += await self._sync_sprints(client, project, key)
        return count

    async def _sync_issues(
        self,
        client: JiraClient,
        project: JiraProject,
        project_key: str,
        *,
        issue_type: str | None = None,
        exclude_type: str | None = None,
        model: type[JiraEpic | JiraIssue],
    ) -> int:
        jql = f'project = "{project_key}"'
        if issue_type:
            jql += f' AND issuetype = "{issue_type}"'
        elif exclude_type:
            jql += f' AND issuetype != "{exclude_type}"'

        issues = await client.search_issues(jql)
        count = 0

        for issue_data in issues:
            fields = issue_data.get("fields", {})
            jira_id = issue_data["id"]
            key = issue_data["key"]

            result = await self.db.execute(
                select(model).where(model.jira_id == jira_id)  # type: ignore[attr-defined]
            )
            record = result.scalar_one_or_none()

            if record is None:
                record = model(jira_id=jira_id, project_id=project.id, key=key)  # type: ignore[call-arg]
                self.db.add(record)

            record.summary = fields.get("summary", "")  # type: ignore[attr-defined]
            record.status = client.parse_status(fields)  # type: ignore[attr-defined]
            record.assignee = client.parse_assignee(fields)  # type: ignore[attr-defined]
            record.synced_at = datetime.now(UTC)  # type: ignore[attr-defined]

            if isinstance(record, JiraIssue):
                record.issue_type = client.parse_issue_type(fields)
                record.priority = client.parse_priority(fields)
                record.due_date = client.parse_due_date(fields)
                parent = fields.get("parent") or {}
                record.epic_key = parent.get("key")

            count += 1

        await self.db.flush()
        return count

    async def _sync_sprints(self, client: JiraClient, project: JiraProject, project_key: str) -> int:
        boards = await client.get_boards_for_project(project_key)
        count = 0

        for board in boards:
            sprints = await client.get_sprints(board["id"])
            for sprint_data in sprints:
                jira_id = str(sprint_data["id"])
                result = await self.db.execute(select(JiraSprint).where(JiraSprint.jira_id == jira_id))
                sprint = result.scalar_one_or_none()

                if sprint is None:
                    sprint = JiraSprint(jira_id=jira_id, project_id=project.id, name=sprint_data["name"])
                    self.db.add(sprint)
                else:
                    sprint.name = sprint_data["name"]

                sprint.state = sprint_data.get("state")
                start = sprint_data.get("startDate")
                end = sprint_data.get("endDate")
                sprint.start_date = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
                sprint.end_date = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
                sprint.synced_at = datetime.now(UTC)
                count += 1

        await self.db.flush()
        return count
