import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnalysisResult } from "./AnalysisResult";

describe("analysis results", () => {
  it("shows an honest unanalysed state", () => {
    render(<AnalysisResult analysis={null} />);
    expect(screen.getByText("Not analyzed")).toBeInTheDocument();
  });
  it("labels AI output and rule priority as unverified suggestions", () => {
    render(<AnalysisResult analysis={{
      status: "completed", category: "Refund Issue", sentiment: "Negative",
      priority: "medium", error_code: null, human_verified: false,
      details: { priority_rule: "negative_sentiment" },
    }} />);
    expect(screen.getByText("AI suggestion · Unverified")).toBeInTheDocument();
    expect(screen.getByText("Refund Issue · Negative")).toBeInTheDocument();
    expect(screen.getByText("Suggested priority: medium")).toBeInTheDocument();
  });
  it("shows failed attempts without fabricated results", () => {
    render(<AnalysisResult analysis={{
      status: "failed", category: null, sentiment: null, priority: null,
      error_code: "rate_limited", human_verified: false, details: {},
    }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Analysis failed: rate limited");
  });
});
