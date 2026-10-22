import { useState, type FormEvent } from 'react';
import type { EvalCase, Evidence } from '../api/evaluation';

export function EvaluationCaseForm({ busy, consent, template, onSave, onSearch }: {
  busy: boolean; consent: boolean; template: EvalCase | null;
  onSave: (value: unknown) => Promise<void>;
  onSearch: (question: string) => Promise<Evidence[]>;
}) {
  const [dataset, setDataset] = useState(template?.dataset ?? 'default');
  const [model, setModel] = useState('');
  const [provider, setProvider] = useState('supplied');
  const [question, setQuestion] = useState(template?.question ?? '');
  const [response, setResponse] = useState('');
  const [reference, setReference] = useState(template?.reference ?? '');
  const [instructions, setInstructions] = useState(template?.context.instructions ?? '');
  const [policy, setPolicy] = useState(template?.context.policy ?? '');
  const [rules, setRules] = useState(JSON.stringify(template?.context.rules ?? {}, null, 2));
  const [evidenceIds, setEvidenceIds] = useState(template?.context.evidence.map(item => item.chunk_id).join(', ') ?? '');
  const [citations, setCitations] = useState('[]');
  const [metadata, setMetadata] = useState('{}');
  const [sources, setSources] = useState<Evidence[]>([]);
  const [error, setError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    try {
      await onSave({ dataset, model, provider, question, response, reference: reference.trim() || null,
        instructions, policy, rules: JSON.parse(rules), citations: JSON.parse(citations), metadata: JSON.parse(metadata),
        evidence_chunk_ids: evidenceIds.split(',').map(value => value.trim()).filter(Boolean) });
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save case.'); }
  }

  return <section className="panel p-6"><h2>{template ? 'Add another response to the same question' : 'Create evaluation case'}</h2>
    <p>Use supplied, de-identified responses from classification, RAG, agents, or other models. Saving a case makes no provider call.</p>
    <form className="kb-form" onSubmit={submit}>
      <div className="eval-two-columns">
        <label>Dataset<input value={dataset} maxLength={80} required onChange={event => setDataset(event.target.value)} /></label>
        <label>Model label<input value={model} maxLength={120} required onChange={event => setModel(event.target.value)} /></label>
      </div>
      <label>Provider label<input value={provider} maxLength={80} required onChange={event => setProvider(event.target.value)} /></label>
      <label>Question<textarea value={question} minLength={3} maxLength={2000} required onChange={event => setQuestion(event.target.value)} /></label>
      <label>Model response<textarea value={response} maxLength={8000} required onChange={event => setResponse(event.target.value)} /></label>
      <label>Reference answer (optional)<textarea value={reference} maxLength={8000} onChange={event => setReference(event.target.value)} /></label>
      <details><summary>Instructions, policy, evidence, and metadata</summary><div className="kb-form">
        <label>Expected instructions<textarea value={instructions} maxLength={2000} onChange={event => setInstructions(event.target.value)} /></label>
        <label>Applicable policy<textarea value={policy} maxLength={2000} onChange={event => setPolicy(event.target.value)} /></label>
        <label>Rules JSON<textarea value={rules} onChange={event => setRules(event.target.value)} /></label>
        <p>Example: {`{"max_words":100,"required_terms":["refund"],"json_object":false,"require_citations":true}`}</p>
        <label>Expected evidence chunk IDs (comma-separated)<input value={evidenceIds} maxLength={200} onChange={event => setEvidenceIds(event.target.value)} /></label>
        <p>Use up to five IDs from your Knowledge Base or agent results. The server copies actual passages from this workspace.</p>
        <button type="button" className="export-button" disabled={busy || !consent || question.trim().length < 3 || question.length > 1000} onClick={async () => {
          setError(''); try { setSources(await onSearch(question)); } catch (failure) { setError(failure instanceof Error ? failure.message : 'Evidence search failed.'); }
        }}>Search workspace evidence</button>
        {sources.map(source => <blockquote key={source.chunk_id}><p>{source.passage}</p><cite>{source.name}{source.page_number ? ` · Page ${source.page_number}` : ''}</cite>
          <p><code>{source.chunk_id}</code></p><button className="export-button" type="button" onClick={() => {
            const ids = new Set(evidenceIds.split(',').map(value => value.trim()).filter(Boolean)); ids.add(source.chunk_id); setEvidenceIds([...ids].join(', '));
          }}>Select evidence</button></blockquote>)}
        <label>Citations JSON<textarea value={citations} onChange={event => setCitations(event.target.value)} /></label>
        <p>Use response markers [source:CHUNK-ID] and metadata {`[{"chunk_id":"CHUNK-ID","quote":"exact passage excerpt"}]`}. Claim entailment is assessed separately.</p>
        <label>Metadata JSON<textarea value={metadata} onChange={event => setMetadata(event.target.value)} /></label>
        <p>String values only. Label synthetic examples with {`{"sample":"true"}`}. Metadata is not sent to the judge.</p>
      </div></details>
      {error && <p className="kb-error" role="alert">{error}</p>}
      <button className="export-button" disabled={busy}>Save case</button>
    </form>
  </section>;
}
