import { useState } from "react";

/** This real health request is independent of the dashboard's mock figures. */
export function HealthStatus() {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  async function checkHealth() {
    setStatus("loading");
    try {
      const response = await fetch("/api/health", {
        signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error("API request failed");
      const body = await response.json();
      if (body.status !== "ok") throw new Error("Unexpected health response");
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }
  return (
    <section
      className="panel mt-4 flex flex-wrap items-center justify-between gap-3"
      aria-label="API health"
    >
      <p role="status" className="text-sm text-slate-300">
        {status === "idle" && "Backend connection has not been checked."}
        {status === "loading" && "Checking backend connection…"}
        {status === "ready" &&
          "API is responding. Database readiness is checked when dashboard data loads."}
        {status === "error" &&
          "Cannot reach the API. Start the backend on port 8000, then retry."}
      </p>
      <button
        className="export-button"
        disabled={status === "loading"}
        onClick={checkHealth}
      >
        {status === "error" ? "Retry connection" : "Check API health"}
      </button>
    </section>
  );
}
