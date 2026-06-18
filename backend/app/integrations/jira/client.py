from datetime import datetime
from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class JiraClientError(Exception):
    pass


class JiraClient:
    """Jira REST API client using API token authentication."""

    def __init__(self) -> None:
        if not all([settings.jira_base_url, settings.jira_email, settings.jira_api_token]):
            raise JiraClientError("Jira credentials not configured")

        self.base_url = settings.jira_base_url.rstrip("/")
        self.auth = (settings.jira_email, settings.jira_api_token)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, auth=self.auth, headers=self.headers, **kwargs)
            if response.status_code >= 400:
                logger.error("jira_api_error", status=response.status_code, body=response.text, path=path)
                raise JiraClientError(f"Jira API error {response.status_code}: {response.text}")
            if response.status_code == 204:
                return None
            return response.json()

    async def get_projects(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/rest/api/3/project/search")
        return data.get("values", [])

    async def search_issues(self, jql: str, fields: list[str] | None = None, max_results: int = 100) -> list[dict]:
        all_issues: list[dict] = []
        next_page_token: str | None = None
        field_list = fields or [
            "summary", "status", "assignee", "issuetype",
            "priority", "duedate", "parent", "customfield_10014",
        ]

        while len(all_issues) < max_results:
            payload: dict[str, Any] = {
                "jql": jql,
                "maxResults": min(max_results - len(all_issues), 100),
                "fields": field_list,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            data = await self._request("POST", "/rest/api/3/search/jql", json=payload)
            issues = data.get("issues", [])
            all_issues.extend(issues)

            next_page_token = data.get("nextPageToken")
            if not issues or not next_page_token:
                break

        return all_issues[:max_results]

    async def get_boards_for_project(self, project_key: str) -> list[dict]:
        data = await self._request("GET", f"/rest/agile/1.0/board?projectKeyOrId={project_key}")
        return data.get("values", [])

    async def get_sprints(self, board_id: int) -> list[dict]:
        data = await self._request("GET", f"/rest/agile/1.0/board/{board_id}/sprint")
        return data.get("values", [])

    async def get_issue_types(self, project_key: str) -> list[str]:
        data = await self._request(
            "GET",
            f"/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes",
        )
        projects = data.get("projects", [])
        if not projects:
            return ["Task"]
        return [t["name"] for t in projects[0].get("issuetypes", [])]

    async def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        due_date: str | None = None,
    ) -> dict:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if due_date:
            fields["duedate"] = due_date

        return await self._request("POST", "/rest/api/3/issue", json={"fields": fields})

    async def list_project_keys(self) -> list[str]:
        projects = await self.get_projects()
        return [p["key"] for p in projects]

    @staticmethod
    def parse_assignee(fields: dict) -> str | None:
        assignee = fields.get("assignee")
        return assignee.get("displayName") if assignee else None

    @staticmethod
    def parse_due_date(fields: dict) -> datetime | None:
        due = fields.get("duedate")
        if not due:
            return None
        return datetime.fromisoformat(due)

    @staticmethod
    def parse_status(fields: dict) -> str | None:
        status = fields.get("status")
        return status.get("name") if status else None

    @staticmethod
    def parse_issue_type(fields: dict) -> str | None:
        issue_type = fields.get("issuetype")
        return issue_type.get("name") if issue_type else None

    @staticmethod
    def parse_priority(fields: dict) -> str | None:
        priority = fields.get("priority")
        return priority.get("name") if priority else None
