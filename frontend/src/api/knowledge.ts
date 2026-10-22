import { apiFetch } from './access';
export type KnowledgeDocument = {
  id: string; name: string; file_type: string; size_bytes: number;
  status: "processing" | "ready" | "failed"; error_code: string | null;
  chunk_count: number; created_at: string; updated_at: string;
};
export type DocumentPage = {
  workspace: string; analytics_available: boolean; items: KnowledgeDocument[];
};
export type KnowledgeAnswer = {
  status: "answered" | "insufficient_evidence"; message: string;
  claims: { explanation: string; citation_id: string }[];
  sources: { citation_id: string; chunk_id: string; document_id: string; name: string;
    page_number: number | null; chunk_index: number; passage: string; similarity: number }[];
  calculated_analytics?: { label: string; total: number; status_counts: Record<string, number>;
    top_categories: { category: string; count: number }[]; as_of: string };
};

async function request<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(`/api/knowledge${path}`, {
    ...init, headers: { ...init.headers, "X-Workspace-Key": key },
    signal: AbortSignal.timeout(180000), cache: "no-store",
  });
  if (!response.ok) {
    let code = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail?.code === "string") code = body.detail.code.replace(/_/g, " ");
      else if (typeof body.detail === "string") code = body.detail;
    } catch { /* A proxy can return an HTML error page. */ }
    throw new Error(code);
  }
  return response.json() as Promise<T>;
}

export const listDocuments = (key: string) => request<DocumentPage>("/documents?limit=100", key);
export const uploadDocument = (key: string, file: File) => request<{ document: KnowledgeDocument; duplicate: boolean }>(
  `/documents?filename=${encodeURIComponent(file.name)}`, key,
  { method: "POST", headers: { "Content-Type": file.name.toLowerCase().endsWith(".pdf") ? "application/pdf" : "text/plain" }, body: file },
);
export const askKnowledge = (key: string, question: string, includeAnalytics: boolean) => request<KnowledgeAnswer>(
  "/ask", key, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, include_analytics: includeAnalytics }) },
);
