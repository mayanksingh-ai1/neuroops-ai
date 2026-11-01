// User access tokens live in memory only. Provider API keys never belong here.
let accessToken = '';
export function setAccessToken(value: string) { accessToken = value; }

const env = (import.meta as unknown as { env?: Record<string, string> }).env;
const API_BASE = (env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export function getApiUrl(path: string): string {
  if (path.startsWith('/api') && API_BASE) {
    return `${API_BASE}${path}`;
  }
  return path;
}

export function apiFetch(path: string, init: RequestInit = {}) {
  const url = getApiUrl(path);
  return fetch(url, accessToken ? { ...init, headers: { ...init.headers, Authorization: `Bearer ${accessToken}` } } : init);
}
