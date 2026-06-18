from datetime import UTC, datetime

from app.agents.risk_agent import RiskAgent
from app.agents.schemas import RaidEntry, RaidEntryType, RaidLogReport, RiskLevel
from app.services.project_context import (
    ProjectContext,
    active_sprints,
    blocked_issues,
    open_issues,
    overdue_issues,
)


class RaidAgent:
    async def analyze(self, ctx: ProjectContext) -> RaidLogReport:
        now = datetime.now(UTC)
        entries: list[RaidEntry] = []

        overdue = overdue_issues(ctx, now)
        blocked = blocked_issues(ctx)
        open_items = open_issues(ctx)

        for issue, days in overdue[:5]:
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.RISK,
                    title=f"Overdue: {issue.key}",
                    description=issue.summary,
                    severity=RiskLevel.HIGH if days >= 7 else RiskLevel.MEDIUM,
                    impact=f"Schedule slip — {days} days overdue",
                    mitigation="Escalate to project lead and re-prioritize sprint scope",
                    jira_key=issue.key,
                )
            )

        for issue in blocked[:5]:
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.ISSUE,
                    title=f"Blocked: {issue.key}",
                    description=issue.summary,
                    severity=RiskLevel.HIGH,
                    impact="Work stoppage on critical path",
                    mitigation="Unblock dependency in next stand-up; assign owner for resolution",
                    jira_key=issue.key,
                )
            )
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.DEPENDENCY,
                    title=f"Dependency blocked: {issue.key}",
                    description=f"{issue.summary} — awaiting external resolution",
                    severity=RiskLevel.MEDIUM,
                    impact="Downstream tasks cannot proceed",
                    mitigation="Identify dependency owner and set escalation deadline",
                    jira_key=issue.key,
                )
            )

        for sprint in active_sprints(ctx):
            if sprint.end_date and sprint.end_date.replace(tzinfo=None) < now.replace(tzinfo=None):
                open_in_sprint = [i for i in ctx.issues if i.sprint_id == sprint.jira_id and i.status != "Done"]
                if open_in_sprint:
                    entries.append(
                        RaidEntry(
                            entry_type=RaidEntryType.RISK,
                            title=f"Sprint slippage: {sprint.name}",
                            description=f"{len(open_in_sprint)} items incomplete after sprint end",
                            severity=RiskLevel.HIGH,
                            impact="Sprint commitment not met; delivery date at risk",
                            mitigation="Re-baseline scope and communicate revised dates to stakeholders",
                        )
                    )

        unassigned = [i for i in open_items if not i.assignee]
        if len(unassigned) >= 2:
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.ASSUMPTION,
                    title="Unassigned work will be picked up this sprint",
                    description=f"{len(unassigned)} open items have no assignee",
                    severity=RiskLevel.LOW,
                    impact="If false, sprint velocity will drop",
                    mitigation="Assign owners in sprint planning; validate capacity assumptions",
                )
            )

        vendor_items = [i for i in ctx.issues if "vendor" in i.summary.lower() or "procurement" in i.summary.lower()]
        if vendor_items:
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.DEPENDENCY,
                    title="Vendor/procurement dependency",
                    description=vendor_items[0].summary,
                    severity=RiskLevel.HIGH,
                    impact="Schedule slip if vendor onboarding delayed",
                    mitigation="Escalate procurement approval; identify interim workaround",
                    jira_key=vendor_items[0].key,
                )
            )

        if len(open_items) > 0 and len(overdue) / len(open_items) < 0.1:
            entries.append(
                RaidEntry(
                    entry_type=RaidEntryType.ASSUMPTION,
                    title="Current team velocity is sustainable",
                    description="Overdue rate below 10% of open work",
                    severity=RiskLevel.LOW,
                    impact="Delivery forecast relies on maintaining current pace",
                    mitigation="Monitor burndown weekly; adjust if velocity drops",
                )
            )

        risk = await RiskAgent().analyze(ctx)
        summary = (
            f"RAID log for {ctx.project.name}: {len(entries)} entries "
            f"({sum(1 for e in entries if e.entry_type == RaidEntryType.RISK)} risks, "
            f"{sum(1 for e in entries if e.entry_type == RaidEntryType.ISSUE)} issues). "
            f"Overall project risk: {risk.risk_score.value}."
        )

        return RaidLogReport(
            project_key=ctx.project.key,
            project_name=ctx.project.name,
            entries=entries,
            summary=summary,
        )
