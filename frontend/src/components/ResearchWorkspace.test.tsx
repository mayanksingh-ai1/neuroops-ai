import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ResearchWorkspace } from "./ResearchWorkspace";

describe("ResearchWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the research workspace initial guide state", () => {
    render(<ResearchWorkspace />);
    expect(screen.getByRole("region", { name: "AI Research workspace" })).toBeInTheDocument();
    expect(
      screen.getByText(/Type a topic above to query stored customer complaints/)
    ).toBeInTheDocument();
  });

  it("executes complaint research and renders matched records", async () => {
    const mockResponses: Record<string, unknown> = {
      "/api/complaints": {
        total: 1,
        items: [
          {
            complaint_id: "CMP-999",
            title: "Refund delay after return",
            category: "Refund Issue",
            status: "open",
            priority: "high",
            channel: "Email",
            received_date: "2026-10-21",
            analysis: {
              status: "completed",
              category: "Refund Issue",
              priority: "high",
            },
          },
        ],
      },
      "/api/analytics/categories": [{ name: "Refund Issue", count: 1 }],
      "/api/analytics/status": { total: 1, counts: { open: 1, in_progress: 0, resolved: 0 } },
      "/api/analytics/trends": [{ day: "2026-10-21", complaints: 1 }],
    };

    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const match = Object.keys(mockResponses).find((k) => url.includes(k));
        return Promise.resolve({
          ok: true,
          json: async () => (match ? mockResponses[match] : []),
        });
      })
    );

    render(<ResearchWorkspace />);
    const input = screen.getByPlaceholderText(/Enter research topic/);
    fireEvent.change(input, { target: { value: "refund" } });
    fireEvent.click(screen.getByRole("button", { name: /Run Research/ }));

    expect(await screen.findByText("Refund delay after return")).toBeInTheDocument();
    expect(screen.getByText("CMP-999")).toBeInTheDocument();
    expect(screen.getByText("All Findings (1 complaints)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Copy Research Summary/ })).toBeInTheDocument();
  });

  it("queries grounded knowledge base when workspace key is provided", async () => {
    const mockResponses: Record<string, unknown> = {
      "/api/complaints": {
        total: 1,
        items: [
          {
            complaint_id: "CMP-888",
            title: "Damaged shipping box",
            category: "Damaged Product",
            status: "resolved",
            priority: "low",
            channel: "Chat",
            received_date: "2026-10-20",
          },
        ],
      },
      "/api/analytics/categories": [{ name: "Damaged Product", count: 1 }],
      "/api/analytics/status": { total: 1, counts: { open: 0, in_progress: 0, resolved: 1 } },
      "/api/analytics/trends": [{ day: "2026-10-20", complaints: 1 }],
      "/api/knowledge/ask": {
        status: "answered",
        message: "Policy requires returns within 30 days.",
        claims: [{ explanation: "Returns must be undamaged in box.", citation_id: "1" }],
        sources: [
          {
            citation_id: "1",
            chunk_id: "chk-1",
            document_id: "doc-1",
            name: "policy.pdf",
            page_number: 2,
            chunk_index: 0,
            passage: "Customers must return items within 30 days.",
            similarity: 0.85,
          },
        ],
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const match = Object.keys(mockResponses).find((k) => url.includes(k));
        return Promise.resolve({
          ok: true,
          json: async () => (match ? mockResponses[match] : []),
        });
      })
    );

    render(<ResearchWorkspace />);
    fireEvent.change(screen.getByPlaceholderText(/Enter research topic/), {
      target: { value: "damaged" },
    });
    fireEvent.change(screen.getByPlaceholderText(/X-Workspace-Key/), {
      target: { value: "workspace_key_12345" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Run Research/ }));

    expect(await screen.findByText("Damaged shipping box")).toBeInTheDocument();
    expect(screen.getByText("Policy requires returns within 30 days.")).toBeInTheDocument();
    expect(screen.getByText(/Returns must be undamaged in box/)).toBeInTheDocument();
    expect(screen.getByText(/"Customers must return items within 30 days."/)).toBeInTheDocument();
  });
});
