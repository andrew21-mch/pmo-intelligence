import { useCallback, useEffect, useState } from "react";
import {
  analyzeMeeting,
  checkHealth,
  DashboardStats,
  generateRaid,
  getProjectRisk,
  getProjects,
  getProjectStatus,
  getRaidEntries,
  getSampleTranscript,
  getStats,
  MeetingReport,
  ProjectSummary,
  ProjectStatusReport,
  RaidEntry,
  RiskAssessment,
  seedDemoData,
  seedJiraProject,
  listJiraProjectsForSeed,
  triggerSync,
} from "./api";

function healthClass(health: string) {
  if (health === "Green") return "health-green";
  if (health === "Amber") return "health-amber";
  return "health-red";
}

function riskClass(risk: string) {
  if (risk === "Low") return "risk-low";
  if (risk === "Medium") return "risk-medium";
  return "risk-high";
}

function raidTypeClass(type: string) {
  if (type === "Risk") return "raid-risk";
  if (type === "Issue") return "raid-issue";
  if (type === "Dependency") return "raid-dependency";
  return "raid-assumption";
}

export default function App() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [status, setStatus] = useState<ProjectStatusReport | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [raidEntries, setRaidEntries] = useState<RaidEntry[]>([]);
  const [meetingReport, setMeetingReport] = useState<MeetingReport | null>(null);
  const [transcript, setTranscript] = useState("");
  const [createJiraTickets, setCreateJiraTickets] = useState(false);
  const [health, setHealth] = useState<string>("checking");
  const [syncing, setSyncing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [raidLoading, setRaidLoading] = useState(false);
  const [meetingLoading, setMeetingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [healthRes, statsRes, projectsRes] = await Promise.all([
        checkHealth(),
        getStats(),
        getProjects(),
      ]);
      setHealth(healthRes.status);
      setStats(statsRes);
      setProjects(projectsRes);
      setError(null);
      if (projectsRes.length > 0 && !selectedProject) {
        setSelectedProject(projectsRes[0].key);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    }
  }, [selectedProject]);

  const loadRaid = useCallback(async (projectKey: string) => {
    if (!projectKey) return;
    try {
      const entries = await getRaidEntries(projectKey);
      setRaidEntries(entries);
    } catch {
      setRaidEntries([]);
    }
  }, []);

  const loadAnalysis = useCallback(async (projectKey: string) => {
    if (!projectKey) return;
    setAnalyzing(true);
    try {
      const [statusRes, riskRes] = await Promise.all([
        getProjectStatus(projectKey),
        getProjectRisk(projectKey),
      ]);
      setStatus(statusRes);
      setRisk(riskRes);
      setError(null);
      await loadRaid(projectKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, [loadRaid]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedProject) {
      loadAnalysis(selectedProject);
    }
  }, [selectedProject, loadAnalysis]);

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      await triggerSync();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleSeed = async () => {
    setSyncing(true);
    setError(null);
    try {
      const result = await seedDemoData();
      await refresh();
      if (result.project_key) {
        setSelectedProject(result.project_key);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleSeedJira = async () => {
    setSyncing(true);
    setError(null);
    try {
      const { projects: jiraProjects } = await listJiraProjectsForSeed();
      if (jiraProjects.length === 0) {
        throw new Error(
          "No Jira projects found. Create a project at nfonandrew73.atlassian.net first (e.g. key: PMO)."
        );
      }
      const projectKey =
        jiraProjects.length === 1
          ? jiraProjects[0].key
          : window.prompt(
              `Enter project key to seed.\nAvailable: ${jiraProjects.map((p) => p.key).join(", ")}`,
              jiraProjects[0].key
            );
      if (!projectKey) return;

      const result = await seedJiraProject(projectKey.trim().toUpperCase());
      await refresh();
      setSelectedProject(result.project_key);
      if (result.tip) {
        setError(null);
        alert(`Created ${result.issues_created} issues in ${result.project_key}.\n\n${result.tip}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Jira seed failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleGenerateRaid = async () => {
    if (!selectedProject) return;
    setRaidLoading(true);
    setError(null);
    try {
      await generateRaid(selectedProject);
      await loadRaid(selectedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "RAID generation failed");
    } finally {
      setRaidLoading(false);
    }
  };

  const handleLoadSampleTranscript = async () => {
    try {
      const { transcript: sample } = await getSampleTranscript();
      setTranscript(sample);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sample");
    }
  };

  const handleAnalyzeMeeting = async () => {
    if (!selectedProject) return;
    setMeetingLoading(true);
    setError(null);
    try {
      const report = await analyzeMeeting(selectedProject, {
        transcript,
        title: "Sprint Review Meeting",
        create_jira_tickets: createJiraTickets,
      });
      setMeetingReport(report);
      if (createJiraTickets && report.jira_tickets_created.length > 0) {
        await refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Meeting analysis failed");
    } finally {
      setMeetingLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>PMO Intelligence Platform</h1>
          <p className="subtitle">Jira sync · Health · Risk · RAID · Meeting intelligence</p>
        </div>
        <div className="header-actions">
          <span className={`badge ${health === "healthy" ? "badge-green" : "badge-red"}`}>
            API: {health}
          </span>
          <button className="btn-secondary" onClick={handleSeed} disabled={syncing}>
            Load Demo Data
          </button>
          <button className="btn-secondary" onClick={handleSeedJira} disabled={syncing}>
            Seed Jira Issues
          </button>
          <button onClick={handleSync} disabled={syncing}>
            {syncing ? "Working…" : "Sync Jira"}
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="stats-grid">
        {[
          { label: "Projects", value: stats?.projects ?? "—" },
          { label: "Issues", value: stats?.issues ?? "—" },
          { label: "Epics", value: stats?.epics ?? "—" },
          { label: "Sprints", value: stats?.sprints ?? "—" },
        ].map((item) => (
          <div key={item.label} className="stat-card">
            <span className="stat-label">{item.label}</span>
            <span className="stat-value">{item.value}</span>
          </div>
        ))}
      </section>

      {projects.length > 0 && (
        <section className="panel">
          <div className="panel-header">
            <h2>Project Analysis</h2>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
            >
              {projects.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.key} — {p.name}
                </option>
              ))}
            </select>
          </div>

          {analyzing && <p className="muted">Running agents…</p>}

          {status && (
            <div className="analysis-grid">
              <div className="analysis-card">
                <div className="analysis-card-header">
                  <h3>Project Health</h3>
                  <span className={`health-badge ${healthClass(status.health)}`}>
                    {status.health}
                  </span>
                </div>
                <p>{status.executive_summary}</p>
                <div className="mini-stats">
                  <span><strong>{status.completed_stories}</strong> completed</span>
                  <span><strong>{status.at_risk_stories}</strong> at risk</span>
                </div>
                {status.sprint_progress.map((s) => (
                  <div key={s.sprint_name} className="progress-row">
                    <span>{s.sprint_name}</span>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${s.completion_pct}%` }} />
                    </div>
                    <span>{s.completion_pct}%</span>
                  </div>
                ))}
                <h4>Recommendations</h4>
                <ul>
                  {status.recommendations.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </div>

              <div className="analysis-card">
                <div className="analysis-card-header">
                  <h3>Risk Assessment</h3>
                  <span className={`risk-badge ${riskClass(risk?.risk_score ?? "Low")}`}>
                    {risk?.risk_score ?? "—"}
                  </span>
                </div>
                {risk && (
                  <>
                    <p>{risk.reasoning}</p>
                    <h4>Signals ({risk.signals.length})</h4>
                    <ul className="signal-list">
                      {risk.signals.map((s) => (
                        <li key={s.rule}>
                          <span className={`signal-severity ${riskClass(s.severity)}`}>{s.severity}</span>
                          {s.description}
                        </li>
                      ))}
                    </ul>
                    <h4>Recommended Actions</h4>
                    <ul>
                      {risk.recommended_actions.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          )}

          {status && (status.delayed_work.length > 0 || status.blocked_issues.length > 0) && (
            <div className="issues-grid">
              {status.delayed_work.length > 0 && (
                <div>
                  <h4>Delayed Work</h4>
                  <table>
                    <thead>
                      <tr><th>Key</th><th>Summary</th><th>Days Overdue</th></tr>
                    </thead>
                    <tbody>
                      {status.delayed_work.map((d) => (
                        <tr key={d.key}>
                          <td>{d.key}</td>
                          <td>{d.summary}</td>
                          <td>{d.days_overdue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {status.blocked_issues.length > 0 && (
                <div>
                  <h4>Blocked Issues</h4>
                  <table>
                    <thead>
                      <tr><th>Key</th><th>Summary</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                      {status.blocked_issues.map((b) => (
                        <tr key={b.key}>
                          <td>{b.key}</td>
                          <td>{b.summary}</td>
                          <td>{b.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {projects.length > 0 && selectedProject && (
        <section className="panel">
          <div className="panel-header">
            <h2>RAID Log</h2>
            <button className="btn-secondary" onClick={handleGenerateRaid} disabled={raidLoading}>
              {raidLoading ? "Generating…" : "Generate RAID Log"}
            </button>
          </div>
          <p className="muted">
            Risks, Assumptions, Issues, and Dependencies auto-generated from Jira data.
          </p>
          {raidEntries.length === 0 ? (
            <p className="muted">No RAID entries yet. Click Generate RAID Log.</p>
          ) : (
            <div className="raid-grid">
              {raidEntries.map((entry) => (
                <div key={entry.id} className="raid-card">
                  <div className="raid-card-header">
                    <span className={`raid-type ${raidTypeClass(entry.entry_type)}`}>{entry.entry_type}</span>
                    <span className={`signal-severity ${riskClass(entry.severity)}`}>{entry.severity}</span>
                  </div>
                  <h4>{entry.title}</h4>
                  <p className="raid-desc">{entry.description}</p>
                  <p><strong>Impact:</strong> {entry.impact}</p>
                  <p><strong>Mitigation:</strong> {entry.mitigation}</p>
                  {entry.jira_key && <p className="muted">Linked: {entry.jira_key}</p>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {projects.length > 0 && selectedProject && (
        <section className="panel">
          <div className="panel-header">
            <h2>Meeting Intelligence</h2>
            <div className="header-actions">
              <button className="btn-secondary" onClick={handleLoadSampleTranscript}>
                Load Sample
              </button>
              <button onClick={handleAnalyzeMeeting} disabled={meetingLoading}>
                {meetingLoading ? "Analyzing…" : "Analyze Transcript"}
              </button>
            </div>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={createJiraTickets}
              onChange={(e) => setCreateJiraTickets(e.target.checked)}
            />
            Create Jira tickets from action items
          </label>
          <textarea
            className="transcript-input"
            rows={8}
            placeholder="Paste Teams or Zoom transcript here…"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
          {meetingReport && (
            <div className="meeting-results">
              <h3>{meetingReport.title}</h3>
              <p>{meetingReport.summary}</p>
              <div className="meeting-columns">
                <div>
                  <h4>Action Items ({meetingReport.action_items.length})</h4>
                  <ul>
                    {meetingReport.action_items.map((a, i) => (
                      <li key={i}>{a.assignee ? `${a.assignee}: ` : ""}{a.description}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Decisions ({meetingReport.decisions.length})</h4>
                  <ul>
                    {meetingReport.decisions.map((d, i) => (
                      <li key={i}>{d.description}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4>Risks ({meetingReport.risks_identified.length})</h4>
                  <ul>
                    {meetingReport.risks_identified.map((r, i) => (
                      <li key={i}><span className={`signal-severity ${riskClass(r.severity)}`}>{r.severity}</span> {r.description}</li>
                    ))}
                  </ul>
                </div>
              </div>
              {meetingReport.jira_tickets_created.length > 0 && (
                <p className="muted">Jira tickets created: {meetingReport.jira_tickets_created.join(", ")}</p>
              )}
            </div>
          )}
        </section>
      )}

      <section className="panel">
        <h2>Projects</h2>
        {projects.length === 0 ? (
          <p className="muted">
            No projects yet. Click <strong>Load Demo Data</strong> to try agents without Jira,
            or configure Jira credentials and sync.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Name</th>
                <th>Issues</th>
                <th>Epics</th>
                <th>Sprints</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.key}>
                  <td>{p.key}</td>
                  <td>{p.name}</td>
                  <td>{p.issue_count}</td>
                  <td>{p.epic_count}</td>
                  <td>{p.sprint_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
