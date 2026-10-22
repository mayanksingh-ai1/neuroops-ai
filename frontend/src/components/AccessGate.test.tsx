import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AccessGate } from './AccessGate';
import { apiFetch, setAccessToken } from '../api/access';

afterEach(() => { setAccessToken(''); vi.unstubAllGlobals(); });
it('keeps the application hidden when configuration is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  render(<AccessGate><p>Private dashboard</p></AccessGate>);
  await screen.findByRole('alert');
  expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument();
});
it('preserves development compatibility', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ required: false }) }));
  render(<AccessGate><p>Development dashboard</p></AccessGate>);
  expect(await screen.findByText('Development dashboard')).toBeInTheDocument();
});
it('authenticates with an in-memory user token and clears it on sign-out', async () => {
  const fetch = vi.fn(async (path: string) => ({ ok: true, json: async () => path.endsWith('/config') ?
    { required: true } : { principal: { id: 'alice', role: 'viewer', workspace: 'alpha' } } }));
  vi.stubGlobal('fetch', fetch);
  render(<AccessGate><p>Private dashboard</p></AccessGate>);
  await screen.findByLabelText('User access token');
  fireEvent.change(screen.getByLabelText('User access token'), { target: { value: 'a'.repeat(48) } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  await screen.findByText('Private dashboard');
  expect(fetch).toHaveBeenCalledWith('/api/auth/session', expect.objectContaining({ headers: { Authorization: 'Bearer ' + 'a'.repeat(48) } }));
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  await apiFetch('/api/auth/session');
  await waitFor(() => expect(fetch).toHaveBeenLastCalledWith('/api/auth/session', {}));
  expect(screen.queryByText('Private dashboard')).not.toBeInTheDocument();
});
