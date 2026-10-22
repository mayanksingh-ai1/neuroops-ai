import { useState, type FormEvent } from "react";
import { classifyBatch, classifyComplaint, type ApiComplaint, type ClassifyItemResponse } from "../api/dashboard";
import { Sparkles, X, AlertCircle, CheckCircle2, Loader2, Key } from "lucide-react";

export function ComplaintClassifyModal({
  open,
  onClose,
  complaints,
  selectedComplaintId,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  complaints: ApiComplaint[];
  selectedComplaintId?: string | null;
  onSuccess: () => void;
}) {
  const [operatorKey, setOperatorKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [progressMsg, setProgressMsg] = useState("");
  const [error, setError] = useState("");
  const [results, setResults] = useState<ClassifyItemResponse[] | null>(null);
  const [targetScope, setTargetScope] = useState<"unanalyzed" | "all">("unanalyzed");

  if (!open) return null;

  const unanalyzedComplaints = complaints.filter(
    (c) => !c.analysis || c.analysis.status === "failed"
  );

  const targetComplaints = selectedComplaintId
    ? complaints.filter((c) => c.complaint_id === selectedComplaintId)
    : targetScope === "unanalyzed"
      ? unanalyzedComplaints
      : complaints;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (operatorKey.trim().length < 32) {
      setError("Operator key (X-Import-Key) must be at least 32 characters long.");
      return;
    }
    if (targetComplaints.length === 0) {
      setError("No matching complaints to classify.");
      return;
    }

    setBusy(true);
    setError("");
    setResults(null);
    setProgressMsg(`Starting classification for ${targetComplaints.length} complaint(s)...`);

    try {
      if (selectedComplaintId) {
        setProgressMsg(`Classifying complaint ${selectedComplaintId}...`);
        const item = await classifyComplaint(selectedComplaintId, operatorKey.trim());
        setResults([item]);
      } else {
        const ids = targetComplaints.map((c) => c.complaint_id);
        setProgressMsg(`Classifying batch of ${ids.length} complaint(s)...`);
        const batchResult = await classifyBatch(ids, operatorKey.trim());
        setResults(batchResult.items);
      }
      onSuccess();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Classification failed.";
      if (msg.includes("missing_api_key") || msg.includes("503")) {
        setError(
          "LLM provider is not configured (missing_api_key). Set OPENAI_API_KEY & LLM_MODEL in backend/.env, or set MOCK_LLM_PROVIDER=true for safe offline testing."
        );
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
      setProgressMsg("");
    }
  }

  const successCount = results?.filter((r) => r.status === "completed").length ?? 0;
  const failedCount = results?.filter((r) => r.status === "failed").length ?? 0;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="classify-modal-title"
    >
      <div className="modal-dialog">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Sparkles size={20} className="text-indigo-400" />
            <h2 id="classify-modal-title">
              {selectedComplaintId ? `Classify Complaint ${selectedComplaintId}` : "Run AI Classification"}
            </h2>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={busy}
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <p className="text-slate-300" style={{ fontSize: "0.88rem", marginBottom: "14px" }}>
              Runs privacy-filtered classification and rule-based priority assessment on complaints.
              Requires an authorized Operator key.
            </p>

            {!selectedComplaintId && (
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "8px" }}>
                  Complaints to classify:
                </label>
                <div style={{ display: "flex", gap: "12px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", color: "#e2e8f0", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="scope"
                      value="unanalyzed"
                      checked={targetScope === "unanalyzed"}
                      onChange={() => setTargetScope("unanalyzed")}
                      disabled={busy}
                    />
                    Unanalyzed / Failed only ({unanalyzedComplaints.length})
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", color: "#e2e8f0", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="scope"
                      value="all"
                      checked={targetScope === "all"}
                      onChange={() => setTargetScope("all")}
                      disabled={busy}
                    />
                    All visible ({complaints.length})
                  </label>
                </div>
              </div>
            )}

            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="operator-key-input"
                style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}
              >
                <Key size={14} style={{ display: "inline", marginRight: "4px" }} />
                Operator Key (X-Import-Key) *
              </label>
              <input
                id="operator-key-input"
                type="password"
                value={operatorKey}
                onChange={(e) => setOperatorKey(e.target.value)}
                placeholder="Enter at least 32 characters"
                disabled={busy}
                required
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  background: "#080d1a",
                  border: "1px solid #273249",
                  borderRadius: "6px",
                  color: "#f1f5f9",
                  fontSize: "0.85rem",
                  outline: "none",
                }}
              />
              <span style={{ fontSize: "0.75rem", color: "#64748b", display: "block", marginTop: "4px" }}>
                Matches IMPORT_API_KEY configured in backend/.env.
              </span>
            </div>

            <div
              style={{
                background: "rgba(30, 41, 59, 0.5)",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "10px 14px",
                fontSize: "0.78rem",
                color: "#94a3b8",
                marginBottom: "16px",
              }}
            >
              <strong style={{ color: "#cbd5e1", display: "block", marginBottom: "4px" }}>
                LLM Provider Notice:
              </strong>
              Requires <code>OPENAI_API_KEY</code> and <code>LLM_MODEL</code> in <code>backend/.env</code>.
              For local verification without paid API charges, set <code>MOCK_LLM_PROVIDER=true</code> in <code>backend/.env</code>.
            </div>

            {error && (
              <div
                role="alert"
                style={{
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "1px solid #ef4444",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  color: "#fca5a5",
                  fontSize: "0.85rem",
                  display: "flex",
                  gap: "8px",
                  alignItems: "flex-start",
                  marginBottom: "16px",
                }}
              >
                <AlertCircle size={17} style={{ flexShrink: 0, marginTop: "2px" }} />
                <div>
                  <strong>Classification Failed</strong>
                  <div style={{ marginTop: "2px" }}>{error}</div>
                </div>
              </div>
            )}

            {results && (
              <div
                style={{
                  background: failedCount === 0 ? "rgba(34, 197, 94, 0.1)" : "rgba(234, 179, 8, 0.1)",
                  border: `1px solid ${failedCount === 0 ? "#16a34a" : "#ca8a04"}`,
                  borderRadius: "8px",
                  padding: "12px 14px",
                  color: failedCount === 0 ? "#86efac" : "#fde047",
                  fontSize: "0.85rem",
                  marginBottom: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600 }}>
                  <CheckCircle2 size={16} />
                  <span>
                    Batch Finished: {successCount} completed, {failedCount} failed
                  </span>
                </div>
                {failedCount > 0 && (
                  <div style={{ marginTop: "8px", fontSize: "0.8rem", color: "#fca5a5" }}>
                    Some complaints failed (e.g. {results.find((r) => r.status === "failed")?.error_code}).
                  </div>
                )}
              </div>
            )}

            {busy && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  color: "#818cf8",
                  fontSize: "0.85rem",
                  marginBottom: "16px",
                }}
              >
                <Loader2 size={16} className="animate-spin" />
                <span>{progressMsg}</span>
              </div>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
            <button
              type="button"
              className="export-button"
              onClick={onClose}
              disabled={busy}
            >
              {results ? "Close" : "Cancel"}
            </button>
            <button
              type="submit"
              className="export-button"
              style={{
                background: "#4f46e5",
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
              disabled={busy || targetComplaints.length === 0}
            >
              {busy ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Classifying...
                </>
              ) : (
                <>
                  <Sparkles size={15} /> Start Classification
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
