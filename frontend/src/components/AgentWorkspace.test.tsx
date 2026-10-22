import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AgentWorkspace } from './AgentWorkspace';

const run = { id: 'run-1', task: 'Investigate refund policy', status: 'completed', created_at: 1700000000,
  expires_at: 1700000090, error_code: null,
  steps: [{ position: 0, tool: 'planning', arguments: {}, status: 'completed', attempts: 1, output: {}, error_code: null }],
  result: { status: 'completed', human_verified: false, database_facts: {
    label: 'Calculated original complaints', scope: 'Installation workspace', total: 7, counts: { open: 7 },
    categories: [{ name: 'Refund', count: 7 }], trends: [{ day: '2026-10-21', complaints: 7 }], trend_days: 30, as_of: '2026-10-21T00:00:00Z',
  }, document_findings: { status: 'answered', message: 'Verify this explanation.',
    claims: [{ explanation: 'Review the refund window.', citation_id: '1' }],
    sources: [{ citation_id: '1', name: 'Policy.txt', page_number: 2, chunk_index: 0, passage: 'Refund requests must arrive within thirty days.' }],
  }, recommendations: [], review_next_step: 'Human review required.', limitations: ['No actions were performed.'] },
};
const reply = (value: unknown) => ({ ok: true, json: async () => value });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

async function connect() {
  fireEvent.change(screen.getByLabelText('Workspace access key'), { target: { value: 'a'.repeat(32) } });
  fireEvent.click(screen.getByRole('button', { name: 'Connect workspace' }));
  await screen.findByLabelText('Investigation task');
}

describe('Agent Workspace', () => {
  it('shows an empty workspace and gates provider calls on consent', async () => {
    const fetch = vi.fn(async () => reply({ items: [] })); vi.stubGlobal('fetch', fetch);
    render(<AgentWorkspace />); await connect();
    expect(screen.getByText('No investigations yet. Submit a task to begin.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Investigation task'), { target: { value: 'Review refund policy' } });
    expect(screen.getByRole('button', { name: 'Start investigation' })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/api/agent/runs', expect.objectContaining({ headers: { 'X-Workspace-Key': 'a'.repeat(32) }, cache: 'no-store' }));
  });

  it('submits a task and separates facts, AI interpretations and quoted citations', async () => {
    const fetch = vi.fn(async (_url: string, init: RequestInit) => reply(init.method === 'POST' ? run : { items: [] }));
    vi.stubGlobal('fetch', fetch); render(<AgentWorkspace />); await connect();
    fireEvent.change(screen.getByLabelText('Investigation task'), { target: { value: run.task } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Start investigation' }));
    await screen.findByRole('region', { name: 'Investigation report' });
    expect(screen.getByText('Calculated database facts')).toBeInTheDocument();
    expect(screen.getByText('AI-generated document interpretations')).toBeInTheDocument();
    expect(screen.getByText('Refund requests must arrive within thirty days.').closest('blockquote')).not.toBeNull();
    expect(screen.getByRole('link', { name: '[1]' })).toHaveAttribute('href', '#agent-source-1');
    expect(fetch).toHaveBeenLastCalledWith('/api/agent/runs', expect.objectContaining({ method: 'POST', body: JSON.stringify({ task: run.task, provider_consent: true }) }));
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
    expect(screen.queryByRole('region', { name: 'Investigation report' })).not.toBeInTheDocument();
  });

  it('cancels a running investigation and shows its stopped timeline', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => reply(url.endsWith('/cancel') ?
      { ...run, status: 'cancelled', result: null, error_code: 'cancelled_by_user' } :
      { items: [{ ...run, status: 'running', result: null }] })));
    render(<AgentWorkspace />); await connect();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel investigation' }));
    expect(await screen.findByText('Run cancelled')).toBeInTheDocument();
    expect(screen.getByText(/in-flight provider request/)).toBeInTheDocument();
  });

  it('shows safe connection errors and allows retry', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Invalid workspace key.' }) })));
    render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText('Workspace access key'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'Connect workspace' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid workspace key.');
    expect(screen.getByRole('button', { name: 'Connect workspace' })).toBeEnabled();
  });

  it('renders insufficient evidence without invented citations', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => reply({ items: [{ ...run, result: { ...run.result,
      status: 'insufficient_evidence', database_facts: null, document_findings: {
        status: 'insufficient_evidence', message: 'No sufficient document evidence.', claims: [], sources: [],
      } } }] })));
    render(<AgentWorkspace />); await connect();
    expect(screen.getByText('No sufficient document evidence.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '[1]' })).not.toBeInTheDocument();
  });

  it('ignores a response arriving after disconnect', async () => {
    let resolve: (value: unknown) => void = () => {};
    const fetch = vi.fn().mockResolvedValueOnce(reply({ items: [] })).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    vi.stubGlobal('fetch', fetch); render(<AgentWorkspace />); await connect();
    fireEvent.change(screen.getByLabelText('Investigation task'), { target: { value: run.task } });
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(screen.getByRole('button', { name: 'Start investigation' }));
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
    resolve(reply(run));
    await waitFor(() => expect(screen.getByLabelText('Workspace access key')).toBeInTheDocument());
    expect(screen.queryByRole('region', { name: 'Investigation report' })).not.toBeInTheDocument();
  });

  it('polls a running timeline and displays the completed report', async () => {
    const fetch = vi.fn(async (url: string) => reply(url.endsWith('/run-1') ? run : {
      items: [{ ...run, status: 'running', result: null }],
    }));
    vi.stubGlobal('fetch', fetch); render(<AgentWorkspace />); await connect();
    expect(screen.getByText('Run running')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('region', { name: 'Investigation report' })).toBeInTheDocument(), { timeout: 3000 });
    expect(fetch).toHaveBeenCalledWith('/api/agent/runs/run-1', expect.anything());
  });
});
