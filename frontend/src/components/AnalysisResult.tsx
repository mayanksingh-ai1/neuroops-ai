import type { ApiComplaint } from "../api/dashboard";

export function AnalysisResult({ analysis }: { analysis: ApiComplaint["analysis"] }) {
  if (!analysis) return <span className="analysis-result">Not analyzed</span>;
  if (analysis.status === "failed") {
    return <span className="analysis-result" role="status">
      Analysis failed: {analysis.error_code?.replace(/_/g, " ")}
      <small>Operator can retry via the API.</small>
    </span>;
  }
  return <div className="analysis-result">
    <strong>AI suggestion · Unverified</strong>
    <span>{analysis.category} · {analysis.sentiment}</span>
    <span>Suggested priority: {analysis.priority}</span>
    <small>Rule: {analysis.details.priority_rule?.replace(/_/g, " ")} · Completed</small>
  </div>;
}
