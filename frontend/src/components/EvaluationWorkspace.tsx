import { useEffect, useRef, useState, type FormEvent } from 'react';
import * as api from '../api/evaluation';
import { EvaluationCaseForm } from './EvaluationCaseForm';
import { ComparisonResults, EvaluationResults, EvaluationSummary, readable } from './EvaluationResults';

const emptyFilters = { dataset: '', model: '', status: '', start: '', end: '' };
function query(filters: typeof emptyFilters) {
  return new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString();
}

export function EvaluationWorkspace() {
  const [enteredKey, setEnteredKey] = useState('');
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [consent, setConsent] = useState(false);
  const [useJudge, setUseJudge] = useState(false);
  const [pairwise, setPairwise] = useState(false);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [filters, setFilters] = useState(emptyFilters);
  const [cases, setCases] = useState<api.EvalCase[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<api.Summary | null>(null);
  const [selected, setSelected] = useState<api.EvalCase | null>(null);
  const [evaluation, setEvaluation] = useState<api.Evaluation | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [comparison, setComparison] = useState<api.Comparison | null>(null);
  const [comparisons, setComparisons] = useState<api.Comparison[]>([]);
  const [template, setTemplate] = useState<api.EvalCase | null>(null);
  const [formVersion, setFormVersion] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<api.ImportResult | null>(null);
  const [reviewKey, setReviewKey] = useState('');
  const [decision, setDecision] = useState('approve');
  const [feedback, setFeedback] = useState('');
  const [corrections, setCorrections] = useState('{}');
  const version = useRef(0);
  useEffect(() => () => { version.current++; }, []);

  async function refresh(accessKey = key, nextFilters = filters, nextOffset = offset) {
    const current = version.current;
    const [page, data, history] = await Promise.all([
      api.listCases(accessKey, `${query(nextFilters)}&offset=${nextOffset}&limit=30`),
      api.summary(accessKey, query(nextFilters)), api.comparisons(accessKey),
    ]);
    if (current !== version.current) return;
    setCases(page.items); setTotal(page.total); setSummary(data); setComparisons(history.items);
    setFilters(nextFilters); setOffset(nextOffset);
  }

  async function action(label: string, work: () => Promise<void>) {
    const current = version.current; setBusy(label); setError(''); setNotice('');
    try { await work(); }
    catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Request failed.'); }
    finally { if (current === version.current) setBusy(''); }
  }

  async function connect(event: FormEvent) {
    event.preventDefault(); const current = ++version.current;
    await action('Connecting…', async () => {
      await refresh(enteredKey, emptyFilters, 0);
      if (current === version.current) { setKey(enteredKey); setEnteredKey(''); }
    });
  }

  function disconnect() {
    version.current++; setKey(''); setEnteredKey(''); setReviewKey(''); setSelected(null); setEvaluation(null);
    setCases([]); setSummary(null); setComparison(null); setComparisons([]); setChosen([]); setTemplate(null);
    setError(''); setNotice(''); setBusy(''); setConsent(false); setUseJudge(false); setPairwise(false);
    setFeedback(''); setCorrections('{}'); setImportResult(null); setFile(null); setDraftFilters(emptyFilters); setFilters(emptyFilters);
  }

  async function selectCase(item: api.EvalCase) {
    const current = version.current;
    await action('Loading case history…', async () => {
      const detail = await api.caseDetail(key, item.id);
      if (current === version.current) { setSelected(detail); setEvaluation(detail.evaluations?.[0] ?? null); setFeedback(''); setCorrections('{}'); }
    });
  }

  async function save(value: unknown) {
    const current = version.current;
    setBusy('Saving case…'); setError(''); setNotice('');
    try {
      const saved = await api.createCase(key, value);
      if (current !== version.current) return;
      setNotice(saved.duplicate ? 'This identical case already exists.' : 'Evaluation case saved.');
      setSelected(saved.case); setEvaluation(null); await refresh();
    } finally { if (current === version.current) setBusy(''); }
  }

  async function evaluate() {
    if (!selected) return; const current = version.current;
    await action('Evaluating supplied response…', async () => {
      const result = await api.evaluateCase(key, selected.id, useJudge, consent);
      if (current !== version.current) return;
      setEvaluation(result);
      const detail = await api.caseDetail(key, selected.id);
      if (current !== version.current) return;
      setSelected(detail); await refresh();
    });
  }

  async function download(format: 'csv' | 'json') {
    const current = version.current;
    await action('Preparing export…', async () => {
      const blob = await api.exportResults(key, query(filters), format);
      if (current !== version.current) return;
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `neuroops-evaluations.${format}`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  return <div className="eval-workspace">
    <section className="panel p-6"><h2>Evaluation Workspace</h2>
      <p>Measure supplied responses, compare evidence, and keep human review auditable. LLM judges are fallible.</p>
      {!key ? <form className="kb-form" onSubmit={connect}>
        <label>Workspace access key<input type="password" autoComplete="off" maxLength={512} required value={enteredKey} onChange={event => setEnteredKey(event.target.value)} /></label>
        <button className="export-button" disabled={!!busy}>Connect workspace</button>
      </form> : <button className="export-button" onClick={disconnect}>Disconnect</button>}
    </section>
    {busy && <p role="status">{busy}</p>}
    {error && <div className="notice" role="alert"><p>{error}</p>{key && <button className="export-button" disabled={!!busy} onClick={() => void action('Refreshing…', () => refresh())}>Retry refresh</button>}</div>}
    {notice && <p role="status">{notice}</p>}
    {key && <>
      <section className="panel p-6"><h2>Provider consent</h2>
        <label className="eval-check"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
          I authorize sharing de-identified questions, responses, references, instructions, policy, and selected passages with the configured providers. Calls may incur charges.</label>
        <p>Saving cases and deterministic checks use no paid provider. Judge and evidence-search calls require this consent. Workspace/reviewer keys and case metadata are not sent to the judge.</p>
      </section>
      <section className="panel p-6"><form className="eval-filters" onSubmit={event => {
        event.preventDefault(); void action('Filtering…', async () => { await refresh(key, draftFilters, 0); setChosen([]); });
      }}>
        <label>Filter dataset<input value={draftFilters.dataset} maxLength={80} onChange={event => setDraftFilters({ ...draftFilters, dataset: event.target.value })} /></label>
        <label>Filter model<input value={draftFilters.model} maxLength={120} onChange={event => setDraftFilters({ ...draftFilters, model: event.target.value })} /></label>
        <label>Evaluation status<select value={draftFilters.status} onChange={event => setDraftFilters({ ...draftFilters, status: event.target.value })}>
          <option value="">All statuses</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option>
        </select></label>
        <label>From date (UTC)<input type="date" value={draftFilters.start} onChange={event => setDraftFilters({ ...draftFilters, start: event.target.value })} /></label>
        <label>Through date (UTC)<input type="date" value={draftFilters.end} onChange={event => setDraftFilters({ ...draftFilters, end: event.target.value })} /></label>
        <button className="export-button" disabled={!!busy}>Apply filters</button>
      </form><p>Dates filter evaluation timestamps in metrics/exports and case creation dates in the case list. Case status matches any attempt; the card shows the latest attempt.</p>
        <div className="eval-actions"><button className="export-button" disabled={!!busy} onClick={() => void download('csv')}>Export CSV</button>
          <button className="export-button" disabled={!!busy} onClick={() => void download('json')}>Export JSON</button></div>
      </section>
      {summary && <EvaluationSummary data={summary} />}
      <EvaluationCaseForm key={`${formVersion}:${template?.id ?? 'new'}`} busy={!!busy} consent={consent} template={template} onSave={save} onSearch={async question => {
        const current = version.current; setBusy('Searching evidence…');
        try { const result = await api.searchEvidence(key, question, consent); return current === version.current ? result.sources : []; }
        finally { if (current === version.current) setBusy(''); }
      }} />
      <section className="panel p-6"><h2>Import evaluation CSV</h2>
        <p>UTF-8 · 1 MiB maximum · 500 rows · Required columns: question, response, model. Identical cases are skipped. Invalid rows are reported separately.</p>
        <form className="kb-form" onSubmit={event => {
          event.preventDefault(); if (!file) return; const current = version.current;
          void action('Importing cases…', async () => {
            if (file.size > 1024 * 1024) throw new Error('CSV must be at most 1 MiB.');
            const result = await api.importCases(key, file);
            if (current === version.current) { setImportResult(result); await refresh(); }
          });
        }}><label>Evaluation CSV<input type="file" accept=".csv,text/csv" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
          <button className="export-button" disabled={!file || !!busy}>Import CSV</button></form>
        {importResult && <div role="status"><p>Imported {importResult.inserted}; duplicates {importResult.duplicates}; invalid {importResult.invalid} of {importResult.total_rows} rows.</p>
          <ul>{importResult.errors.map(row => <li key={row.row}>Row {row.row}: {row.message}</li>)}</ul>
          {importResult.errors_truncated && <p>Only the first 50 errors are shown.</p>}</div>}
      </section>
      <section className="panel p-6"><h2>Evaluation cases</h2><p>{total} matching cases. Select two to four comparable responses.</p>
        {!cases.length && <p>No cases match these filters.</p>}
        <ul className="eval-case-list">{cases.map(item => <li key={item.id}>
          <input type="checkbox" aria-label={`Compare ${item.model}: ${item.question}`} checked={chosen.includes(item.id)} disabled={!!busy || (!chosen.includes(item.id) && chosen.length >= 4)} onChange={event =>
            setChosen(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} />
          <button disabled={!!busy} aria-pressed={selected?.id === item.id} onClick={() => void selectCase(item)}>
            <strong>{item.model} · {item.dataset}</strong><span>{item.question}</span>
            <small>{item.latest_evaluation?.status ?? 'Not evaluated'}{item.context.metadata.sample === 'true' ? ' · Sample data' : ''}</small>
          </button></li>)}</ul>
        <div className="eval-actions"><button className="export-button" disabled={!!busy || offset === 0} onClick={() => void action('Loading…', () => refresh(key, filters, Math.max(0, offset - 30)))}>Previous cases</button>
          <span>{total ? `${offset + 1}–${Math.min(offset + 30, total)} of ${total}` : '0 cases'}</span>
          <button className="export-button" disabled={!!busy || offset + 30 >= total} onClick={() => void action('Loading…', () => refresh(key, filters, offset + 30))}>Next cases</button></div>
        <label className="eval-check"><input type="checkbox" checked={pairwise} onChange={event => setPairwise(event.target.checked)} /> Include pairwise LLM preference (exactly two responses; two calls with reversed order)</label>
        <button className="export-button" disabled={!!busy || chosen.length < 2 || (pairwise && (!consent || chosen.length !== 2))} onClick={() => {
          const current = version.current; void action('Comparing responses…', async () => {
            const result = await api.compare(key, chosen, pairwise, consent);
            if (current === version.current) { setComparison(result); await refresh(); }
          });
        }}>Compare selected responses</button>
      </section>
      {selected && <section className="panel p-6" aria-label="Selected evaluation case">
        <h2>{selected.model} · {selected.dataset}</h2><h3>Question</h3><p>{selected.question}</p>
        <h3>Supplied response</h3><pre>{selected.response}</pre><h3>Reference answer</h3><p>{selected.reference ?? 'Not supplied — reference-based correctness is not assessed.'}</p>
        {selected.context.evidence.map(source => <blockquote key={source.chunk_id}><p>{source.passage}</p><cite>{source.name}{source.page_number ? ` · Page ${source.page_number}` : ''}</cite></blockquote>)}
        <details><summary>Stored evaluation context</summary><pre>{JSON.stringify(selected.context, null, 2)}</pre></details>
        <div className="eval-actions"><button className="export-button" disabled={!!busy} onClick={() => { setTemplate(selected); setFormVersion(value => value + 1); setNotice('The case form now shares this question and evaluation context. Enter another model label and response.'); }}>Use question for another model</button>
          <button className="export-button" disabled={!!busy} onClick={() => { setTemplate(null); setFormVersion(value => value + 1); }}>Clear case form</button></div>
        <label className="eval-check"><input type="checkbox" checked={useJudge} onChange={event => setUseJudge(event.target.checked)} /> Include LLM judge</label>
        <button className="export-button" disabled={!!busy || (useJudge && !consent)} onClick={() => void evaluate()}>Run evaluation</button>
        {!!selected.evaluations?.length && <label className="eval-history-select">Evaluation history<select value={evaluation?.id ?? ''} onChange={event => setEvaluation(selected.evaluations?.find(item => item.id === event.target.value) ?? null)}>
          {selected.evaluations.map(item => <option key={item.id} value={item.id}>{new Date(item.created_at * 1000).toLocaleString()} · {item.status} · {item.id.slice(0, 8)}</option>)}
        </select></label>}
        {evaluation && <><EvaluationResults evaluation={evaluation} />
          <form className="kb-form" onSubmit={event => {
            event.preventDefault(); const current = version.current;
            void action('Recording human review…', async () => {
              await api.review(key, reviewKey, evaluation.id, { decision, feedback, corrections: decision === 'correct' ? JSON.parse(corrections) : {} });
              if (current !== version.current) return;
              setReviewKey(''); setFeedback(''); const detail = await api.caseDetail(key, selected.id);
              if (current !== version.current) return;
              setSelected(detail); setEvaluation(detail.evaluations?.find(item => item.id === evaluation.id) ?? null); setNotice('Review appended. Original automated scores are preserved.');
            });
          }}><h3>Human review</h3><p>Reviewer identity comes from the configured reviewer key. Corrections are separate opinions and do not train any model.</p>
            <label>Reviewer key<input type="password" autoComplete="off" maxLength={512} required value={reviewKey} onChange={event => setReviewKey(event.target.value)} /></label>
            <label>Review decision<select value={decision} onChange={event => setDecision(event.target.value)}><option value="approve">Approve</option><option value="reject">Reject</option><option value="correct">Correct</option></select></label>
            <label>Reviewer feedback<textarea value={feedback} minLength={3} maxLength={2000} required onChange={event => setFeedback(event.target.value)} /></label>
            {decision === 'correct' && <label>Corrections JSON<textarea value={corrections} required onChange={event => setCorrections(event.target.value)} /><small>{`Example: {"correctness":{"score":0.75,"reason":"Mostly correct; missed the stated exception."}}. Use null for not assessed.`}</small></label>}
            <button className="export-button" disabled={!!busy}>Save human review</button>
          </form></>}
      </section>}
      {comparisons.length > 0 && <section className="panel p-6"><h2>Recent comparison snapshots</h2><ul>
        {comparisons.map(item => <li key={item.id}><button className="export-button" onClick={() => setComparison(item)}>
          {new Date(item.created_at * 1000).toLocaleString()} · {item.items.map(entry => entry.case.model).join(' / ')} · {readable(item.pairwise.status)}
        </button></li>)}
      </ul></section>}
      {comparison && <ComparisonResults comparison={comparison} />}
    </>}
  </div>;
}
