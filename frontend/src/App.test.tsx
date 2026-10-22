import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const responses: Record<string, unknown> = {
  "/api/complaints?limit=10": { total: 2, items: [
    { complaint_id: "CMP-1", title: "Refund still pending", category: "refund delay", status: "open", priority: "high", channel: "Email", received_date: "2026-10-18" },
    { complaint_id: "CMP-2", title: "Package damaged", category: "damaged item", status: "resolved", priority: "medium", channel: "Chat", received_date: "2026-10-19" },
  ] },
  "/api/analytics/categories": [{ name: "refund delay", count: 1 }, { name: "damaged item", count: 1 }],
  "/api/analytics/status": { total: 2, counts: { open: 1, in_progress: 0, resolved: 1 } },
  "/api/analytics/trends": [{ day: "2026-10-18", complaints: 1 }, { day: "2026-10-19", complaints: 1 }],
};

afterEach(() => vi.unstubAllGlobals());

function mockApi() {
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ ok: true, json: async () => responses[url] ?? responses["/api/complaints?limit=10"] })));
}

describe("database-backed dashboard", () => {
  it("renders API data instead of Phase 1 sample figures", async () => {
    mockApi(); render(<App />);
    expect(await screen.findByText("Stored records")).toBeInTheDocument();
    expect(screen.getByText("Refund still pending")).toBeInTheDocument();
    expect(screen.getByText("50.0%")).toBeInTheDocument();
  });

  it("sends search input to the backend", async () => {
    mockApi(); render(<App />);
    await screen.findByText("Refund still pending");
    fireEvent.change(screen.getByRole("textbox", { name: "Search complaints" }), { target: { value: "refund" } });
    expect(await screen.findByText("Refund still pending")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/complaints?limit=10&q=refund", expect.anything());
  });

  it("opens complaint intelligence and displays the unanalyzed state", async () => {
    mockApi(); render(<App />);
    await screen.findByText("Refund still pending");
    fireEvent.click(screen.getByRole("button", { name: "Complaint Analysis" }));
    expect(screen.getByRole("region", { name: "Stored complaint intelligence" })).toBeInTheDocument();
    expect(screen.getAllByText("Not analyzed")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Classify Complaints/ })).toBeEnabled();
  });

  it("opens classification modal when Classify Complaints is clicked", async () => {
    mockApi(); render(<App />);
    await screen.findByText("Refund still pending");
    fireEvent.click(screen.getByRole("button", { name: "Complaint Analysis" }));
    fireEvent.click(screen.getByRole("button", { name: /Classify Complaints/ }));
    expect(screen.getByRole("dialog", { name: /Run AI Classification/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Operator Key/)).toBeInTheDocument();
  });

  it("shows the empty state when the database contains no complaints", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ ok: true, json: async () => url.includes("complaints") ? { total: 0, items: [] } : url.includes("status") ? { total: 0, counts: { open: 0, in_progress: 0, resolved: 0 } } : [] })));
    render(<App />);
    expect(await screen.findByText("No complaint data yet")).toBeInTheDocument();
    expect(screen.getByText("No complaints found")).toBeInTheDocument();
  });
});
