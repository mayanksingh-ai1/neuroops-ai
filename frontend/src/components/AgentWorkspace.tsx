import { useEffect, useRef, useState, type FormEvent } from 'react';
import { listRuns, createRun, getRun, cancelRun, type AgentRun, type AgentReport } from '../api/agent';

const active = (run: AgentRun | null) => !!run && ['queued', 'running'].includes(run.status);
const label = (value: string) => value.replace(/_/g, ' ');

function Report({ report }: { report: AgentReport }) {
  const facts = report.database_facts;
  const findings = report.document_findings;
  return <section className="panel p-6 agent-report" aria-label="Investigation report">
    <h2>Investigation report · {label(report.status)}</h2>
    <p className="kb-muted">AI-assisted investigation · Not human verified</p>
    {facts && <section><h3>Calculated database facts</h3><p>{facts.label}</p>
      <p>{facts.scope} · Snapshot {new Date(facts.as_of).toLocaleString()}</p>
      <p><strong>{facts.total}</strong> total complaints</p>
      <div className="agent-facts">{Object.entries(facts.counts).map(([status, count]) =>
        <span key={status}>{label(status)}: <strong>{count}</strong></span>)}</div>
      <h4>Original complaint categories</h4><ul>{facts.categories.map(row => <li key={row.name}>{row.name}: {row.count}</li>)}</ul>
      <details><summary>Daily trend · last {facts.trend_days} days</summary><div className="agent-scroll">
        <table><thead><tr><th>Date</th><th>Complaints</th></tr></thead><tbody>{facts.trends.map(row =>
          <tr key={row.day}><td>{row.day}</td><td>{row.complaints}</td></tr>)}</tbody></table>
      </div></details>
    </section>}
    {findings && <section><h3>AI-generated document interpretations</h3><p>{findings.message}</p>
      {findings.claims.map((claim, index) => <p key={index}>{claim.explanation} <a href={`#agent-source-${claim.citation_id}`}>[{claim.citation_id}]</a></p>)}
      <h3>Quoted document evidence</h3>
      {findings.sources.map(source => <blockquote id={`agent-source-${source.citation_id}`} key={source.citation_id}>
        <p>{source.passage}</p><cite>[{source.citation_id}] {source.name}{source.page_number ? ` · Page ${source.page_number}` : ''} · Chunk {source.chunk_index + 1}</cite>
      </blockquote>)}
    </section>}
    <section><h3>Review and limitations</h3><p>{report.review_next_step}</p>
      <ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul>
    </section>
  </section>;
}

