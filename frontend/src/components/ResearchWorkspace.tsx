import { useState, type FormEvent } from "react";
import { Search, Sparkles, BookOpen, Database, AlertCircle, Copy, Check, Key, Loader2 } from "lucide-react";
import { fetchDashboard, type ApiComplaint } from "../api/dashboard";
import { askKnowledge, type KnowledgeAnswer } from "../api/knowledge";

export function ResearchWorkspace() {
  const [topic, setTopic] = useState("");
  const [workspaceKey, setWorkspaceKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const [matchedComplaints, setMatchedComplaints] = useState<ApiComplaint[]>([]);
  const [totalFound, setTotalFound] = useState<number | null>(null);
  const [knowledgeResult, setKnowledgeResult] = useState<KnowledgeAnswer | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "complaints" | "policy">("all");

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!topic.trim()) {
      setError("Please enter a research topic or search query.");
      return;
    }

    setBusy(true);
    setError("");
    setKnowledgeResult(null);

    try {
      // 1. Fetch matching complaints from database
      const dashboard = await fetchDashboard(topic.trim());
      setMatchedComplaints(dashboard.complaints);
      setTotalFound(dashboard.total);

      // 2. If workspace key provided, also query grounded knowledge base
      if (workspaceKey.trim()) {
        try {
          const answer = await askKnowledge(workspaceKey.trim(), topic.trim(), true);
          setKnowledgeResult(answer);
        } catch (kbErr) {
          // If knowledge query fails, report it without blocking complaint findings
          console.warn("Knowledge base query note:", kbErr);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research query failed.");
    } finally {
      setBusy(false);
    }
  }

  function copySummary() {
    const summaryText = [
      `=== NeuroOps AI Research Summary: "${topic}" ===`,
      `Total Matching Complaints in Database: ${totalFound ?? 0}`,
      matchedComplaints.length > 0
        ? `\nKey Complaints:\n` +
          matchedComplaints
            .slice(0, 5)
            .map((c) => `- [${c.complaint_id}] ${c.title} (${c.category} · Priority: ${c.priority})`)
            .join("\n")
        : "",
      knowledgeResult
        ? `\nGrounded Policy Guidance:\n${knowledgeResult.message}\n` +
          knowledgeResult.claims.map((claim) => `* ${claim.explanation} [${claim.citation_id}]`).join("\n")
        : "",
      `\nGenerated on: ${new Date().toLocaleString()} (AI-assisted · Unverified)`,
    ].filter(Boolean).join("\n");

    void navigator.clipboard.writeText(summaryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  return (
    <section className="panel p-6" aria-label="AI Research workspace">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "14px" }}>
        <div>
          <h2 style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Search size={20} className="text-indigo-400" /> AI Research & Trend Synthesis
          </h2>
          <p className="mt-2 text-slate-300" style={{ fontSize: "0.88rem" }}>
            Investigate complaint patterns and cross-reference operational feedback with grounded company policies.
          </p>
        </div>
        {totalFound !== null && (
          <button
            type="button"
            className="export-button"
            onClick={copySummary}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            {copied ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />}
            {copied ? "Copied Summary" : "Copy Research Summary"}
          </button>
        )}
      </div>

      <form onSubmit={handleSearch} style={{ marginTop: "20px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "center" }}>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Enter research topic (e.g. 'refund delay', 'damaged shipping parcel', 'double billing')..."
              style={{
                width: "100%",
                padding: "10px 14px",
                background: "#080d1a",
                border: "1px solid #273249",
                borderRadius: "8px",
                color: "#f1f5f9",
                fontSize: "0.9rem",
                outline: "none",
              }}
              disabled={busy}
            />
          </div>
          <button
            type="submit"
            className="export-button"
            style={{
              background: "#4f46e5",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "10px 18px",
            }}
            disabled={busy || !topic.trim()}
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            <span>{busy ? "Synthesizing…" : "Run Research"}</span>
          </button>
        </div>

        <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <label style={{ fontSize: "0.78rem", color: "#94a3b8", display: "flex", alignItems: "center", gap: "5px" }}>
            <Key size={13} />
            Optional Workspace Key (for RAG Policy Grounding):
          </label>
          <input
            type="password"
            value={workspaceKey}
            onChange={(e) => setWorkspaceKey(e.target.value)}
            placeholder="X-Workspace-Key (optional)"
            style={{
              padding: "5px 10px",
              background: "#0b1220",
              border: "1px solid #1e293b",
              borderRadius: "4px",
              color: "#cbd5e1",
              fontSize: "0.78rem",
              width: "220px",
            }}
            disabled={busy}
          />
        </div>
      </form>

      {error && (
        <div
          role="alert"
          style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid #ef4444",
            borderRadius: "8px",
            padding: "12px 16px",
            color: "#fca5a5",
            fontSize: "0.85rem",
            display: "flex",
            gap: "10px",
            marginTop: "20px",
            alignItems: "center",
          }}
        >
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {totalFound !== null && (
        <div style={{ marginTop: "24px" }}>
          <div style={{ display: "flex", gap: "12px", borderBottom: "1px solid #1e293b", paddingBottom: "10px", marginBottom: "16px" }}>
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              style={{
                background: "none",
                border: "none",
                color: activeTab === "all" ? "#818cf8" : "#94a3b8",
                fontWeight: activeTab === "all" ? 600 : 400,
                cursor: "pointer",
                fontSize: "0.88rem",
                paddingBottom: "4px",
                borderBottom: activeTab === "all" ? "2px solid #818cf8" : "none",
              }}
            >
              All Findings ({totalFound} complaints)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("complaints")}
              style={{
                background: "none",
                border: "none",
                color: activeTab === "complaints" ? "#818cf8" : "#94a3b8",
                fontWeight: activeTab === "complaints" ? 600 : 400,
                cursor: "pointer",
                fontSize: "0.88rem",
                paddingBottom: "4px",
                borderBottom: activeTab === "complaints" ? "2px solid #818cf8" : "none",
              }}
            >
              Database Evidence
            </button>
            {knowledgeResult && (
              <button
                type="button"
                onClick={() => setActiveTab("policy")}
                style={{
                  background: "none",
                  border: "none",
                  color: activeTab === "policy" ? "#818cf8" : "#94a3b8",
                  fontWeight: activeTab === "policy" ? 600 : 400,
                  cursor: "pointer",
                  fontSize: "0.88rem",
                  paddingBottom: "4px",
                  borderBottom: activeTab === "policy" ? "2px solid #818cf8" : "none",
                }}
              >
                Grounded Policy Evidence
              </button>
            )}
          </div>

          {(activeTab === "all" || activeTab === "complaints") && (
            <div style={{ marginBottom: "24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                <Database size={16} className="text-indigo-400" />
                <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#f1f5f9" }}>
                  Operational Complaint Records ({totalFound} total matching)
                </h3>
              </div>

              {matchedComplaints.length === 0 ? (
                <p className="empty-state">No complaints matching "{topic}" in stored records.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>COMPLAINT</th>
                        <th>CATEGORY</th>
                        <th>CHANNEL</th>
                        <th>STATUS</th>
                        <th>PRIORITY</th>
                        <th>AI TRIAGE STATUS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {matchedComplaints.map((c) => (
                        <tr key={c.complaint_id}>
                          <td>
                            <div className="complaint-title">{c.title}</div>
                            <div className="complaint-id">{c.complaint_id}</div>
                          </td>
                          <td>{c.category}</td>
                          <td>{c.channel}</td>
                          <td>
                            <span
                              style={{
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                background: c.status === "resolved" ? "rgba(34, 197, 94, 0.15)" : "rgba(234, 179, 8, 0.15)",
                                color: c.status === "resolved" ? "#86efac" : "#fde047",
                              }}
                            >
                              {c.status}
                            </span>
                          </td>
                          <td>{c.priority}</td>
                          <td>
                            {c.analysis?.status === "completed" ? (
                              <span style={{ color: "#86efac", fontSize: "0.8rem" }}>
                                {c.analysis.category} ({c.analysis.priority})
                              </span>
                            ) : c.analysis?.status === "failed" ? (
                              <span style={{ color: "#fca5a5", fontSize: "0.8rem" }}>Failed ({c.analysis.error_code})</span>
                            ) : (
                              <span style={{ color: "#64748b", fontSize: "0.8rem" }}>Not analyzed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {(activeTab === "all" || activeTab === "policy") && knowledgeResult && (
            <div
              style={{
                background: "rgba(15, 23, 42, 0.6)",
                border: "1px solid #1e293b",
                borderRadius: "10px",
                padding: "20px",
                marginBottom: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <BookOpen size={17} className="text-indigo-400" />
                <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#f1f5f9" }}>
                  Grounded Policy Interpretation · RAG
                </h3>
                <span style={{ fontSize: "0.72rem", background: "#1e293b", color: "#94a3b8", padding: "2px 6px", borderRadius: "4px" }}>
                  Unverified AI Interpretation
                </span>
              </div>

              <p style={{ fontSize: "0.9rem", color: "#cbd5e1", lineHeight: 1.6, marginBottom: "16px" }}>
                {knowledgeResult.message}
              </p>

              {knowledgeResult.claims.length > 0 && (
                <div style={{ marginBottom: "16px" }}>
                  <h4 style={{ fontSize: "0.85rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>
                    Verified Document Claims
                  </h4>
                  <ul style={{ listStyle: "disc", paddingLeft: "20px", color: "#e2e8f0", fontSize: "0.85rem" }}>
                    {knowledgeResult.claims.map((claim, idx) => (
                      <li key={idx} style={{ marginBottom: "6px" }}>
                        {claim.explanation}{" "}
                        <span style={{ color: "#818cf8", fontWeight: 600 }}>[{claim.citation_id}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {knowledgeResult.sources.length > 0 && (
                <div>
                  <h4 style={{ fontSize: "0.85rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>
                    Source Passages & Quotations
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {knowledgeResult.sources.map((src) => (
                      <blockquote
                        key={src.citation_id}
                        style={{
                          background: "#080d1a",
                          borderLeft: "3px solid #818cf8",
                          padding: "10px 14px",
                          borderRadius: "0 6px 6px 0",
                          fontSize: "0.82rem",
                          color: "#94a3b8",
                          margin: 0,
                        }}
                      >
                        <p style={{ margin: 0, color: "#d1d5db" }}>"{src.passage}"</p>
                        <cite style={{ display: "block", marginTop: "4px", fontSize: "0.75rem", color: "#64748b" }}>
                          [{src.citation_id}] {src.name} {src.page_number ? `· Page ${src.page_number}` : ""} · Chunk {src.chunk_index + 1}
                        </cite>
                      </blockquote>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {workspaceKey && !knowledgeResult && !busy && (
            <p className="mt-2 text-slate-400" style={{ fontSize: "0.8rem" }}>
              Note: No knowledge documents matched this query in the provided workspace.
            </p>
          )}
        </div>
      )}

      {totalFound === null && !busy && (
        <div style={{ textAlign: "center", padding: "40px 20px", color: "#64748b" }}>
          <Search size={32} style={{ margin: "0 auto 12px", opacity: 0.5 }} />
          <p style={{ fontSize: "0.95rem", color: "#94a3b8", margin: 0 }}>
            Type a topic above to query stored customer complaints and cross-examine with grounded policies.
          </p>
        </div>
      )}
    </section>
  );
}
