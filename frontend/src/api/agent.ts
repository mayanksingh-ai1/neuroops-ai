import type { KnowledgeAnswer } from './knowledge';
import { apiFetch } from './access';

export type AgentReport = {
  status: string; human_verified: false;
  database_facts: null | { label: string; scope: string; total: number; counts: Record<string, number>;
    categories: { name: string; count: number }[]; trends: { day: string; complaints: number }[]; trend_days: number; as_of: string };
  document_findings: KnowledgeAnswer | null;
  recommendations: string[]; review_next_step: string; limitations: string[];
};
export type AgentRun = {
  id: string; task: string; status: string; created_at: number; expires_at: number;
  error_code: string | null; result: AgentReport | null;
  steps: { position: number; tool: string; arguments: Record<string, unknown>; status: string;
    attempts: number; output: Record<string, unknown> | null; error_code: string | null }[];
};

async function request<T>(key: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(`/api/agent/runs${path}`, { ...init, cache: 'no-store',
    signal: AbortSignal.timeout(15000), headers: { ...init.headers, 'X-Workspace-Key': key } });
  if (!response.ok) {
    let message = `Agent request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail?.code === 'string') message = body.detail.code.replace(/_/g, ' ');
      else if (typeof body.detail === 'string') message = body.detail;
    } catch { /* Proxy errors may not be JSON. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const listRuns = (key: string) => request<{ items: AgentRun[] }>(key, '');
export const getRun = (key: string, id: string) => request<AgentRun>(key, `/${encodeURIComponent(id)}`);
export const cancelRun = (key: string, id: string) => request<AgentRun>(key, `/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
export const createRun = (key: string, task: string) => request<AgentRun>(key, '', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task, provider_consent: true }),
});
