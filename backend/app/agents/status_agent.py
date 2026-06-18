from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.agents.schemas import (
    BlockedIssue,
    DelayedWorkItem,
    HealthLevel,
    ProjectStatusReport,
    SprintProgress,
)
from app.services.llm import LLMService
from app.services.project_context import (
    ProjectContext,
    active_sprints,
    blocked_issues,
    is_done,
    open_issues,
    overdue_issues,
)


class StatusLLMOutput(BaseModel):
    executive_summary: str
    recommendations: list[str] = Field(min_length=1, max_length=5)


STATUS_SYSTEM_PROMPT = """You are a PMO analyst generating executive project status summaries.
Use the provided Jira metrics to write concise, actionable insights for senior leadership.
Be direct, quantify impact where possible, and avoid jargon."""


class StatusAgent:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    async def analyze(self, ctx: ProjectContext) -> ProjectStatusReport:
        now = datetime.now(UTC)
        open_items = open_issues(ctx)
        overdue = overdue_issues(ctx, now)
        blocked = blocked_issues(ctx)
        completed = [i for i in ctx.issues if is_done(i.status)]

        sprint_progress = self._sprint_progress(ctx)
        health = self._compute_health(len(overdue), len(blocked), len(open_items))

        llm_output = await self._llm_enrich(ctx, health, overdue, blocked, open_items, completed)

        return ProjectStatusReport(
            project_key=ctx.project.key,
            project_name=ctx.project.name,
            health=health,
            executive_summary=llm_output.executive_summary,
            sprint_progress=sprint_progress,
            completed_stories=len(completed),
            at_risk_stories=len(overdue) + len(blocked),
            delayed_work=[
                DelayedWorkItem(
                    key=issue.key,
                    summary=issue.summary,
                    assignee=issue.assignee,
                    days_overdue=days,
                )
                for issue, days in overdue[:10]
            ],
            blocked_issues=[
                BlockedIssue(
                    key=issue.key,
                    summary=issue.summary,
                    assignee=issue.assignee,
                    status=issue.status,
                )
                for issue in blocked[:10]
            ],
            recommendations=llm_output.recommendations,
        )

    def _compute_health(self, overdue_count: int, blocked_count: int, open_count: int) -> HealthLevel:
        if overdue_count >= 5 or blocked_count >= 3:
            return HealthLevel.RED
        if overdue_count >= 2 or blocked_count >= 1 or (open_count > 0 and overdue_count / open_count > 0.2):
            return HealthLevel.AMBER
        return HealthLevel.GREEN

    def _sprint_progress(self, ctx: ProjectContext) -> list[SprintProgress]:
        progress: list[SprintProgress] = []
        for sprint in active_sprints(ctx) or ctx.sprints[:3]:
            sprint_issues = [i for i in ctx.issues if i.sprint_id == sprint.jira_id]
            if not sprint_issues:
                sprint_issues = ctx.issues[:20]
            done = [i for i in sprint_issues if is_done(i.status)]
            total = len(sprint_issues) or 1
            progress.append(
                SprintProgress(
                    sprint_name=sprint.name,
                    state=sprint.state,
                    completed_stories=len(done),
                    total_stories=len(sprint_issues),
                    completion_pct=round(len(done) / total * 100, 1),
                )
            )
        return progress

    async def _llm_enrich(
        self,
        ctx: ProjectContext,
        health: HealthLevel,
        overdue: list,
        blocked: list,
        open_items: list,
        completed: list,
    ) -> StatusLLMOutput:
        metrics = {
            "project": f"{ctx.project.key} — {ctx.project.name}",
            "health": health.value,
            "completed_stories": len(completed),
            "open_stories": len(open_items),
            "overdue_stories": len(overdue),
            "blocked_stories": len(blocked),
            "overdue_examples": [f"{i.key}: {i.summary} ({d}d overdue)" for i, d in overdue[:5]],
            "blocked_examples": [f"{i.key}: {i.summary}" for i in blocked[:5]],
        }

        if self.llm.is_configured:
            llm_result = await self.llm.try_structured_completion(
                system=STATUS_SYSTEM_PROMPT,
                user=f"Generate an executive status summary from these metrics:\n{metrics}",
                schema=StatusLLMOutput,
            )
            if llm_result is not None:
                return llm_result

        return StatusLLMOutput(
            executive_summary=(
                f"Project {ctx.project.name} is rated {health.value}. "
                f"{len(completed)} stories completed with {len(overdue)} overdue and {len(blocked)} blocked."
            ),
            recommendations=self._fallback_recommendations(health, overdue, blocked),
        )

    @staticmethod
    def _fallback_recommendations(health: HealthLevel, overdue: list, blocked: list) -> list[str]:
        recs: list[str] = []
        if overdue:
            recs.append(f"Prioritize {len(overdue)} overdue items — oldest is {overdue[0][1]} days late")
        if blocked:
            recs.append(f"Unblock {len(blocked)} issues via dependency review and escalation")
        if health == HealthLevel.AMBER:
            recs.append("Increase QA capacity by 20% to recover sprint commitments")
        if not recs:
            recs.append("Maintain current velocity and monitor sprint burndown")
        return recs
