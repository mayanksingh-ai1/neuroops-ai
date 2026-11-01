"""Comprehensive end-to-end verification script for NeuroOps AI.
Tests every major module against the running local server.
"""
import json
import urllib.request
import urllib.error
import time

BASE_URL = "http://127.0.0.1:8000"
WORKSPACE_KEY = "company_workspace_key_32_characters_long"
IMPORT_KEY = "dev_local_import_key_32_characters_secret"

results = []

def record(test_name, success, detail=""):
    status = "PASS" if success else "FAIL"
    print(f"[{status}] {test_name}: {detail}")
    results.append((test_name, success, detail))

def http_request(path, method="GET", data=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = headers or {}
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = content
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = content
        return e.code, parsed

def run_tests():
    print("=" * 65)
    print("NeuroOps AI — End-to-End System Verification (All Features)")
    print("=" * 65)

    # 1. Health & Readiness
    code, body = http_request("/api/health")
    record("1.1 Health Check", code == 200 and body.get("status") == "ok", f"Status: {code}")

    code, body = http_request("/api/ready")
    record("1.2 System Readiness", code == 200 and body.get("status") == "ready", f"Status: {code}, Schema: {body.get('schema')}")

    code, body = http_request("/api/metrics")
    record("1.3 System Metrics", code == 200 and "duration_seconds_total" in body, f"Status: {code}")

    # 2. Phase 2: CSV Complaint Ingestion
    sample_csv = f"complaint_id,title,category,status,priority,channel,received_date\nE2E-TEST-{int(time.time())},Delivery delayed parcel late,Delivery Delay,open,medium,web,2026-10-22\n"
    code, body = http_request(
        "/api/complaints/import",
        method="POST",
        data=sample_csv,
        headers={"X-Import-Key": IMPORT_KEY, "Content-Type": "text/csv"}
    )
    inserted = body.get("inserted", 0) if isinstance(body, dict) else 0
    duplicates = body.get("duplicates", 0) if isinstance(body, dict) else 0
    record("2.1 CSV Complaint Ingestion", code == 200 and (inserted >= 1 or duplicates >= 1), f"Inserted: {inserted}, Duplicates: {duplicates}")

    # 2.2 List Complaints
    code, body = http_request("/api/complaints")
    complaints = body.get("items", []) if isinstance(body, dict) else []
    record("2.2 List Complaints", code == 200 and len(complaints) > 0, f"Found {len(complaints)} complaints")
    
    complaint_id = complaints[0]["complaint_id"] if complaints else "E2E-TEST-001"

    # 3. Phase 3: AI Complaint Classification (Mock / Offline Mode)
    code, body = http_request(
        f"/api/complaints/{complaint_id}/classify",
        method="POST",
        headers={"X-Import-Key": IMPORT_KEY}
    )
    category = body.get("category") if isinstance(body, dict) else None
    status = body.get("status") if isinstance(body, dict) else None
    record("3.1 Free Heuristic Complaint Classification", code == 200 and status == "completed", f"Status: {status}, Category: {category}")

    # 3.2 Analytics endpoints
    code, body = http_request("/api/analytics/categories")
    record("3.2 Complaint Analytics Categories", code == 200 and isinstance(body, list), f"Categories: {len(body) if isinstance(body, list) else 0}")

    code, body = http_request("/api/analytics/status")
    record("3.3 Complaint Analytics Status", code == 200 and "counts" in body, f"Total: {body.get('total')}")

    # 4. Phase 4: Knowledge Base Document Ingestion & RAG Retrieval
    with open(r"C:\Users\mayank singh\Desktop\neuroops-ai\neuroops_sample_company_policy.pdf", "rb") as f:
        pdf_bytes = f.read()

    code, body = http_request(
        "/api/knowledge/documents?filename=e2e_verification_policy.pdf",
        method="POST",
        data=pdf_bytes,
        headers={"X-Workspace-Key": WORKSPACE_KEY, "Content-Type": "application/pdf"}
    )
    doc_status = body.get("document", {}).get("status") if isinstance(body, dict) else None
    record("4.1 Knowledge Base PDF Ingestion & Indexing", code == 200 and doc_status in ("ready", "processing"), f"Doc Status: {doc_status}")

    # 4.2 List Knowledge Base Documents
    code, body = http_request("/api/knowledge/documents", headers={"X-Workspace-Key": WORKSPACE_KEY})
    docs = body.get("items", []) if isinstance(body, dict) else []
    record("4.2 List KB Documents", code == 200 and len(docs) > 0, f"Documents indexed: {len(docs)}")

    # 4.3 RAG Question Answering
    code, body = http_request(
        "/api/knowledge/ask",
        method="POST",
        data={"question": "What is the policy for standard product returns?"},
        headers={"X-Workspace-Key": WORKSPACE_KEY}
    )
    rag_status = body.get("status") if isinstance(body, dict) else None
    has_claims = len(body.get("claims", [])) > 0 if isinstance(body, dict) else False
    record("4.3 RAG Question Answering", code == 200 and rag_status == "answered" and has_claims, f"Status: {rag_status}")

    # 5. Phase 5: Autonomous AI Agent
    code, body = http_request(
        "/api/agent/runs",
        method="POST",
        data={"task": "Investigate recurring delivery delays for customer orders", "provider_consent": True},
        headers={"X-Workspace-Key": WORKSPACE_KEY}
    )
    run_id = body.get("id") if isinstance(body, dict) else None
    record("5.1 AI Agent Run Creation", code == 202 and run_id is not None, f"Run ID: {run_id}")

    if run_id:
        final_state = None
        for _ in range(10):
            time.sleep(0.5)
            code, body = http_request(f"/api/agent/runs/{run_id}", headers={"X-Workspace-Key": WORKSPACE_KEY})
            final_state = body.get("status") if isinstance(body, dict) else None
            if final_state in ("completed", "failed"):
                break
        record("5.2 AI Agent Step Execution", code == 200 and final_state == "completed", f"Final State: {final_state}")

    # 6. Phase 6: Quality Evaluation Cases
    case_payload = {
        "dataset": "return-policy-qa",
        "question": "How long do refunds take?",
        "response": "Refunds are initiated within 5-7 business days.",
        "model": "mock-rag-v1"
    }
    code, body = http_request(
        "/api/evaluation/cases",
        method="POST",
        data=case_payload,
        headers={"X-Workspace-Key": WORKSPACE_KEY}
    )
    case_id = body.get("case", {}).get("id") if isinstance(body, dict) else None
    record("6.1 Evaluation Case Creation", code == 201 and case_id is not None, f"Case ID: {case_id}")

    code, body = http_request("/api/evaluation/cases", headers={"X-Workspace-Key": WORKSPACE_KEY})
    cases = body.get("items", []) if isinstance(body, dict) else []
    record("6.2 List Evaluation Cases", code == 200 and len(cases) > 0, f"Cases: {len(cases)}")

    # 7. Phase 7: Security & Fail-Closed Guardrails
    code, _ = http_request("/api/knowledge/documents", headers={"X-Workspace-Key": "invalid_short_key"})
    record("7.1 Security: Reject Invalid Workspace Key", code == 401, f"Denied with HTTP {code}")

    code, _ = http_request("/api/complaints/import", method="POST", data="test", headers={"X-Import-Key": "wrong_key"})
    record("7.2 Security: Reject Invalid Import Key", code == 401, f"Denied with HTTP {code}")

    code, _ = http_request("/api/knowledge/documents?filename=test..pdf/hack", method="POST", data=b"bad", headers={"X-Workspace-Key": WORKSPACE_KEY, "Content-Type": "application/pdf"})
    record("7.3 Security: Reject Traversal / Malformed Filename", code == 422, f"Rejected with HTTP {code}")

    print("=" * 65)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"Summary: {passed}/{total} tests passed ({round(passed/total*100, 1)}%)")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
