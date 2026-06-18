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

export function checkHealth(): Promise<{ status: string }> {
  return fetchJson("/health");
}
