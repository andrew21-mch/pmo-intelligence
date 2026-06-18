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
