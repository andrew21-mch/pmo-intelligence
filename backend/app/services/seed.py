"""Load demo Jira data for local development without a Jira connection."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jira import JiraEpic, JiraIssue, JiraProject, JiraSprint


async def seed_demo_data(db: AsyncSession) -> dict:
    existing = await db.scalar(select(JiraProject).limit(1))
    if existing:
        return {"status": "skipped", "message": "Data already exists"}

    now = datetime.now(UTC)
    project = JiraProject(
        jira_id="10001",
        key="DEMO",
        name="Customer Portal Modernization",
        project_type="software",
        lead_display_name="Alex PM",
    )
    db.add(project)
    await db.flush()

    epic = JiraEpic(
        jira_id="20001",
        project_id=project.id,
        key="DEMO-1",
        summary="Authentication & SSO",
        status="In Progress",
        assignee="Jordan Dev",
    )
    db.add(epic)

    sprint = JiraSprint(
        jira_id="30001",
        project_id=project.id,
        name="Sprint 24",
        state="active",
        start_date=now - timedelta(days=10),
        end_date=now - timedelta(days=2),
    )
    db.add(sprint)
    await db.flush()

    issues = [
        ("40001", "DEMO-10", "Implement OAuth2 login flow", "Story", "Done", "Jordan Dev", now - timedelta(days=5)),
        ("40002", "DEMO-11", "Add SSO provider integration", "Story", "Done", "Sam QA", now - timedelta(days=3)),
        ("40003", "DEMO-12", "Migrate user sessions", "Story", "In Progress", "Jordan Dev", now - timedelta(days=1)),
        ("40004", "DEMO-13", "Security penetration testing", "Story", "Blocked", "Sam QA", now - timedelta(days=14)),
        ("40005", "DEMO-14", "Update API documentation", "Task", "To Do", "Unassigned", now - timedelta(days=7)),
        ("40006", "DEMO-15", "Performance load testing", "Story", "In Progress", "Jordan Dev", now - timedelta(days=10)),
        ("40007", "DEMO-16", "Deploy to staging environment", "Story", "To Do", "Alex Ops", now - timedelta(days=2)),
        ("40008", "DEMO-17", "Fix login redirect bug", "Bug", "In Progress", "Jordan Dev", None),
        ("40009", "DEMO-18", "Configure CI/CD pipeline", "Task", "Done", "Alex Ops", None),
        ("40010", "DEMO-19", "User acceptance testing", "Story", "To Do", "Sam QA", now + timedelta(days=5)),
        ("40011", "DEMO-20", "Vendor API integration", "Story", "Blocked", None, now - timedelta(days=21)),
        ("40012", "DEMO-21", "Dashboard analytics widget", "Story", "In Progress", "Jordan Dev", None),
    ]

    for jira_id, key, summary, issue_type, status, assignee, due in issues:
        db.add(
            JiraIssue(
                jira_id=jira_id,
                project_id=project.id,
                key=key,
                summary=summary,
                issue_type=issue_type,
                status=status,
                assignee=assignee if assignee != "Unassigned" else None,
                priority="High" if "Blocked" in status or (due and due < now) else "Medium",
                epic_key="DEMO-1" if issue_type == "Story" and key != "DEMO-20" else None,
                sprint_id=sprint.jira_id,
                due_date=due,
            )
        )

    await db.commit()
    return {"status": "seeded", "project_key": "DEMO", "issues": len(issues)}
