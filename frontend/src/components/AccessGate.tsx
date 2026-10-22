import { useEffect, useRef, useState, type ReactNode, type FormEvent } from 'react';
import { apiFetch, setAccessToken } from '../api/access';

export function AccessGate({ children }: { children: ReactNode }) {
  const [required, setRequired] = useState<boolean | null>(null);
  const [connected, setConnected] = useState(false);
  const [token, setToken] = useState('');
  const [identity, setIdentity] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    const version = ++generation.current;
    fetch('/api/auth/config', { cache: 'no-store', signal: AbortSignal.timeout(5000) }).then(async response => {
      if (!response.ok) throw new Error('Unable to read access configuration.');
      const config = await response.json();
      if (typeof config.required !== 'boolean') throw new Error('Invalid access configuration.');
      if (version === generation.current) setRequired(config.required);
    }).catch(() => { if (version === generation.current) setError('API unavailable. Start the backend, then reload this page.'); });
    return () => { generation.current++; setAccessToken(''); };
  }, []);
  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setAccessToken(token);
    try {
      const response = await apiFetch('/api/auth/session', { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error(`Access denied (${response.status}). Check your assigned access token.`);
      const data = await response.json();
      setIdentity(`${data.principal.id} · ${data.principal.role} · ${data.principal.workspace}`);
      setToken(''); setConnected(true);
    } catch (failure) { setAccessToken(''); setError(failure instanceof Error ? failure.message : 'Connection failed.'); }
    finally { setBusy(false); }
  }
  if (required === false) return <>{children}</>;
  if (connected) return <><div className="access-banner"><span>{identity}</span><button onClick={() => { setAccessToken(''); setConnected(false); setIdentity(''); }}>Sign out</button></div>{children}</>;
  return <main className="access-gate panel p-6"><h1>NeuroOps AI</h1><h2>Authorized workspace access</h2>
    {error && <p role="alert">{error}</p>}
    {required === null ? <p>Checking API access configuration…</p> : <form className="kb-form" onSubmit={connect}>
      <label>User access token<input type="password" autoComplete="off" required minLength={32} maxLength={512} value={token} onChange={event => setToken(event.target.value)} /></label>
      <p>Use the access token assigned by your administrator, not an AI-provider API key. It stays in memory and is cleared on sign-out or reload.</p>
      <button className="export-button" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>}
  </main>;
}
