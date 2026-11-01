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

const demoComplaints: ApiComplaint[] = [
  {
    complaint_id: "CMP-1001",
    title: "Delayed delivery for order #48291 with priority shipment",
    category: "Delivery Delay",
    status: "open",
    priority: "high",
    channel: "email",
    received_date: "2026-10-22",
    analysis: {
      status: "completed",
      category: "Delivery Delay",
      sentiment: "Negative",
      priority: "high",
      error_code: null,
      human_verified: false,
      details: { priority_rule: "delivery_deadline_exceeded", provider: "mock-demo" },
    },
  },
  {
    complaint_id: "CMP-1002",
    title: "Refund not credited after 14 business days",
    category: "Refund Issue",
    status: "in_progress",
    priority: "high",
    channel: "web",
    received_date: "2026-10-21",
    analysis: {
      status: "completed",
      category: "Refund Issue",
      sentiment: "Negative",
      priority: "high",
      error_code: null,
      human_verified: false,
      details: { priority_rule: "statutory_refund_timeline", provider: "mock-demo" },
    },
  },
  {
    complaint_id: "CMP-1003",
    title: "Packaging arrived torn, inner merchandise scratched",
    category: "Damaged Product",
    status: "open",
    priority: "medium",
    channel: "mobile_app",
    received_date: "2026-10-20",
    analysis: {
      status: "completed",
      category: "Damaged Product",
      sentiment: "Negative",
      priority: "medium",
      error_code: null,
      human_verified: false,
      details: { priority_rule: "transit_damage", provider: "mock-demo" },
    },
  },
  {
    complaint_id: "CMP-1004",
    title: "Wrong color received for winter jacket",
    category: "Wrong Item",
    status: "resolved",
    priority: "low",
    channel: "phone",
    received_date: "2026-10-19",
    analysis: {
      status: "completed",
      category: "Wrong Item",
      sentiment: "Neutral",
      priority: "low",
      error_code: null,
      human_verified: false,
      details: { priority_rule: "catalog_variance", provider: "mock-demo" },
    },
  },
  {
    complaint_id: "CMP-1005",
    title: "Support agent was very helpful in resolving billing query",
    category: "Customer Support",
    status: "resolved",
    priority: "low",
    channel: "chat",
    received_date: "2026-10-18",
    analysis: {
      status: "completed",
      category: "Customer Support",
      sentiment: "Positive",
      priority: "low",
      error_code: null,
      human_verified: false,
      details: { priority_rule: "positive_feedback", provider: "mock-demo" },
    },
  },
];

async function request<T>(path: string): Promise<T> {
  const response = await apiFetch(path, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function fetchDashboard(query = ""): Promise<DashboardData> {
  const suffix = query ? `&q=${encodeURIComponent(query)}` : "";
  try {
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
  } catch (err) {
    if (typeof window !== "undefined") {
      const q = query.toLowerCase();
      const filtered = q
        ? demoComplaints.filter(c => c.title.toLowerCase().includes(q) || c.category.toLowerCase().includes(q))
        : demoComplaints;
      return {
        complaints: filtered,
        total: filtered.length,
        categories: [
          { name: "Delivery Delay", count: 1, color: colors[0] },
          { name: "Refund Issue", count: 1, color: colors[1] },
          { name: "Damaged Product", count: 1, color: colors[2] },
          { name: "Wrong Item", count: 1, color: colors[3] },
          { name: "Customer Support", count: 1, color: colors[4] },
        ],
        status: { total: filtered.length, counts: { open: 2, in_progress: 1, resolved: 2 } },
        trend: [
          { day: "10-18", complaints: 1 },
          { day: "10-19", complaints: 1 },
          { day: "10-20", complaints: 1 },
          { day: "10-21", complaints: 1 },
          { day: "10-22", complaints: 1 },
        ],
      };
    }
    throw err;
  }
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
