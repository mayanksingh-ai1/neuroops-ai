import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KnowledgeBase } from "./KnowledgeBase";

const doc = { id: "doc-1", name: "refunds.txt", status: "ready", chunk_count: 1, error_code: null };
const page = { workspace: "alpha", analytics_available: true, items: [doc] };
const answer = {
  status: "answered", message: "AI explanation — verify against evidence.",
  claims: [{ explanation: "Refunds are available within 30 days.", citation_id: "1" }],
  sources: [{ citation_id: "1", name: "refunds.txt", page_number: null, chunk_index: 0,
    passage: "Refunds are available within 30 days of delivery." }],
  calculated_analytics: { label: "Calculated from imported complaints.", total: 4,
    status_counts: { open: 4 }, top_categories: [{ category: "refund", count: 4 }] },
};

afterEach(() => vi.unstubAllGlobals());

async function connect() {
  fireEvent.change(screen.getByLabelText("Workspace access key"), { target: { value: "a".repeat(32) } });
  fireEvent.click(screen.getByRole("button", { name: "Connect workspace" }));
  await screen.findByText("refunds.txt");
}

describe("Knowledge Base", () => {
  it("connects with a workspace key and displays stored documents", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => page })));
    render(<KnowledgeBase />); await connect();
    expect(screen.getByText("ready · 1 chunks")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/knowledge/documents?limit=100", expect.objectContaining({
      headers: { "X-Workspace-Key": "a".repeat(32) }, cache: "no-store",
    }));
    expect(screen.queryByLabelText("Workspace access key")).not.toBeInTheDocument();
  });

  it("renders quoted sources separately from AI explanations and calculated counts", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith("/ask") ? answer : page })));
    render(<KnowledgeBase />); await connect();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "What is the refund policy?" } });
    fireEvent.click(screen.getByLabelText("Include calculated complaint totals and category counts"));
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("AI-generated explanation")).toBeInTheDocument();
    expect(screen.getByText("Quoted document evidence")).toBeInTheDocument();
    expect(screen.getByText("Refunds are available within 30 days of delivery.").tagName).toBe("BLOCKQUOTE");
    expect(screen.getByRole("region", { name: "Calculated complaint analytics" })).toHaveTextContent("Total complaints: 4");
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows insufficient evidence and clears stale answers", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith("/ask") ? {
      status: "insufficient_evidence", message: "The available documents do not provide enough information.", claims: [], sources: [],
    } : page })));
    render(<KnowledgeBase />); await connect();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "What about international orders?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Insufficient document evidence")).toBeInTheDocument();
    expect(screen.queryByText("Quoted document evidence")).not.toBeInTheDocument();
  });

  it("uploads a raw file only after sharing consent", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => ({ ok: true,
      json: async () => init.method === "POST" ? { document: doc, duplicate: false } : page })));
    render(<KnowledgeBase />); await connect();
    const file = new File(["Refund rules"], "rules.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText("Document"), { target: { files: [file] } });
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I am authorized/ }));
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText("Document processed and ready for questions.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/knowledge/documents?filename=rules.txt", expect.objectContaining({ method: "POST", body: file }));
  });

  it("shows connection errors without exposing documents", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: "A valid workspace key is required." }) })));
    render(<KnowledgeBase />);
    fireEvent.change(screen.getByLabelText("Workspace access key"), { target: { value: "a".repeat(32) } });
    fireEvent.click(screen.getByRole("button", { name: "Connect workspace" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A valid workspace key is required.");
    expect(screen.queryByText("Documents")).not.toBeInTheDocument();
  });

  it("shows empty and processing states without inventing answers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ ...page, items: [] }) })));
    render(<KnowledgeBase />);
    fireEvent.change(screen.getByLabelText("Workspace access key"), { target: { value: "a".repeat(32) } });
    fireEvent.click(screen.getByRole("button", { name: "Connect workspace" }));
    expect(await screen.findByText("No documents yet. Upload a company policy or guide to begin.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
  });
});
