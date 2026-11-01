// User access tokens live in memory only. Provider API keys never belong here.
let accessToken = '';
export function setAccessToken(value: string) { accessToken = value; }

const env = (import.meta as unknown as { env?: Record<string, string> }).env;
const defaultApiBase = (env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export function getCustomApiBase(): string {
  try {
    return localStorage.getItem('neuroops_api_base') || defaultApiBase;
  } catch {
    return defaultApiBase;
  }
}

export function setCustomApiBase(url: string) {
  try {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (trimmed) {
      localStorage.setItem('neuroops_api_base', trimmed);
    } else {
      localStorage.removeItem('neuroops_api_base');
    }
  } catch {
    // Ignore storage failure
  }
}

export function getApiUrl(path: string): string {
  const base = getCustomApiBase();
  if (path.startsWith('/api') && base) {
    return `${base}${path}`;
  }
  return path;
}

export function apiFetch(path: string, init: RequestInit = {}) {
  const url = getApiUrl(path);
  return fetch(url, accessToken ? { ...init, headers: { ...init.headers, Authorization: `Bearer ${accessToken}` } } : init);
}
