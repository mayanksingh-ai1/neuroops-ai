import { apiFetch } from './access';
export type Metric = { score: number | null; status: string; reason: string; raw_score?: number | null };
export type Review = { id: string; reviewer_id: string; decision: string; feedback: string;
  corrections: Record<string, { score: number | null; reason: string }>; created_at: number };
export type Evaluation = { id: string; case_id: string; status: string; error_code: string | null;
  deterministic: Record<string, Metric>; judged: Record<string, Metric>; evaluator: Record<string, unknown>;
  rubric: Record<string, unknown>; reviews: Review[]; created_at: number; human_verified: false };
export type Evidence = { chunk_id: string; document_id: string; name: string; page_number: number | null; passage: string };
export type EvalCase = { id: string; dataset: string; model: string; provider: string; question: string;
  response: string; reference: string | null; created_at: number;
  context: { evidence: Evidence[]; instructions: string; policy: string; rules: Record<string, unknown>;
    citations: { chunk_id: string; quote: string }[]; metadata: Record<string, string> };
  latest_evaluation?: Evaluation | null; evaluations?: Evaluation[] };
export type Summary = { evaluations: number; distinct_cases: number; completed: number; failed: number; label: string;
  metrics: { method: string; metric: string; mean: number | null; assessed: number; not_assessed: number;
    distribution: { zero: number; partial: number; one: number } }[];
  common_failures: { type: string; count: number }[]; models: { model: string; evaluations: number; distinct_cases: number }[] };
export type Comparison = { id: string; created_at: number; limitation: string;
  items: { case: EvalCase; evaluation: Evaluation | null }[];
  pairwise: { status: string; preference: string | null; error_code?: string; order_agreement?: boolean;
    judgments?: { order: string[]; preference: string; reason: string }[] } };
export type ImportResult = { total_rows: number; inserted: number; duplicates: number; invalid: number;
  errors: { row: number; message: string }[]; errors_truncated: boolean };

async function response(key: string, path: string, init: RequestInit = {}) {
  const result = await apiFetch(`/api/evaluation${path}`, { ...init, cache: 'no-store', signal: AbortSignal.timeout(90000),
    headers: { ...init.headers, 'X-Workspace-Key': key } });
  if (!result.ok) {
    let message = `Evaluation request failed (${result.status}).`;
    try {
      const body = await result.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (body.detail?.code) message = String(body.detail.code).replace(/_/g, ' ');
      else if (Array.isArray(body.detail)) message = body.detail.map((error: { loc: string[]; msg: string }) => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('; ');
    } catch { /* A proxy may return HTML. */ }
    throw new Error(message);
  }
  return result;
}
async function request<T>(key: string, path: string, init?: RequestInit): Promise<T> {
  return (await response(key, path, init)).json() as Promise<T>;
}
const body = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
export const listCases = (key: string, query = '') => request<{ items: EvalCase[]; total: number }>(key, `/cases?${query}`);
export const caseDetail = (key: string, id: string) => request<EvalCase>(key, `/cases/${encodeURIComponent(id)}`);
export const summary = (key: string, query = '') => request<Summary>(key, `/summary?${query}`);
export const createCase = (key: string, value: unknown) => request<{ case: EvalCase; duplicate: boolean }>(key, '/cases', body(value));
export const importCases = (key: string, file: File) => request<ImportResult>(key, '/cases/import', { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file });
export const evaluateCase = (key: string, id: string, useJudge: boolean, consent: boolean) => request<Evaluation>(key,
  `/cases/${encodeURIComponent(id)}/evaluate`, body({ use_judge: useJudge, provider_consent: consent }));
export const comparisons = (key: string) => request<{ items: Comparison[] }>(key, '/comparisons');
export const compare = (key: string, ids: string[], useJudge: boolean, consent: boolean) => request<Comparison>(key, '/comparisons',
  body({ case_ids: ids, use_judge: useJudge, provider_consent: consent }));
export const review = (key: string, reviewerKey: string, id: string, value: unknown) => request<Review>(key,
  `/results/${encodeURIComponent(id)}/reviews`, { ...body(value), headers: { 'Content-Type': 'application/json', 'X-Reviewer-Key': reviewerKey } });
export const searchEvidence = (key: string, question: string, consent: boolean) => request<{ sources: Evidence[] }>(key, '/evidence/search',
  body({ question, provider_consent: consent }));
export const exportResults = async (key: string, query: string, format: 'csv' | 'json') =>
  (await response(key, `/export?${query}&format=${format}`)).blob();
