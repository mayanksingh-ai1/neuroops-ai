import { apiFetch } from './access';
export type ApiComplaint = {
  complaint_id: string;
  title: string;
  category: string;
  status: "open" | "in_progress" | "resolved";
  priority: "low" | "medium" | "high";
  channel: string;
  received_date: string;
  analysis?: {
    status: "completed" | "failed";
    category: string | null;
    sentiment: "Positive" | "Neutral" | "Negative" | null;
    priority: "low" | "medium" | "high" | null;
    error_code: string | null;
    human_verified: false;
    details: { priority_rule?: string; provider?: string };
  } | null;
};

export type DashboardData = {
  complaints: ApiComplaint[];
  total: number;
  categories: { name: string; count: number; color: string }[];
  status: { total: number; counts: Record<string, number> };
  trend: { day: string; complaints: number }[];
};

const colors = ["#818cf8", "#a78bfa", "#38bdf8", "#2dd4bf", "#fbbf24"];

async function request<T>(path: string): Promise<T> {
  const response = await apiFetch(path, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function fetchDashboard(query = ""): Promise<DashboardData> {
  const suffix = query ? `&q=${encodeURIComponent(query)}` : "";
  const [complaintPage, categoryRows, status, trend] = await Promise.all([
    request<{ total: number; items: ApiComplaint[] }>(`/api/complaints?limit=10${suffix}`),
    request<{ name: string; count: number }[]>("/api/analytics/categories"),
    request<{ total: number; counts: Record<string, number> }>("/api/analytics/status"),
    request<{ day: string; complaints: number }[]>("/api/analytics/trends"),
  ]);
  return {
    complaints: complaintPage.items,
    total: complaintPage.total,
    categories: categoryRows.map((row, index) => ({ ...row, color: colors[index % colors.length] })),
    status,
    trend: trend.map((row) => ({ ...row, day: row.day.slice(5) })),
  };
}

export type ImportError = {
  row: number;
  fields?: Record<string, string>;
  message?: string;
};

export type ImportResult = {
  total_rows: number;
  inserted: number;
  duplicates: number;
  invalid: number;
  errors: ImportError[];
  errors_truncated: boolean;
};

export async function importComplaintsCsv(file: File, importKey: string): Promise<ImportResult> {
  if (file.size > 2 * 1024 * 1024) {
    throw new Error("CSV exceeds the 2 MiB limit.");
  }
  const response = await apiFetch("/api/complaints/import", {
    method: "POST",
    headers: {
      "Content-Type": "text/csv",
      "X-Import-Key": importKey.trim(),
    },
    body: file,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ")
          : `Import failed (${response.status})`;
    throw new Error(message);
  }
  return data as ImportResult;
}

export type ClassifyItemResponse = {
  id: string;
  complaint_id: string;
  status: "completed" | "failed" | "not_found";
  category: string | null;
  sentiment: "Positive" | "Neutral" | "Negative" | null;
  priority: "low" | "medium" | "high" | null;
  error_code: string | null;
  human_verified: false;
  details: { priority_rule?: string; provider?: string };
  http_status?: number;
};

export async function classifyComplaint(complaintId: string, importKey: string): Promise<ClassifyItemResponse> {
  const response = await apiFetch(`/api/complaints/${encodeURIComponent(complaintId)}/classify`, {
    method: "POST",
    headers: {
      "X-Import-Key": importKey.trim(),
    },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.code
          ? `Classification error: ${detail.code}`
          : `Classification failed (${response.status})`;
    throw new Error(message);
  }
  return data as ClassifyItemResponse;
}

export async function classifyBatch(
  complaintIds: string[],
  importKey: string
): Promise<{ items: ClassifyItemResponse[] }> {
  const results: ClassifyItemResponse[] = [];
  const chunkSize = 5;
  for (let i = 0; i < complaintIds.length; i += chunkSize) {
    const chunk = complaintIds.slice(i, i + chunkSize);
    const response = await apiFetch("/api/complaints/classify-batch", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Import-Key": importKey.trim(),
      },
      body: JSON.stringify({ complaint_ids: chunk }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ")
            : `Batch classification failed (${response.status})`;
      throw new Error(message);
    }
    if (data?.items) {
      results.push(...data.items);
    }
  }
  return { items: results };
}
