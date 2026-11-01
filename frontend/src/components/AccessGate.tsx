import { useEffect, useRef, useState, type ReactNode, type FormEvent } from 'react';
import { apiFetch, getCustomApiBase, setAccessToken, setCustomApiBase } from '../api/access';

export function AccessGate({ children }: { children: ReactNode }) {
  const [required, setRequired] = useState<boolean | null>(null);
  const [connected, setConnected] = useState(false);
  const [token, setToken] = useState('');
  const [identity, setIdentity] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [apiUrl, setApiUrl] = useState(getCustomApiBase());
  const generation = useRef(0);

  function checkConfig() {
    const version = ++generation.current;
    setError('');
    apiFetch('/api/auth/config', { cache: 'no-store', signal: AbortSignal.timeout(5000) })
      .then(async response => {
        if (!response.ok) throw new Error('Unable to read access configuration.');
        const config = await response.json();
        if (typeof config.required !== 'boolean') throw new Error('Invalid access configuration.');
        if (version === generation.current) setRequired(config.required);
      })
      .catch(() => {
        if (version === generation.current) {
          setError('API unavailable. Start the backend, connect a remote API URL, or launch Interactive Demo Mode below.');
        }
      });
  }

  useEffect(() => {
    checkConfig();
    return () => { generation.current++; setAccessToken(''); };
  }, []);

  async function connect(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setAccessToken(token);
    try {
      const response = await apiFetch('/api/auth/session', { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error(`Access denied (${response.status}). Check your assigned access token.`);
      const data = await response.json();
      setIdentity(`${data.principal.id} · ${data.principal.role} · ${data.principal.workspace}`);
      setToken('');
      setConnected(true);
    } catch (failure) {
      setAccessToken('');
      setError(failure instanceof Error ? failure.message : 'Connection failed.');
    } finally {
      setBusy(false);
    }
  }

  function handleSaveApiUrl() {
    setCustomApiBase(apiUrl);
    checkConfig();
  }

  function enterDemoMode() {
    setConnected(true);
    setIdentity('Demo Operator · operator · demo-workspace');
  }

  if (required === false) return <>{children}</>;
  if (connected) {
    return (
      <>
        <div className="access-banner">
          <span>{identity}</span>
          <button onClick={() => { setAccessToken(''); setConnected(false); setIdentity(''); }}>Sign out</button>
        </div>
        {children}
      </>
    );
  }

  return (
    <main className="access-gate panel p-6">
      <h1>NeuroOps AI</h1>
      <h2>Authorized workspace access</h2>
      {error && <p role="alert" className="kb-error">{error}</p>}
      
      {required === null && !error && <p>Checking API access configuration…</p>}

      {error ? (
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <button
            type="button"
            className="export-button"
            onClick={enterDemoMode}
          >
            Launch Interactive Demo Mode (Full UI Preview)
          </button>

          <details style={{ background: '#0c1322', padding: '12px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <summary style={{ cursor: 'pointer', color: '#93c5fd', fontWeight: 500 }}>
              Connect Remote Backend API URL (Cloud / Render / Tunnel)
            </summary>
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '12px', color: '#94a3b8' }}>
                Backend Base URL:
                <input
                  type="url"
                  placeholder="https://neuroops-api.onrender.com"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  style={{ width: '100%', marginTop: '4px', padding: '8px 12px', borderRadius: '6px', background: '#10192c', border: '1px solid #3b4968', color: '#e2e8f0' }}
                />
              </label>
              <button
                type="button"
                className="select-button"
                style={{ alignSelf: 'flex-start' }}
                onClick={handleSaveApiUrl}
              >
                Save & Connect
              </button>
            </div>
          </details>
        </div>
      ) : required !== null ? (
        <form className="kb-form" onSubmit={connect}>
          <label>
            User access token
            <input
              type="password"
              autoComplete="off"
              required
              minLength={32}
              maxLength={512}
              value={token}
              onChange={event => setToken(event.target.value)}
            />
          </label>
          <p>
            Use the access token assigned by your administrator, not an AI-provider API key. It stays in memory and is cleared on sign-out or reload.
          </p>
          <button className="export-button" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      ) : null}
    </main>
  );
}
