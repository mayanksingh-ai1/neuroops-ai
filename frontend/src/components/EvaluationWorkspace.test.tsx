import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EvaluationWorkspace } from './EvaluationWorkspace';

const empty = { evaluations: 0, distinct_cases: 0, completed: 0, failed: 0, metrics: [], common_failures: [], models: [], label: 'Stored automated attempts.' };
const metric = { score: null, status: 'not_assessed', reason: 'No reference supplied.' };
const evaluation = { id: 'eval-1', case_id: 'case-1', status: 'completed', error_code: null,
  deterministic: { correctness: metric }, judged: { correctness: metric }, rubric: { version: 'eval-v1' },
  evaluator: { provider: 'local' }, reviews: [], created_at: 1700000000, human_verified: false };
const sample = { id: 'case-1', dataset: 'demo', model: 'model-a', provider: 'supplied', question: 'Refund window?',
  response: 'Thirty days.', reference: null, created_at: 1700000000,
  context: { evidence: [], instructions: '', policy: '', rules: {}, citations: [], metadata: { sample: 'true' } },
  latest_evaluation: null, evaluations: [] };
const reply = (data: unknown) => ({ ok: true, json: async () => data });
afterEach(() => vi.unstubAllGlobals());

function setup(items: unknown[] = [], custom?: (url: string, init: RequestInit) => unknown) {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const result = custom?.(url, init);
    if (result !== undefined) return result;
    if (url.includes('/summary')) return reply(empty);
    if (url.includes('/comparisons')) return reply({ items: [] });
    if (url.endsWith('/cases/case-1')) return reply(sample);
    return reply({ items, total: items.length });
  });
  vi.stubGlobal('fetch', fetch);
  render(<EvaluationWorkspace />);
  return fetch;
}

async function connect() {
  fireEvent.change(screen.getByLabelText('Workspace access key'), { target: { value: 'a'.repeat(32) } });
  fireEvent.click(screen.getByRole('button', { name: 'Connect workspace' }));
  await screen.findByText('Measured evaluation activity');
}

describe('Evaluation Workspace', () => {
  it('shows real empty states without sample performance', async () => {
    const fetch = setup(); await connect();
    expect(screen.getByText('No cases match these filters.')).toBeInTheDocument();
    expect(screen.getByText(/No evaluations match these filters/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/cases?'), expect.objectContaining({
      headers: { 'X-Workspace-Key': 'a'.repeat(32) }, cache: 'no-store' }));
  });

  it('creates a supplied case without making judge calls', async () => {
    const fetch = setup([], (url, init) => url.endsWith('/cases') && init.method === 'POST' ? reply({ case: sample, duplicate: false }) : undefined);
    await connect();
    fireEvent.change(screen.getByLabelText('Model label'), { target: { value: 'model-a' } });
    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Refund window?' } });
    fireEvent.change(screen.getByLabelText('Model response'), { target: { value: 'Thirty days.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save case' }));
    await screen.findByText('Evaluation case saved.');
    const call = fetch.mock.calls.find(([url, init]) => url.endsWith('/cases') && init.method === 'POST');
    expect(JSON.parse(call![1].body as string).reference).toBeNull();
    expect(fetch.mock.calls.some(([url]) => url.includes('/evaluate'))).toBe(false);
  });

  it('runs deterministic evaluation and labels missing scores and method', async () => {
    setup([sample], (url, init) => url.endsWith('/evaluate') && init.method === 'POST' ? reply(evaluation) : undefined);
    await connect();
    fireEvent.click(screen.getByRole('button', { name: /model-a · demo/ }));
    await screen.findByRole('region', { name: 'Selected evaluation case' });
    fireEvent.click(screen.getByRole('button', { name: 'Run evaluation' }));
    await screen.findByRole('article', { name: 'Automated evaluation' });
    expect(screen.getByText('Deterministic checks — limited proxies')).toBeInTheDocument();
    expect(screen.getByText('LLM judgments — unverified assessments')).toBeInTheDocument();
    expect(screen.getAllByText('Not assessed')).toHaveLength(2);
    fireEvent.click(screen.getByLabelText('Include LLM judge'));
    expect(screen.getByRole('button', { name: 'Run evaluation' })).toBeDisabled();
  });

  it('shows CSV invalid rows clearly', async () => {
    setup([], url => url.endsWith('/cases/import') ? reply({ total_rows: 2, inserted: 1, duplicates: 0, invalid: 1,
      errors: [{ row: 3, message: 'model: missing' }], errors_truncated: false }) : undefined);
    await connect();
    fireEvent.change(screen.getByLabelText('Evaluation CSV'), { target: { files: [new File(['question,response,model'], 'cases.csv', { type: 'text/csv' })] } });
    fireEvent.click(screen.getByRole('button', { name: 'Import CSV' }));
    expect(await screen.findByText('Row 3: model: missing')).toBeInTheDocument();
    expect(screen.getByText('Imported 1; duplicates 0; invalid 1 of 2 rows.')).toBeInTheDocument();
  });

  it('applies filters to the dashboard and case list', async () => {
    const fetch = setup(); await connect();
    fireEvent.change(screen.getByLabelText('Filter model'), { target: { value: 'model-a' } });
    fireEvent.change(screen.getByLabelText('Filter dataset'), { target: { value: 'demo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/summary?dataset=demo&model=model-a'), expect.anything()));
  });

  it('keeps review feedback separate and sends reviewer key only to review endpoint', async () => {
    let reviewed = false;
    const review = { id: 'review-1', reviewer_id: 'reviewer-1', decision: 'approve', feedback: 'Checked against policy.', corrections: {}, created_at: 1700000001 };
    const fetch = setup([sample], (url) => {
      if (url.endsWith('/reviews')) { reviewed = true; return reply(review); }
      if (url.endsWith('/cases/case-1')) return reply({ ...sample, evaluations: [{ ...evaluation, reviews: reviewed ? [review] : [] }] });
      return undefined;
    });
    await connect(); fireEvent.click(screen.getByRole('button', { name: /model-a · demo/ }));
    await screen.findByRole('article', { name: 'Automated evaluation' });
    fireEvent.change(screen.getByLabelText('Reviewer key'), { target: { value: 'r'.repeat(32) } });
    fireEvent.change(screen.getByLabelText('Reviewer feedback'), { target: { value: 'Checked against policy.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save human review' }));
    await screen.findByText('Review appended. Original automated scores are preserved.');
    expect(screen.getByText('reviewer-1')).toBeInTheDocument();
    expect(screen.getAllByText('Not assessed')).toHaveLength(2);
    const reviewerCalls = fetch.mock.calls.filter(([, init]) => (init.headers as Record<string, string>)['X-Reviewer-Key']);
    expect(reviewerCalls).toHaveLength(1);
    expect(reviewerCalls[0][0]).toContain('/results/eval-1/reviews');
  });

  it('shows authorized connection errors', async () => {
    setup([], () => ({ ok: false, status: 401, json: async () => ({ detail: 'Invalid workspace key.' }) }));
    fireEvent.change(screen.getByLabelText('Workspace access key'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'Connect workspace' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid workspace key.');
  });
});
