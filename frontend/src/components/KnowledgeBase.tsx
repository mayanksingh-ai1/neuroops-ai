import { FormEvent, useEffect, useRef, useState } from "react";
import { askKnowledge, listDocuments, uploadDocument, type DocumentPage, type KnowledgeAnswer } from "../api/knowledge";

export function KnowledgeBase() {
  const [enteredKey, setEnteredKey] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [includeAnalytics, setIncludeAnalytics] = useState(false);
  const [result, setResult] = useState<KnowledgeAnswer | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [consent, setConsent] = useState(false);
  const version = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => () => { version.current += 1; }, []);

  async function connect(event: FormEvent) {
    event.preventDefault();
    const current = ++version.current;
    setPage(null); setResult(null); setAccessKey(""); setError(""); setNotice(""); setBusy("Connecting…");
    try {
      const data = await listDocuments(enteredKey);
      if (version.current !== current) return;
      setPage(data); setAccessKey(enteredKey); setEnteredKey(""); setIncludeAnalytics(false);
    } catch (failure) {
      if (version.current === current) setError(failure instanceof Error ? failure.message : "Connection failed.");
    } finally { if (version.current === current) setBusy(""); }
  }

  async function refresh() {
    const current = version.current;
    try {
      const data = await listDocuments(accessKey);
      if (version.current === current) setPage(data);
    } catch (failure) {
      if (version.current === current) setError(failure instanceof Error ? failure.message : "Could not refresh documents.");
    }
  }

  // Poll only while a server-side document is being processed.
  useEffect(() => {
    if (!accessKey || !page?.items.some(document => document.status === "processing")) return;
    const timer = window.setTimeout(() => { void refresh(); }, 3000);
    return () => window.clearTimeout(timer);
  }, [accessKey, page]);

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !consent) return;
    if (!/\.(pdf|txt)$/i.test(file.name)) { setError("Choose a PDF or TXT document."); return; }
    if (file.size > 10 * 1024 * 1024) { setError("Files must be at most 10 MiB; your workspace may have a smaller limit."); return; }
    const current = version.current;
    setError(""); setNotice(""); setBusy("Extracting text and creating embeddings…");
    try {
      const response = await uploadDocument(accessKey, file);
      if (version.current !== current) return;
      setNotice(response.duplicate ? "This document version already exists. Its status is shown below." : "Document processed and ready for questions.");
      setFile(null); if (fileInput.current) fileInput.current.value = "";
    } catch (failure) {
      if (version.current === current) setError(failure instanceof Error ? failure.message : "Upload failed.");
    } finally {
      if (version.current === current) {
        await refresh();
        if (version.current === current) setBusy("");
      }
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const current = version.current;
    setBusy("Retrieving evidence and preparing an answer…"); setError(""); setResult(null);
    try {
      const response = await askKnowledge(accessKey, question.trim(), includeAnalytics);
      if (version.current === current) setResult(response);
    } catch (failure) {
      if (version.current === current) setError(failure instanceof Error ? failure.message : "Question failed.");
    } finally { if (version.current === current) setBusy(""); }
  }

  function disconnect() {
    version.current += 1;
    setAccessKey(""); setPage(null); setResult(null); setQuestion(""); setEnteredKey("");
    setFile(null); setError(""); setNotice(""); setBusy(""); setConsent(false);
  }

  return <section className="kb-page" aria-label="Knowledge Base">
    <div className="panel kb-panel">
      <h2>Company knowledge base</h2>
      <p>Ask questions about company documents and check the quoted evidence behind each answer.</p>
      {!accessKey ? <form onSubmit={connect} className="kb-form">
        <label>Workspace access key<input type="password" autoComplete="off" required minLength={32}
          value={enteredKey} onChange={event => setEnteredKey(event.target.value)} /></label>
        <small>Use the workspace key supplied by your administrator. It is held in memory for this page session.</small>
        <button className="export-button" disabled={!!busy}>Connect workspace</button>
      </form> : <div className="kb-toolbar">
        <span>Connected workspace: <strong>{page?.workspace}</strong></span>
        <button className="export-button" onClick={disconnect}>Disconnect</button>
      </div>}
    </div>
    {busy && <div className="panel kb-panel" role="status">{busy}</div>}
    {error && <div className="panel kb-panel kb-error" role="alert">{error}</div>}
    {notice && <div className="panel kb-panel" role="status">{notice}</div>}
    {accessKey && <>
      <div className="kb-grid">
        <section className="panel kb-panel">
          <h2>Add company documents</h2>
          <p>PDF with selectable text or UTF-8 TXT. Default limit: 5 MiB. Scanned PDFs need OCR before upload.</p>
          <form onSubmit={upload} className="kb-form">
            <label>Document<input ref={fileInput} type="file" accept=".pdf,.txt,application/pdf,text/plain"
              onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
            <label className="kb-check"><input type="checkbox" checked={consent}
              onChange={event => setConsent(event.target.checked)} />
              I am authorized to upload this document and share its text with the configured AI providers.</label>
            <small>Document text is sent for embeddings. Retrieved passages and your question are sent for answering. Remove unnecessary personal or confidential information first.</small>
            <button className="export-button" disabled={!!busy || !file || !consent}>Upload document</button>
          </form>
        </section>
        <section className="panel kb-panel">
          <div className="kb-toolbar"><h2>Documents</h2><button className="export-button" disabled={!!busy} onClick={() => void refresh()}>Refresh documents</button></div>
          {page?.items.length === 0 ? <p>No documents yet. Upload a company policy or guide to begin.</p> :
            <ul className="kb-documents">{page?.items.map(document => <li key={document.id}>
              <strong>{document.name}</strong><span>{document.status} · {document.chunk_count} chunks</span>
              {document.error_code && <span className="kb-error">{document.error_code.replace(/_/g, " ")} — upload the same file to retry.</span>}
            </li>)}</ul>}
        </section>
      </div>
      <section className="panel kb-panel">
        <h2>Ask your documents</h2>
        <form onSubmit={ask} className="kb-form">
          <label>Question<textarea required minLength={3} maxLength={1000} value={question}
            onChange={event => setQuestion(event.target.value)} placeholder="What does our policy say about damaged deliveries?" /></label>
          {page?.analytics_available && <label className="kb-check"><input type="checkbox" checked={includeAnalytics}
            onChange={event => setIncludeAnalytics(event.target.checked)} /> Include calculated complaint totals and category counts</label>}
          <button className="export-button" disabled={!!busy || !page?.items.some(document => document.status === "ready") || question.trim().length < 3}>Ask question</button>
        </form>
        {result && <article className="kb-answer" aria-label="Knowledge answer">
          <h3>{result.status === "answered" ? "AI-generated explanation" : "Insufficient document evidence"}</h3>
          <p>{result.message}</p>
          {result.claims.map((claim, index) => <p key={index}>{claim.explanation} <a href={`#kb-source-${claim.citation_id}`}>[{claim.citation_id}]</a></p>)}
          {result.sources.length > 0 && <h3>Quoted document evidence</h3>}
          {result.sources.map(source => <figure id={`kb-source-${source.citation_id}`} key={source.citation_id}>
            <figcaption>[{source.citation_id}] {source.name} · {source.page_number ? `Page ${source.page_number}` : "TXT document"} · Chunk {source.chunk_index + 1}</figcaption>
            <blockquote>{source.passage}</blockquote>
          </figure>)}
          {result.calculated_analytics && <section className="kb-calculated" aria-label="Calculated complaint analytics">
            <h3>Calculated complaint analytics</h3><p>{result.calculated_analytics.label}</p>
            <p>Total complaints: {result.calculated_analytics.total}</p>
            <ul>{Object.entries(result.calculated_analytics.status_counts).map(([status, count]) => <li key={status}>{status}: {count}</li>)}</ul>
            <ul>{result.calculated_analytics.top_categories.map(row => <li key={row.category}>{row.category}: {row.count}</li>)}</ul>
          </section>}
        </article>}
      </section>
    </>}
  </section>;
}
