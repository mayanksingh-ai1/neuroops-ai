import { useState, useRef, type FormEvent, type ChangeEvent, type DragEvent } from "react";
import { importComplaintsCsv, type ImportResult } from "../api/dashboard";
import { Upload, X, AlertCircle, CheckCircle2, FileText, Loader2 } from "lucide-react";

export function ComplaintImportModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (result: ImportResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [importKey, setImportKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  function handleFileSelect(selected: File | null) {
    setError("");
    setResult(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (selected.size > 2 * 1024 * 1024) {
      setError("File exceeds the 2 MiB limit.");
      setFile(null);
      return;
    }
    if (!selected.name.toLowerCase().endsWith(".csv") && selected.type !== "text/csv") {
      setError("Please select a valid .csv file.");
      setFile(null);
      return;
    }
    setFile(selected);
  }

  function onFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    handleFileSelect(event.target.files?.[0] ?? null);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    handleFileSelect(event.dataTransfer.files?.[0] ?? null);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Please select a CSV file to import.");
      return;
    }
    if (importKey.trim().length < 32) {
      setError("X-Import-Key must be at least 32 characters long.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);

    try {
      const res = await importComplaintsCsv(file, importKey.trim());
      setResult(res);
      onSuccess(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import CSV.");
    } finally {
      setBusy(false);
    }
  }

  function handleReset() {
    setFile(null);
    setError("");
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div className="modal-dialog">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Upload size={20} className="text-indigo-400" />
            <h2 id="import-modal-title">Import Complaints CSV</h2>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            disabled={busy}
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ color: "#94a3b8", fontSize: "0.9rem", lineHeight: 1.5, marginBottom: "16px" }}>
          Upload a validated UTF-8 CSV file up to 2 MiB (max 5,000 rows). Records are verified
          and inserted into PostgreSQL. Existing complaints with matching IDs are preserved.
        </p>

        <form onSubmit={handleSubmit} className="kb-form" style={{ marginTop: 0 }}>
          <label>
            <span>Operator Import Key (<code>X-Import-Key</code>)</span>
            <input
              type="password"
              autoComplete="off"
              required
              minLength={32}
              placeholder="Enter configured 32+ char IMPORT_API_KEY"
              value={importKey}
              onChange={(e) => setImportKey(e.target.value)}
              disabled={busy}
            />
            <small style={{ color: "#64748b" }}>
              Key is held only in memory for this import request.
            </small>
          </label>

          <label>
            <span>Select CSV File</span>
            <div
              className={`drop-zone ${dragOver ? "active" : ""}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                style={{ display: "none" }}
                onChange={onFileInputChange}
                disabled={busy}
              />
              <FileText size={32} style={{ margin: "0 auto 8px", color: file ? "#818cf8" : "#64748b" }} />
              {file ? (
                <div>
                  <strong style={{ color: "#f8fafc", display: "block" }}>{file.name}</strong>
                  <small style={{ color: "#94a3b8" }}>
                    {(file.size / 1024).toFixed(1)} KB · Click or drag to replace
                  </small>
                </div>
              ) : (
                <div>
                  <strong style={{ color: "#cbd5e1", display: "block" }}>
                    Click to browse or drop CSV here
                  </strong>
                  <small style={{ color: "#64748b" }}>
                    Required headers: complaint_id, title, category, status, priority, channel, received_date
                  </small>
                </div>
              )}
            </div>
          </label>

          {busy && (
            <div className="panel" style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: "10px", background: "#0b1120" }}>
              <Loader2 size={18} className="animate-spin text-indigo-400" />
              <span style={{ fontSize: "0.9rem", color: "#cbd5e1" }}>
                Validating CSV rows and storing records in database...
              </span>
            </div>
          )}

          {error && (
            <div className="panel kb-error" role="alert" style={{ padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: "10px" }}>
              <AlertCircle size={18} style={{ flexShrink: 0, marginTop: "2px" }} />
              <span style={{ fontSize: "0.9rem" }}>{error}</span>
            </div>
          )}

          {result && (
            <div className="import-success" role="status">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600 }}>
                <CheckCircle2 size={18} />
                <span>Import Completed Successfully!</span>
              </div>
              <ul style={{ marginTop: "8px", paddingLeft: "20px", fontSize: "0.85rem", lineHeight: 1.6 }}>
                <li><b>{result.inserted}</b> new complaint(s) inserted</li>
                <li><b>{result.duplicates}</b> duplicate(s) skipped</li>
                {result.invalid > 0 && (
                  <li style={{ color: "#fca5a5" }}>
                    <b>{result.invalid}</b> invalid row(s) skipped
                  </li>
                )}
                <li><b>{result.total_rows}</b> total rows processed</li>
              </ul>
              {result.errors.length > 0 && (
                <div style={{ marginTop: "10px" }}>
                  <small style={{ color: "#fca5a5", fontWeight: 600 }}>
                    Row Validation Warnings:
                  </small>
                  <ul className="import-error-list">
                    {result.errors.map((err, idx) => (
                      <li key={idx}>
                        Row {err.row}: {err.message || JSON.stringify(err.fields)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "12px" }}>
            {result ? (
              <button
                type="button"
                className="export-button"
                onClick={onClose}
              >
                Done
              </button>
            ) : (
              <>
                {file && (
                  <button
                    type="button"
                    className="select-button"
                    onClick={handleReset}
                    disabled={busy}
                  >
                    Clear File
                  </button>
                )}
                <button
                  type="button"
                  className="select-button"
                  onClick={onClose}
                  disabled={busy}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="export-button"
                  disabled={busy || !file || importKey.trim().length < 32}
                >
                  {busy ? "Importing..." : "Import CSV"}
                </button>
              </>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
