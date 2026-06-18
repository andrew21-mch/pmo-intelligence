from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.agents.schemas import RiskAssessment, RiskLevel, RiskSignal
from app.services.llm import LLMService
from app.services.project_context import (
    ProjectContext,
    active_sprints,
    assignee_workload,
    blocked_issues,
    is_done,
    open_issues,
    overdue_issues,
)

BOTTLENECK_THRESHOLD = 8
SPRINT_SLIPPAGE_DAYS = 0


class RiskLLMOutput(BaseModel):
    reasoning: str
    recommended_actions: list[str] = Field(min_length=1, max_length=5)


RISK_SYSTEM_PROMPT = """You are a PMO risk analyst. Given rule-based risk signals from Jira data,
synthesize a concise risk narrative and actionable recommendations for the PMO.
Prioritize the highest-severity signals. Be specific and executive-ready."""


class RiskAgent:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    async def analyze(self, ctx: ProjectContext) -> RiskAssessment:
        now = datetime.now(UTC)
        signals = self._detect_signals(ctx, now)
        risk_score = self._score(signals)
        llm_output = await self._llm_enrich(ctx, signals, risk_score)

        return RiskAssessment(
            project_key=ctx.project.key,
            project_name=ctx.project.name,
            risk_score=risk_score,
            signals=signals,
            reasoning=llm_output.reasoning,
            recommended_actions=llm_output.recommended_actions,
        )

    def _detect_signals(self, ctx: ProjectContext, now: datetime) -> list[RiskSignal]:
        signals: list[RiskSignal] = []

        overdue = overdue_issues(ctx, now)
        if overdue:
            worst_days = overdue[0][1]
            severity = RiskLevel.HIGH if worst_days >= 7 else RiskLevel.MEDIUM
            signals.append(
                RiskSignal(
                    rule="overdue_tasks",
                    severity=severity,
                    description=f"{len(overdue)} tasks overdue (worst: {worst_days} days)",
                    affected_items=[issue.key for issue, _ in overdue[:5]],
                )
            )

        blocked = blocked_issues(ctx)
        if blocked:
            signals.append(
                RiskSignal(
                    rule="blocked_issues",
                    severity=RiskLevel.HIGH if len(blocked) >= 2 else RiskLevel.MEDIUM,
                    description=f"{len(blocked)} issues blocked awaiting resolution",
                    affected_items=[i.key for i in blocked[:5]],
                )
            )

        workload = assignee_workload(ctx)
        bottlenecks = {name: count for name, count in workload.items() if count >= BOTTLENECK_THRESHOLD}
        if bottlenecks:
            top = max(bottlenecks, key=bottlenecks.get)  # type: ignore[arg-type]
            signals.append(
                RiskSignal(
                    rule="resource_bottleneck",
                    severity=RiskLevel.MEDIUM,
                    description=f"Resource bottleneck: {top} has {bottlenecks[top]} open items",
                    affected_items=[top],
                )
            )

        unassigned = [i for i in open_issues(ctx) if not i.assignee]
        if len(unassigned) >= 3:
            signals.append(
                RiskSignal(
                    rule="unassigned_work",
                    severity=RiskLevel.LOW,
                    description=f"{len(unassigned)} open items have no assignee",
                    affected_items=[i.key for i in unassigned[:5]],
                )
            )

        for sprint in active_sprints(ctx):
            if sprint.end_date and sprint.end_date.replace(tzinfo=None) < now.replace(tzinfo=None):
                open_in_sprint = [
                    i for i in ctx.issues
                    if i.sprint_id == sprint.jira_id and not is_done(i.status)
                ]
                if open_in_sprint:
                    days_past = (now.replace(tzinfo=None) - sprint.end_date.replace(tzinfo=None)).days
                    signals.append(
                        RiskSignal(
                            rule="sprint_slippage",
                            severity=RiskLevel.HIGH if days_past >= 3 else RiskLevel.MEDIUM,
                            description=(
                                f"Sprint '{sprint.name}' ended {days_past} days ago "
                                f"with {len(open_in_sprint)} incomplete items"
                            ),
                            affected_items=[i.key for i in open_in_sprint[:5]],
                        )
                    )

        missing_deps = [i for i in blocked if i.epic_key is None and i.issue_type == "Story"]
        if missing_deps:
            signals.append(
                RiskSignal(
                    rule="missing_dependencies",
                    severity=RiskLevel.MEDIUM,
                    description=f"{len(missing_deps)} stories blocked without linked epic/dependency",
                    affected_items=[i.key for i in missing_deps[:5]],
                )
            )

        return signals

    @staticmethod
    def _score(signals: list[RiskSignal]) -> RiskLevel:
        if any(s.severity == RiskLevel.HIGH for s in signals):
            return RiskLevel.HIGH
        if any(s.severity == RiskLevel.MEDIUM for s in signals):
            return RiskLevel.MEDIUM
        if signals:
            return RiskLevel.LOW
        return RiskLevel.LOW

    async def _llm_enrich(
        self, ctx: ProjectContext, signals: list[RiskSignal], risk_score: RiskLevel
    ) -> RiskLLMOutput:
        signal_text = [
            f"[{s.severity.value}] {s.rule}: {s.description} — items: {', '.join(s.affected_items)}"
            for s in signals
        ] or ["No significant risk signals detected"]

        if self.llm.is_configured:
            llm_result = await self.llm.try_structured_completion(
                system=RISK_SYSTEM_PROMPT,
                user=(
                    f"Project: {ctx.project.key} — {ctx.project.name}\n"
                    f"Risk Score: {risk_score.value}\n"
                    f"Signals:\n" + "\n".join(signal_text)
                ),
                schema=RiskLLMOutput,
            )
            if llm_result is not None:
                return llm_result

        return RiskLLMOutput(
            reasoning=self._fallback_reasoning(signals, risk_score),
            recommended_actions=self._fallback_actions(signals, risk_score),
        )

    @staticmethod
    def _fallback_reasoning(signals: list[RiskSignal], risk_score: RiskLevel) -> str:
        if not signals:
            return "No significant risk signals detected from current Jira data."
        top = signals[0]
        return (
            f"Risk Score: {risk_score.value}. Primary concern: {top.description}. "
            f"{len(signals)} total signal(s) identified."
        )

    @staticmethod
    def _fallback_actions(signals: list[RiskSignal], risk_score: RiskLevel) -> list[str]:
        if not signals:
            return ["Continue monitoring sprint metrics and dependency tracking"]
        actions: list[str] = []
        rules = {s.rule for s in signals}
        if "overdue_tasks" in rules:
            actions.append("Escalate overdue critical-path items to project leadership")
        if "sprint_slippage" in rules:
            actions.append("Re-baseline sprint scope and communicate revised delivery dates")
        if "resource_bottleneck" in rules:
            actions.append("Rebalance workload or add capacity to bottlenecked assignees")
        if risk_score == RiskLevel.HIGH:
            actions.append("Escalate to PMO for steering committee review")
        return actions or ["Review open risks in next stand-up"]
