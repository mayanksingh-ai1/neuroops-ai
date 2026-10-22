import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ComplaintImportModal } from "./ComplaintImportModal";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("does not render dialog when open is false", () => {
  render(
    <ComplaintImportModal
      open={false}
      onClose={() => {}}
      onSuccess={() => {}}
    />
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("renders modal dialog and elements when open is true", () => {
  render(
    <ComplaintImportModal
      open={true}
      onClose={() => {}}
      onSuccess={() => {}}
    />
  );
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Import Complaints CSV" })).toBeInTheDocument();
  expect(screen.getByLabelText(/Operator Import Key/i)).toBeInTheDocument();
  expect(screen.getByText(/Click to browse or drop CSV here/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Import CSV" })).toBeDisabled();
});

it("rejects non-csv files and files exceeding 2 MiB", () => {
  render(
    <ComplaintImportModal
      open={true}
      onClose={() => {}}
      onSuccess={() => {}}
    />
  );
  const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

  // Non-csv file
  const txtFile = new File(["test"], "test.txt", { type: "text/plain" });
  fireEvent.change(fileInput, { target: { files: [txtFile] } });
  expect(screen.getByText("Please select a valid .csv file.")).toBeInTheDocument();

  // File exceeding 2 MiB
  const largeBlob = new Uint8Array(2 * 1024 * 1024 + 10);
  const largeFile = new File([largeBlob], "large.csv", { type: "text/csv" });
  fireEvent.change(fileInput, { target: { files: [largeFile] } });
  expect(screen.getByText("File exceeds the 2 MiB limit.")).toBeInTheDocument();
});

it("submits valid CSV with X-Import-Key header and reports success", async () => {
  const onSuccess = vi.fn();
  const mockResponse = {
    total_rows: 5,
    inserted: 4,
    duplicates: 1,
    invalid: 0,
    errors: [],
    errors_truncated: false,
  };

  const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockResponse,
  });
  vi.stubGlobal("fetch", mockFetch);

  render(
    <ComplaintImportModal
      open={true}
      onClose={() => {}}
      onSuccess={onSuccess}
    />
  );

  const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
  const keyInput = screen.getByLabelText(/Operator Import Key/i);
  const submitButton = screen.getByRole("button", { name: "Import CSV" });

  const testCsv = new File(
    ["complaint_id,title,category,status,priority,channel,received_date\nCMP_1,Late,Shipping,open,low,web,2026-10-18\n"],
    "complaints.csv",
    { type: "text/csv" }
  );

  fireEvent.change(fileInput, { target: { files: [testCsv] } });
  fireEvent.change(keyInput, { target: { value: "a".repeat(32) } });

  expect(submitButton).not.toBeDisabled();
  fireEvent.click(submitButton);

  await screen.findByRole("status");
  expect(screen.getByText("Import Completed Successfully!")).toBeInTheDocument();
  expect(screen.getByText(/new complaint\(s\) inserted/)).toHaveTextContent("4 new complaint(s) inserted");
  expect(screen.getByText(/duplicate\(s\) skipped/)).toHaveTextContent("1 duplicate(s) skipped");
  expect(screen.getByText(/total rows processed/)).toHaveTextContent("5 total rows processed");

  expect(mockFetch).toHaveBeenCalledWith(
    "/api/complaints/import",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({
        "Content-Type": "text/csv",
        "X-Import-Key": "a".repeat(32),
      }),
      body: testCsv,
    })
  );

  expect(onSuccess).toHaveBeenCalledWith(mockResponse);
});

it("displays server error message when import fails", async () => {
  const mockFetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "A valid X-Import-Key header is required." }),
  });
  vi.stubGlobal("fetch", mockFetch);

  render(
    <ComplaintImportModal
      open={true}
      onClose={() => {}}
      onSuccess={() => {}}
    />
  );

  const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
  const keyInput = screen.getByLabelText(/Operator Import Key/i);

  const testCsv = new File(
    ["complaint_id,title,category,status,priority,channel,received_date\n"],
    "complaints.csv",
    { type: "text/csv" }
  );

  fireEvent.change(fileInput, { target: { files: [testCsv] } });
  fireEvent.change(keyInput, { target: { value: "x".repeat(32) } });

  fireEvent.click(screen.getByRole("button", { name: "Import CSV" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("A valid X-Import-Key header is required.");
});
