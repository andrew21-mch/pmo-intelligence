from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JiraProject(Base):
    __tablename__ = "jira_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    project_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lead_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    epics: Mapped[list["JiraEpic"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    issues: Mapped[list["JiraIssue"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sprints: Mapped[list["JiraSprint"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class JiraEpic(Base):
    __tablename__ = "jira_epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("jira_projects.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["JiraProject"] = relationship(back_populates="epics")


class JiraIssue(Base):
    __tablename__ = "jira_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("jira_projects.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    issue_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    epic_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sprint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["JiraProject"] = relationship(back_populates="issues")


class JiraSprint(Base):
    __tablename__ = "jira_sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jira_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("jira_projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["JiraProject"] = relationship(back_populates="sprints")


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), default="jira")
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