export function AgentWorkspace() {
  const [enteredKey, setEnteredKey] = useState('');
  const [key, setKey] = useState('');
  const [task, setTask] = useState('');
  const [consent, setConsent] = useState(false);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const version = useRef(0);
  const selection = useRef(0);
  useEffect(() => () => { version.current++; selection.current++; }, []);

  function update(next: AgentRun) {
    setRun(next);
    setRuns(previous => [next, ...previous.filter(item => item.id !== next.id)].slice(0, 20));
  }

  async function connect(event: FormEvent) {
    event.preventDefault(); const current = ++version.current;
    setBusy('Connecting…'); setError('');
    try {
      const data = await listRuns(enteredKey);
      if (current !== version.current) return;
      setKey(enteredKey); setEnteredKey(''); setRuns(data.items); setRun(data.items[0] ?? null);
    } catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Connection failed.'); }
    finally { if (current === version.current) setBusy(''); }
  }

  async function refresh(id: string) {
    const current = version.current, selected = ++selection.current;
    try {
      const next = await getRun(key, id);
      if (current === version.current && selected === selection.current) { update(next); setError(''); }
    } catch (failure) {
      if (current === version.current && selected === selection.current) setError(failure instanceof Error ? failure.message : 'Status refresh failed.');
    }
  }

  useEffect(() => {
    if (!key || !active(run) || error) return;
    const timer = window.setTimeout(() => { if (run) void refresh(run.id); }, 1500);
    return () => window.clearTimeout(timer);
  }, [key, run, error]);

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!consent) return;
    const current = version.current; selection.current++;
    setBusy('Submitting investigation…'); setError('');
    try {
      const next = await createRun(key, task);
      if (current === version.current) update(next);
    } catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Could not create run. Refresh history before resubmitting.'); }
    finally { if (current === version.current) setBusy(''); }
  }

  async function cancel() {
    if (!run) return;
    const current = version.current; selection.current++;
    setBusy('Cancelling…'); setError('');
    try { const next = await cancelRun(key, run.id); if (current === version.current) update(next); }
    catch (failure) { if (current === version.current) setError(failure instanceof Error ? failure.message : 'Cancellation failed.'); }
    finally { if (current === version.current) setBusy(''); }
  }

  return <div className="agent-workspace">
    <section className="panel p-6"><h2>Agent Workspace</h2>
      <p className="kb-muted">A bounded investigation using complaint aggregates and your company knowledge base.</p>
      <p>Read-only tools · Up to four steps · Evidence retained for review</p>
      {!key ? <form onSubmit={connect} className="kb-form">
        <label htmlFor="agent-key">Workspace access key</label>
        <input id="agent-key" type="password" value={enteredKey} onChange={event => setEnteredKey(event.target.value)} required autoComplete="off" maxLength={512} />
        <button className="export-button" disabled={!!busy}>Connect workspace</button>
      </form> : <><button className="export-button" onClick={() => {
        version.current++; selection.current++; setKey(''); setEnteredKey(''); setRuns([]); setRun(null); setError(''); setBusy(''); setTask(''); setConsent(false);
      }}>Disconnect</button><p className="kb-muted">The key stays in memory. Disconnecting does not cancel a running investigation.</p></>}
    </section>
    {busy && <p role="status">{busy}</p>}
    {error && <div className="notice" role="alert"><p>{error}</p>{run && <button className="export-button" onClick={() => void refresh(run.id)}>Retry status</button>}</div>}
    {key && <>
      <section className="panel p-6"><form onSubmit={submit} className="kb-form">
        <label htmlFor="agent-task">Investigation task</label>
        <textarea id="agent-task" rows={4} minLength={3} maxLength={1000} required value={task} onChange={event => setTask(event.target.value)}
          placeholder="Summarize overall complaint categories and the last 30 days of trends, then find our refund policy." />
        <p className="kb-muted">Use general business questions. Do not include customer names, order IDs, or personal information. Individual customer investigations and filtered statistics are not supported.</p>
        <label><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /> I approve sending this task and relevant document passages to the configured AI providers. Provider usage may incur charges.</label>
        <button className="export-button" disabled={!consent || task.trim().length < 3 || !!busy || active(run)}>Start investigation</button>
      </form></section>
      <div className="agent-columns"><section className="panel p-6"><h2>Recent investigations</h2>
        {!runs.length && <p>No investigations yet. Submit a task to begin.</p>}
        <ul className="agent-history">{runs.map(item => <li key={item.id}><button disabled={!!busy} aria-pressed={run?.id === item.id} onClick={() => { setRun(item); void refresh(item.id); }}>
          <strong>{item.task}</strong><span>{label(item.status)} · {new Date(item.created_at * 1000).toLocaleString()}</span>
        </button></li>)}</ul>
      </section><section className="panel p-6" aria-label="Execution timeline"><h2>Execution timeline</h2>
        {!run ? <p>Select an investigation to view its steps.</p> : <>
          <p role="status">Run {label(run.status)}</p>
          {active(run) && <button className="export-button" onClick={() => void cancel()} disabled={!!busy}>Cancel investigation</button>}
          {run.error_code && <p role="alert">{label(run.error_code)}. Review the steps below. A new run requires a new submission.</p>}
          <ol className="agent-timeline">{run.steps.map(step => <li key={step.position}>
            <h3>{step.position + 1}. {label(step.tool)}</h3><p>{label(step.status)} · Attempts: {step.attempts}</p>
            {step.error_code && <p>{label(step.error_code)}</p>}
            <details><summary>Arguments and tool result</summary><pre>{JSON.stringify({ arguments: step.arguments, output: step.output }, null, 2)}</pre></details>
          </li>)}</ol>
          {run.status === 'cancelled' && <p>Further steps are stopped. An in-flight provider request may finish, but its output will be discarded.</p>}
        </>}
      </section></div>
      {run?.result && <Report report={run.result} />}
    </>}
  </div>;
}
