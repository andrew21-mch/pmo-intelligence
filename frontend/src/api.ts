const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface DashboardStats {
  projects: number;
  issues: number;
  epics: number;
  sprints: number;
  last_sync: {
    id: number;
    status: string;
    message: string | null;
    records_synced: number;
  } | null;
}

export interface ProjectSummary {
  key: string;
  name: string;
  issue_count: number;
  epic_count: number;
  sprint_count: number;
}

export interface SyncResponse {
  id: number;
  status: string;
  message: string | null;
  records_synced: number;
}

export interface ProjectStatusReport {
  project_key: string;
  project_name: string;
  health: "Green" | "Amber" | "Red";
  executive_summary: string;
  sprint_progress: {
    sprint_name: string;
    state: string | null;
    completed_stories: number;
    total_stories: number;
    completion_pct: number;
  }[];
  completed_stories: number;
  at_risk_stories: number;
  delayed_work: {
    key: string;
    summary: string;
    assignee: string | null;
    days_overdue: number;
  }[];
  blocked_issues: {
    key: string;
    summary: string;
    assignee: string | null;
    status: string | null;
  }[];
  recommendations: string[];
}

export interface RiskAssessment {
  project_key: string;
  project_name: string;
  risk_score: "Low" | "Medium" | "High";
  signals: {
    rule: string;
    severity: "Low" | "Medium" | "High";
    description: string;
    affected_items: string[];
  }[];
  reasoning: string;
  recommended_actions: string[];
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new Error(`Cannot reach API at ${API_URL}. Is docker-compose running?`);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? body.message ?? message;
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new Error(message);
  }
  return response.json();
}

export function getStats(): Promise<DashboardStats> {
  return fetchJson("/api/jira/stats");
}

export function getProjects(): Promise<ProjectSummary[]> {
  return fetchJson("/api/jira/projects");
}

export function triggerSync(): Promise<SyncResponse> {
  return fetchJson("/api/jira/sync", { method: "POST" });
}

export function seedDemoData(): Promise<{ status: string; project_key?: string; issues?: number }> {
  return fetchJson("/api/dev/seed", { method: "POST" });
}

export function listJiraProjectsForSeed(): Promise<{ projects: { key: string; name: string }[] }> {
  return fetchJson("/api/dev/jira/projects");
}

export function seedJiraProject(projectKey: string): Promise<{
  status: string;
  project_key: string;
  issues_created: number;
  issue_keys: string[];
  tip?: string;
}> {
  return fetchJson("/api/dev/seed-jira", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_key: projectKey }),
  });
}

export function getProjectStatus(projectKey: string): Promise<ProjectStatusReport> {
  return fetchJson(`/api/agents/projects/${projectKey}/status`);
}

export function getProjectRisk(projectKey: string): Promise<RiskAssessment> {
  return fetchJson(`/api/agents/projects/${projectKey}/risk`);
}

export interface RaidEntry {
  id: number;
  project_key: string;
  entry_type: "Risk" | "Assumption" | "Issue" | "Dependency";
  title: string;
  description: string;
  severity: "Low" | "Medium" | "High";
  impact: string;
  mitigation: string;
  source: string;
  jira_key: string | null;
  created_at: string;
}

export interface RaidLogReport {
  project_key: string;
  project_name: string;
  entries: Omit<RaidEntry, "id" | "project_key" | "created_at">[];
  summary: string;
}

export interface MeetingReport {
  project_key: string;
  title: string;
  summary: string;
  action_items: { description: string; assignee: string | null; due_date: string | null }[];
  decisions: { description: string }[];
  risks_identified: { description: string; severity: string }[];
  jira_tickets_created: string[];
}

export function generateRaid(projectKey: string): Promise<RaidLogReport> {
  return fetchJson(`/api/agents/projects/${projectKey}/raid/generate`, { method: "POST" });
}

export function getRaidEntries(projectKey: string): Promise<RaidEntry[]> {
  return fetchJson(`/api/agents/projects/${projectKey}/raid`);
}

export function analyzeMeeting(
  projectKey: string,
  body: { transcript: string; title?: string; create_jira_tickets?: boolean }
): Promise<MeetingReport> {
  return fetchJson(`/api/agents/projects/${projectKey}/meetings/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getSampleTranscript(): Promise<{ transcript: string }> {
  return fetchJson("/api/agents/meetings/sample-transcript");
}

export interface DocumentInfo {
  id: number;
  filename: string;
  title: string;
  doc_type: string;
  project_key: string | null;
  chunk_count: number;
  uploaded_at: string;
}

export interface ExecutiveReport {
  template: string;
  project_key: string;
  project_name: string;
  title: string;
  generated_at: string;
  markdown: string;
  html: string;
  health: string;
  risk_score: string;
  citations: { title: string; excerpt: string; doc_id: number | null }[];
}

export function listDocuments(projectKey?: string): Promise<DocumentInfo[]> {
  const q = projectKey ? `?project_key=${projectKey}` : "";
  return fetchJson(`/api/documents${q}`);
}

export async function uploadDocument(
  file: File,
  opts: { title?: string; doc_type?: string; project_key?: string }
): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  if (opts.title) form.append("title", opts.title);
  form.append("doc_type", opts.doc_type || "governance");
  if (opts.project_key) form.append("project_key", opts.project_key);

  const response = await fetch(`${API_URL}/api/documents/upload`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await response.text() || "Upload failed");
  return response.json();
}

export async function seedGovernanceDoc(projectKey?: string): Promise<DocumentInfo> {
  const form = new FormData();
  if (projectKey) form.append("project_key", projectKey);
  const response = await fetch(`${API_URL}/api/documents/seed-governance`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await response.text() || "Seed failed");
  return response.json();
}

export function generateReport(
  projectKey: string,
  template: string
): Promise<ExecutiveReport> {
  return fetchJson(`/api/agents/projects/${projectKey}/reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template }),
  });
}

export async function downloadReportPdf(html: string, title: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/agents/reports/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ html, title }),
  });
  if (!response.ok) {
    throw new Error((await response.text()) || "PDF export failed");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[^\w\s-]/g, "").trim() || "report"}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function checkHealth(): Promise<{ status: string }> {
  return fetchJson("/health");
}
