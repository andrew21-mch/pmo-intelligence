# PMO Intelligence Platform

**AI-powered PMO dashboard** — Jira sync, multi-agent analysis, RAG governance citations, LangGraph orchestration, and executive reports with PDF export.

**Repository:** https://github.com/andrew21-mch/pmo-intelligence

<!-- Screenshot: add a dashboard image URL here when you have one -->
<!-- ![PMO Intelligence dashboard](https://your-image-url.png) -->

---

## What it does

| Capability | Description |
|------------|-------------|
| **Jira Integration** | Sync projects, issues, epics, sprints, and assignees from Jira Cloud |
| **Status Agent** | Executive health summary, sprint progress, overdue/blocked work |
| **Risk Agent** | Rule-based risk detection with optional LLM enrichment |
| **RAID Agent** | Auto-generates Risks, Assumptions, Issues, Dependencies |
| **Meeting Agent** | Transcript analysis → actions, decisions, risks; optional Jira tickets |
| **RAG Knowledge Base** | Upload governance docs; agents cite them in reports |
| **Reporting Agent** | Weekly / monthly / steering committee templates (HTML + PDF) |
| **PMO Briefing** | One-click pipeline orchestrating all agents with latency metrics |

---

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI |
| AI | Ollama (local) or OpenAI, **LangGraph** orchestration |
| Database | PostgreSQL |
| Vector DB | Qdrant |
| Frontend | React, Vite |
| Deployment | Docker, GitHub Actions |

---

## Quick start

```bash
git clone https://github.com/andrew21-mch/pmo-intelligence.git
cd pmo-intelligence
cp .env.example .env
docker-compose up --build -d
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

---

## Demo without Jira

1. Open the dashboard → **Load Demo Data**
2. Select project **DEMO** from the dropdown
3. **Knowledge Base** → **Load Sample Governance Doc**
4. **PMO Briefing** → **Generate PMO Briefing**
5. **Reports** → **Download PDF**

---

## Demo with Jira

- Add Atlassian credentials to `.env` (see below)
- Recreate the API container:

```bash
docker rm -f portfolio_api_1
docker-compose up -d api
```

- Click **Sync Jira** — all projects your account can see appear in the dropdown
- Select a project (e.g. **SCRUM**)
- **Projects** tab → upload CSV to bulk-create tasks (optional)
- **Generate PMO Briefing** for a full end-to-end run

---

## Architecture

```
React Dashboard
    │
    ▼
FastAPI ──► Jira Sync ──► PostgreSQL
    │
    ├── Status Agent ──┐
    ├── Risk Agent     │
    ├── RAID Agent     ├──► Ollama / OpenAI
    ├── Meeting Agent  │
    └── Reporting Agent┘
    │
    ├── RAG Service ──► Qdrant (embeddings)
    └── PDF Export
```

### PMO Briefing pipeline (LangGraph)

```
START → status_agent → risk_agent → raid_agent → rag_agent → report_agent → END
```

Each node records timing metrics. The coordinator invokes the compiled graph via `briefing_graph.ainvoke()`.

```python
# backend/app/graphs/briefing_graph.py (simplified)
graph.add_edge(START, "status_agent")
graph.add_edge("status_agent", "risk_agent")
graph.add_edge("risk_agent", "raid_agent")
graph.add_edge("raid_agent", "rag_agent")
graph.add_edge("rag_agent", "report_agent")
graph.add_edge("report_agent", END)
```

---

## Key API endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/jira/sync` | Sync all Jira projects |
| `POST /api/jira/import/csv` | Import tasks from CSV |
| `POST /api/agents/projects/{key}/briefing` | Full PMO briefing pipeline |
| `GET /api/agents/projects/{key}/status` | Status agent output |
| `GET /api/agents/projects/{key}/risk` | Risk agent output |
| `POST /api/agents/projects/{key}/raid/generate` | Generate RAID log |
| `POST /api/agents/projects/{key}/meetings/analyze` | Meeting intelligence |
| `POST /api/documents/upload` | Upload governance document |
| `POST /api/agents/projects/{key}/reports/generate` | Executive report |
| `POST /api/agents/reports/pdf` | Export report as PDF |
| `POST /api/dev/seed` | Load demo data (no Jira) |

---

## Configuration

### Jira (optional)

```env
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN="your-token-here"
```

Create a token at: https://id.atlassian.com/manage-profile/security/api-tokens

### LLM — Ollama (default, no OpenAI key required)

```bash
docker exec portfolio_ollama_1 ollama pull llama3.2
docker exec portfolio_ollama_1 ollama pull nomic-embed-text
```

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434/v1
OLLAMA_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Agents fall back to rule-based output if the LLM is unreachable.

---

## CSV task import

Required column: `summary`

Optional: `description`, `issue_type`, `priority`, `due_date`, `status`, `assignee`

```bash
curl -O http://localhost:8000/api/jira/import/csv/template
curl -X POST http://localhost:8000/api/jira/import/csv \
  -F "project_key=SCRUM" \
  -F "push_to_jira=true" \
  -F "file=@pmo-tasks-template.csv"
```

---

## Project structure

```
backend/
  app/agents/          # Status, Risk, RAID, Meeting, Reporting agents
  app/graphs/          # LangGraph StateGraph orchestration
  app/api/             # FastAPI route handlers
  app/integrations/    # Jira client + sync
  app/services/        # RAG, embeddings, briefing coordinator, PDF export
frontend/
  src/App.tsx          # Tabbed dashboard
docker-compose.yml     # Postgres, Qdrant, Ollama, API, frontend
```

---

## Highlights for reviewers

- **Multi-agent orchestration** with LangGraph, not a single monolithic prompt
- **Enterprise integration** with real Jira Cloud sync (all visible projects)
- **RAG citations** from uploaded governance documents in executive reports
- **Graceful LLM fallback** when Ollama/OpenAI is unavailable
- **Full Docker stack** — Postgres, Qdrant, Ollama, API, frontend in one command
- **Demo mode** works without any external credentials

---

## License

MIT
