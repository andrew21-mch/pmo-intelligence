import { useCallback, useEffect, useMemo, useState } from "react";
import {
  analyzeMeeting,
  checkHealth,
  DashboardStats,
  DocumentInfo,
  ExecutiveReport,
  generateRaid,
  generateReport,
  getProjectRisk,
  getProjects,
  getProjectStatus,
  getRaidEntries,
  getSampleTranscript,
  getStats,
  listDocuments,
  MeetingReport,
  ProjectSummary,
  ProjectStatusReport,
  RaidEntry,
  RiskAssessment,
  seedDemoData,
  seedGovernanceDoc,
  seedJiraProject,
  listJiraProjectsForSeed,
  triggerSync,
  uploadDocument,
  downloadReportPdf,
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

const RAID_COLUMNS = [
  { type: "Risk" as const, letter: "R", label: "Risks", hint: "What might go wrong" },
  { type: "Assumption" as const, letter: "A", label: "Assumptions", hint: "What we believe is true" },
  { type: "Issue" as const, letter: "I", label: "Issues", hint: "What is wrong now" },
  { type: "Dependency" as const, letter: "D", label: "Dependencies", hint: "What we rely on" },
];

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
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [report, setReport] = useState<ExecutiveReport | null>(null);
  const [reportTemplate, setReportTemplate] = useState("weekly");
  const [reportView, setReportView] = useState<"markdown" | "html">("html");
  const [reportLoading, setReportLoading] = useState(false);
  const [pdfExportLoading, setPdfExportLoading] = useState(false);
  const [docLoading, setDocLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const raidByType = useMemo(() => {
    const grouped: Record<string, RaidEntry[]> = {
      Risk: [],
      Assumption: [],
      Issue: [],
      Dependency: [],
    };
    for (const entry of raidEntries) {
      grouped[entry.entry_type]?.push(entry);
    }
    return grouped;
  }, [raidEntries]);

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

  const loadDocuments = useCallback(async (projectKey: string) => {
    try {
      const docs = await listDocuments(projectKey);
      setDocuments(docs);
    } catch {
      setDocuments([]);
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
      await Promise.all([loadRaid(projectKey), loadDocuments(projectKey)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, [loadRaid, loadDocuments]);

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

  const handleSeedGovernance = async () => {
    if (!selectedProject) return;
    setDocLoading(true);
    try {
      await seedGovernanceDoc(selectedProject);
      await loadDocuments(selectedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to seed governance doc");
    } finally {
      setDocLoading(false);
    }
  };

  const handleUploadDocument = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedProject) return;
    setDocLoading(true);
    try {
      await uploadDocument(file, { project_key: selectedProject, doc_type: "governance" });
      await loadDocuments(selectedProject);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setDocLoading(false);
      e.target.value = "";
    }
  };

  const handleGenerateReport = async () => {
    if (!selectedProject) return;
    setReportLoading(true);
    setError(null);
    try {
      const result = await generateReport(selectedProject, reportTemplate);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setReportLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!report) return;
    setPdfExportLoading(true);
    setError(null);
    try {
      await downloadReportPdf(report.html, report.title);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF export failed");
    } finally {
      setPdfExportLoading(false);
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
          <p className="subtitle">Jira sync · RAG · Reports · RAID · Meeting intelligence</p>
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
        <section className="panel raid-panel">
          <div className="raid-panel-top">
            <div>
              <h2>RAID Log</h2>
              <p className="raid-subtitle">
                Risks · Assumptions · Issues · Dependencies — auto-generated from Jira
              </p>
            </div>
            <button className="btn-secondary" onClick={handleGenerateRaid} disabled={raidLoading}>
              {raidLoading ? "Generating…" : "Generate RAID Log"}
            </button>
          </div>

          {raidEntries.length > 0 && (
            <div className="raid-summary">
              {RAID_COLUMNS.map((col) => (
                <div key={col.type} className={`raid-summary-item ${raidTypeClass(col.type)}`}>
                  <span className="raid-summary-letter">{col.letter}</span>
                  <div>
                    <span className="raid-summary-count">{raidByType[col.type].length}</span>
                    <span className="raid-summary-label">{col.label}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {raidEntries.length === 0 ? (
            <div className="raid-empty">
              <div className="raid-empty-letters">
                {RAID_COLUMNS.map((col) => (
                  <span key={col.type} className={`raid-empty-letter ${raidTypeClass(col.type)}`}>
                    {col.letter}
                  </span>
                ))}
              </div>
              <p>No RAID entries yet</p>
              <span className="muted">Generate a log from your synced Jira data</span>
            </div>
          ) : (
            <div className="raid-board">
              {RAID_COLUMNS.map((col) => (
                <div key={col.type} className={`raid-column ${raidTypeClass(col.type)}`}>
                  <div className="raid-column-header">
                    <span className="raid-column-letter">{col.letter}</span>
                    <div>
                      <h3>{col.label}</h3>
                      <span className="raid-column-hint">{col.hint}</span>
                    </div>
                    <span className="raid-column-count">{raidByType[col.type].length}</span>
                  </div>
                  <div className="raid-column-body">
                    {raidByType[col.type].length === 0 ? (
                      <p className="raid-column-empty">None detected</p>
                    ) : (
                      raidByType[col.type].map((entry) => (
                        <article key={entry.id} className="raid-entry">
                          <div className="raid-entry-top">
                            <span className={`raid-severity ${riskClass(entry.severity)}`}>
                              {entry.severity}
                            </span>
                            {entry.jira_key && (
                              <span className="raid-jira-key">{entry.jira_key}</span>
                            )}
                          </div>
                          <h4>{entry.title}</h4>
                          <p className="raid-entry-desc">{entry.description}</p>
                          <div className="raid-entry-field">
                            <span className="raid-field-label">Impact</span>
                            <p>{entry.impact}</p>
                          </div>
                          <div className="raid-entry-field raid-entry-mitigation">
                            <span className="raid-field-label">Mitigation</span>
                            <p>{entry.mitigation}</p>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
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

      {projects.length > 0 && selectedProject && (
        <section className="panel">
          <div className="panel-header">
            <h2>Knowledge Base (RAG)</h2>
            <div className="header-actions">
              <button className="btn-secondary" onClick={handleSeedGovernance} disabled={docLoading}>
                Load Sample Governance Doc
              </button>
              <label className="upload-btn">
                {docLoading ? "Uploading…" : "Upload Document"}
                <input type="file" accept=".txt,.md,.markdown" onChange={handleUploadDocument} hidden />
              </label>
            </div>
          </div>
          <p className="muted">Upload PMO governance docs — agents cite them in executive reports.</p>
          {documents.length === 0 ? (
            <p className="muted">No documents indexed yet.</p>
          ) : (
            <table>
              <thead>
                <tr><th>Title</th><th>Type</th><th>Chunks</th><th>Uploaded</th></tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id}>
                    <td>{d.title}</td>
                    <td>{d.doc_type}</td>
                    <td>{d.chunk_count}</td>
                    <td>{d.uploaded_at.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {projects.length > 0 && selectedProject && (
        <section className="panel report-panel">
          <div className="panel-header">
            <h2>Executive Reporting</h2>
            <div className="header-actions">
              <select value={reportTemplate} onChange={(e) => setReportTemplate(e.target.value)}>
                <option value="weekly">Weekly Status</option>
                <option value="monthly">Monthly Portfolio</option>
                <option value="steering_committee">Steering Committee</option>
              </select>
              <button onClick={handleGenerateReport} disabled={reportLoading}>
                {reportLoading ? "Generating…" : "Generate Report"}
              </button>
            </div>
          </div>
          {report && (
            <>
              <div className="report-meta">
                <span className={`health-badge ${healthClass(report.health)}`}>{report.health}</span>
                <span className={`risk-badge ${riskClass(report.risk_score)}`}>Risk: {report.risk_score}</span>
                <span className="muted">{report.generated_at}</span>
              </div>
              {report.citations.length > 0 && (
                <div className="report-citations">
                  <h4>Governance Citations ({report.citations.length})</h4>
                  {report.citations.map((c, i) => (
                    <blockquote key={i}><strong>{c.title}</strong> — {c.excerpt}</blockquote>
                  ))}
                </div>
              )}
              <div className="report-tabs">
                <button
                  className={reportView === "html" ? "tab-active" : "btn-secondary"}
                  onClick={() => setReportView("html")}
                >
                  Report Preview
                </button>
                <button
                  className={reportView === "markdown" ? "tab-active" : "btn-secondary"}
                  onClick={() => setReportView("markdown")}
                >
                  Raw Markdown
                </button>
                <button
                  className="btn-secondary report-export-btn"
                  onClick={handleDownloadPdf}
                  disabled={pdfExportLoading}
                >
                  {pdfExportLoading ? "Exporting…" : "Download PDF"}
                </button>
              </div>
              {reportView === "html" ? (
                <iframe
                  className="report-iframe"
                  title="Report preview"
                  srcDoc={report.html}
                  sandbox=""
                />
              ) : (
                <pre className="report-preview">{report.markdown}</pre>
              )}
            </>
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
