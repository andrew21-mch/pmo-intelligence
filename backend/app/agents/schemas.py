from enum import Enum

from pydantic import BaseModel, Field


class HealthLevel(str, Enum):
    GREEN = "Green"
    AMBER = "Amber"
    RED = "Red"


class SprintProgress(BaseModel):
    sprint_name: str
    state: str | None
    completed_stories: int
    total_stories: int
    completion_pct: float


class DelayedWorkItem(BaseModel):
    key: str
    summary: str
    assignee: str | None
    days_overdue: int


class BlockedIssue(BaseModel):
    key: str
    summary: str
    assignee: str | None
    status: str | None


class ProjectStatusReport(BaseModel):
    project_key: str
    project_name: str
    health: HealthLevel
    executive_summary: str
    sprint_progress: list[SprintProgress]
    completed_stories: int
    at_risk_stories: int
    delayed_work: list[DelayedWorkItem]
    blocked_issues: list[BlockedIssue]
    recommendations: list[str]


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class RiskSignal(BaseModel):
    rule: str
    severity: RiskLevel
    description: str
    affected_items: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    project_key: str
    project_name: str
    risk_score: RiskLevel
    signals: list[RiskSignal]
    reasoning: str
    recommended_actions: list[str]


class RaidEntryType(str, Enum):
    RISK = "Risk"
    ASSUMPTION = "Assumption"
    ISSUE = "Issue"
    DEPENDENCY = "Dependency"


class RaidEntry(BaseModel):
    entry_type: RaidEntryType
    title: str
    description: str
    severity: RiskLevel
    impact: str
    mitigation: str
    source: str = "agent"
    jira_key: str | None = None


class RaidLogReport(BaseModel):
    project_key: str
    project_name: str
    entries: list[RaidEntry]
    summary: str


class ActionItem(BaseModel):
    description: str
    assignee: str | None = None
    due_date: str | None = None


class MeetingDecision(BaseModel):
    description: str


class MeetingRisk(BaseModel):
    description: str
    severity: RiskLevel = RiskLevel.MEDIUM


class MeetingIntelligenceReport(BaseModel):
    project_key: str
    title: str
    summary: str
    action_items: list[ActionItem]
    decisions: list[MeetingDecision]
    risks_identified: list[MeetingRisk]
    jira_tickets_created: list[str] = Field(default_factory=list)


class RaidEntryStored(RaidEntry):
    id: int
    project_key: str
    created_at: str


class MeetingRecordStored(BaseModel):
    id: int
    project_key: str
    title: str
    summary: str
    action_items: list[ActionItem]
    decisions: list[MeetingDecision]
    risks_identified: list[MeetingRisk]
    jira_tickets_created: list[str]
    created_at: str
