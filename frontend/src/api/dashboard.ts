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
    details: { priority_rule?: string };
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
