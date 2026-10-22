import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ComplaintClassifyModal } from "./ComplaintClassifyModal";
import type { ApiComplaint } from "../api/dashboard";

const dummyComplaints: ApiComplaint[] = [
  {
    complaint_id: "TEST-1",
    title: "Delivery delay parcel lost",
    category: "Delivery Delay",
    status: "open",
    priority: "medium",
    channel: "Email",
    received_date: "2026-10-20",
    analysis: null,
  },
  {
    complaint_id: "TEST-2",
    title: "Wrong item delivered",
    category: "Wrong Item",
    status: "open",
    priority: "low",
    channel: "Chat",
    received_date: "2026-10-21",
    analysis: null,
  },
];

describe("ComplaintClassifyModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders when open and displays target complaint counts", () => {
    render(
      <ComplaintClassifyModal
        open={true}
        onClose={vi.fn()}
        complaints={dummyComplaints}
        onSuccess={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { name: "Run AI Classification" })).toBeInTheDocument();
    expect(screen.getByText(/Unanalyzed \/ Failed only \(2\)/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Operator Key/)).toBeInTheDocument();
  });

  it("validates that operator key is at least 32 characters", async () => {
    render(
      <ComplaintClassifyModal
        open={true}
        onClose={vi.fn()}
        complaints={dummyComplaints}
        onSuccess={vi.fn()}
      />
    );

    const input = screen.getByLabelText(/Operator Key/);
    fireEvent.change(input, { target: { value: "short_key" } });
    fireEvent.click(screen.getByRole("button", { name: /Start Classification/ }));

    expect(
      await screen.findByText(/Operator key \(X-Import-Key\) must be at least 32 characters long/)
    ).toBeInTheDocument();
  });

  it("triggers batch classification with valid operator key and calls onSuccess", async () => {
    const onSuccess = vi.fn();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            id: "uuid-1",
            complaint_id: "TEST-1",
            status: "completed",
            category: "Delivery Delay",
            sentiment: "Negative",
            priority: "medium",
            details: { priority_rule: "default", provider: "mock" },
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    render(
      <ComplaintClassifyModal
        open={true}
        onClose={vi.fn()}
        complaints={[dummyComplaints[0]]}
        onSuccess={onSuccess}
      />
    );

    const input = screen.getByLabelText(/Operator Key/);
    fireEvent.change(input, { target: { value: "x".repeat(32) } });
    fireEvent.click(screen.getByRole("button", { name: /Start Classification/ }));

    await waitFor(() => {
      expect(screen.getByText(/Batch Finished: 1 completed, 0 failed/)).toBeInTheDocument();
    });
    expect(onSuccess).toHaveBeenCalled();
  });

  it("displays helpful error explanation when missing_api_key occurs", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: { code: "missing_api_key" } }),
    });
    vi.stubGlobal("fetch", mockFetch);

    render(
      <ComplaintClassifyModal
        open={true}
        onClose={vi.fn()}
        complaints={dummyComplaints}
        onSuccess={vi.fn()}
      />
    );

    const input = screen.getByLabelText(/Operator Key/);
    fireEvent.change(input, { target: { value: "x".repeat(32) } });
    fireEvent.click(screen.getByRole("button", { name: /Start Classification/ }));

    expect(
      await screen.findByText(/LLM provider is not configured \(missing_api_key\)/)
    ).toBeInTheDocument();
  });
});
