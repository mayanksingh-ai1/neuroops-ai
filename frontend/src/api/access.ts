// User access tokens live in memory only. Provider API keys never belong here.
let accessToken = '';
export function setAccessToken(value: string) { accessToken = value; }
export function apiFetch(path: string, init: RequestInit = {}) {
  return fetch(path, accessToken ? { ...init, headers: { ...init.headers, Authorization: `Bearer ${accessToken}` } } : init);
}
