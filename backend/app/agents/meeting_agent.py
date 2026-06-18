import re

from pydantic import BaseModel, Field

from app.agents.schemas import (
    ActionItem,
    MeetingDecision,
    MeetingIntelligenceReport,
    MeetingRisk,
    RiskLevel,
)
from app.integrations.jira.client import JiraClient, JiraClientError
from app.services.llm import LLMService


class MeetingLLMOutput(BaseModel):
    summary: str
    action_items: list[ActionItem] = Field(default_factory=list)
    decisions: list[MeetingDecision] = Field(default_factory=list)
    risks_identified: list[MeetingRisk] = Field(default_factory=list)


MEETING_SYSTEM_PROMPT = """You are a PMO meeting analyst. Extract structured intelligence from meeting transcripts.
Identify action items (with assignee if mentioned), decisions made, and project risks discussed.
Be concise and specific. Use severity Low/Medium/High for risks."""


SAMPLE_TRANSCRIPT = """Sprint Review — Customer Portal Team
Date: June 18, 2026

Sarah (PM): Let's review sprint progress. OAuth login is done but security testing is blocked.

Jordan (Dev): The pen test vendor hasn't responded. That's blocking SCRUM-13.

Sarah: Decision — we will escalate to procurement today. Action: Jordan to follow up with vendor by Friday.

Sam (QA): UAT starts next week assuming security clears. Risk: if vendor delay continues, we miss the release window.

Sarah: Action: Sam to prepare UAT test cases while we wait. Mike to update the steering committee on Amber status.

Decision: Release date moved from June 30 to July 7 if security testing not complete by June 25.
"""


class MeetingAgent:
    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or LLMService()

    async def analyze(
        self,
        *,
        project_key: str,
        transcript: str,
        title: str = "Meeting Analysis",
        create_jira_tickets: bool = False,
    ) -> MeetingIntelligenceReport:
        text = transcript.strip()
        if not text:
            text = SAMPLE_TRANSCRIPT

        llm_result = await self.llm.try_structured_completion(
            system=MEETING_SYSTEM_PROMPT,
            user=f"Analyze this meeting transcript:\n\n{text}",
            schema=MeetingLLMOutput,
        )

        if llm_result is not None:
            report = MeetingIntelligenceReport(
                project_key=project_key,
                title=title,
                summary=llm_result.summary,
                action_items=llm_result.action_items,
                decisions=llm_result.decisions,
                risks_identified=llm_result.risks_identified,
            )
        else:
            report = self._fallback_parse(project_key, title, text)

        if create_jira_tickets and report.action_items:
            report.jira_tickets_created = await self._create_jira_tickets(project_key, report.action_items)

        return report

    def _fallback_parse(self, project_key: str, title: str, text: str) -> MeetingIntelligenceReport:
        action_items: list[ActionItem] = []
        decisions: list[MeetingDecision] = []
        risks: list[MeetingRisk] = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if re.search(r"\baction\s*:", lower) or lower.startswith("action -"):
                desc = re.sub(r"(?i)^.*?action\s*:\s*", "", stripped)
                assignee = self._extract_assignee(desc)
                action_items.append(ActionItem(description=desc, assignee=assignee))

            elif re.search(r"\bdecision\s*:", lower) or lower.startswith("decision -"):
                desc = re.sub(r"(?i)^.*?decision\s*:\s*", "", stripped)
                decisions.append(MeetingDecision(description=desc))

            elif re.search(r"\brisk\s*:", lower) or "risk:" in lower:
                desc = re.sub(r"(?i)^.*?risk\s*:\s*", "", stripped)
                severity = RiskLevel.HIGH if any(w in lower for w in ("critical", "miss", "delay")) else RiskLevel.MEDIUM
                risks.append(MeetingRisk(description=desc, severity=severity))

        if not action_items:
            action_items = [ActionItem(description="Follow up on blocked items discussed in meeting")]
        if not decisions:
            decisions = [MeetingDecision(description="Continue monitoring sprint progress")]
        if not risks:
            risks = [MeetingRisk(description="Vendor or dependency delays may impact schedule", severity=RiskLevel.MEDIUM)]

        summary = f"Meeting analyzed for {project_key}. Found {len(action_items)} actions, {len(decisions)} decisions, {len(risks)} risks."

        return MeetingIntelligenceReport(
            project_key=project_key,
            title=title,
            summary=summary,
            action_items=action_items,
            decisions=decisions,
            risks_identified=risks,
        )

    @staticmethod
    def _extract_assignee(text: str) -> str | None:
        match = re.match(r"^([A-Za-z]+)\s+to\s+", text)
        return match.group(1) if match else None

    async def _create_jira_tickets(self, project_key: str, action_items: list[ActionItem]) -> list[str]:
        created: list[str] = []
        try:
            client = JiraClient()
            issue_types = await client.get_issue_types(project_key)
            issue_type = "Task" if "Task" in issue_types else issue_types[0]

            for item in action_items[:5]:
                summary = item.description[:255]
                result = await client.create_issue(
                    project_key=project_key,
                    summary=f"[Meeting Action] {summary}",
                    issue_type=issue_type,
                )
                created.append(result["key"])
        except JiraClientError:
            pass
        return created
