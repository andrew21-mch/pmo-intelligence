# PMO Intelligence Platform — 5-Day Sprint Timeline

> Sequential implementation: each day builds on the previous.  
> Assumption: ~8–10 focused hours/day, API-token Jira auth (OAuth deferred), Markdown/HTML reports (PDF/PPT deferred).

---

## Day 1 — Foundation + Jira Integration (Phases 1–2)

| Block | Deliverable |
|-------|-------------|
| Morning | Repo structure, Docker Compose (Postgres, Qdrant, API), FastAPI app shell, config, logging |
| Midday | SQLAlchemy models, Alembic migrations, health endpoints |
| Afternoon | Jira client (projects, epics, tasks, sprints, assignees, statuses), sync service, scheduled job stub |
| Evening | React app shell, dashboard layout, Jira sync trigger UI, GitHub Actions CI |

**Exit criteria:** `docker compose up` runs all services; Jira sync stores data in Postgres; frontend shows sync status.

---

## Day 2 — Status Agent + Risk Detection Agent (Phases 3–4)

| Block | Deliverable |
|-------|-------------|
| Morning | OpenAI client, Pydantic structured output schemas, prompt templates |
| Midday | **Status Agent**: executive summary, sprint progress, delayed/blocked work |
| Afternoon | **Risk Agent**: rule engine (overdue, dependencies, bottlenecks, sprint slippage) + LLM reasoning layer |
| Evening | API endpoints + React panels for project health and risk score |

**Exit criteria:** Given synced Jira data, API returns structured status summary and risk assessment with recommendations.

---

## Day 3 — RAID Agent + Meeting Intelligence Agent (Phases 5–6)

| Block | Deliverable |
|-------|-------------|
| Morning | **RAID Agent**: auto-generate Risks, Assumptions, Issues, Dependencies with severity + mitigations |
| Midday | RAID persistence (DB), CRUD API, React RAID log view |
| Afternoon | **Meeting Agent**: transcript upload (Teams/Zoom plain text), extract summary, actions, decisions, risks |
| Evening | Optional Jira ticket creation from meeting action items |

**Exit criteria:** RAID log auto-populated from project data; meeting transcript produces structured output.

---

## Day 4 — RAG Knowledge System + Executive Reporting (Phases 7–8)

| Block | Deliverable |
|-------|-------------|
| Morning | Document upload API, chunking pipeline, OpenAI embeddings, Qdrant storage |
| Midday | RAG retrieval service with metadata filters + citation support |
| Afternoon | Wire RAG context into Status/Risk/RAID agents |
| Evening | **Reporting Agent**: weekly/monthly/steering committee templates; export as Markdown/HTML |

**Exit criteria:** Upload governance doc → agents cite it; generate full executive report from live data.

---

## Day 5 — Multi-Agent Orchestration + Observability + Portfolio Polish (Phases 9–10)

| Block | Deliverable |
|-------|-------------|
| Morning | **LangGraph coordinator**: route tasks, run agents in pipeline, merge outputs, conflict resolution |
| Midday | Observability: token usage, LLM cost tracking, agent latency, failure logging |
| Afternoon | Observability dashboard (React), agent performance metrics |
| Evening | Architecture diagram, README, deployment guide, demo script, case study outline |

**Exit criteria:** Single "Generate PMO Briefing" call runs all agents; dashboard shows costs/metrics; repo is portfolio-ready.

---

## Daily Dependency Chain

```
Day 1: Infrastructure + Data
         ↓
Day 2: Status + Risk (needs Jira data)
         ↓
Day 3: RAID + Meeting (needs risk/status context)
         ↓
Day 4: RAG + Reports (needs all agent outputs + docs)
         ↓
Day 5: Orchestration + Observability (needs all agents)
```

---

## Scope Cuts (if behind schedule)

| Cut | Saves | Impact |
|-----|-------|--------|
| Jira OAuth → API token only | ~4h | Low — document in README |
| PDF/PPT export → HTML/Markdown | ~6h | Low for portfolio |
| Meeting → Jira ticket creation | ~3h | Medium — show JSON output instead |
| Full observability UI → API metrics endpoint | ~4h | Low — JSON is enough for demo |
| GitHub Actions → lint + test only | ~1h | Minimal |

---

## Portfolio Deliverables (end of Day 5)

- [ ] GitHub repo with source, README, deployment guide
- [ ] Architecture diagram (Mermaid in README)
- [ ] Working demo: Jira sync → multi-agent briefing → executive report
- [ ] Case study outline (Problem → Architecture → Decisions → Challenges → Results)
