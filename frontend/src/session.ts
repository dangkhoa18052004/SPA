const AUTH_KEYS = ['admin_token', 'admin_role', 'admin_user'];
export const LOGIN_PATH = '/admin/login';

/** Only same-site staff pages may be used as a post-login destination. */
export function safeNext(value: string | null | undefined): string | null {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null;
  const path = value.split(/[?#]/)[0];
  if (path === LOGIN_PATH || !/^\/(admin|employee)(\/|$)/.test(path)) return null;
  return value;
}

export function loginUrl(next?: string) {
  const target = safeNext(next);
  return target ? `${LOGIN_PATH}?next=${encodeURIComponent(target)}` : LOGIN_PATH;
}

export function clearSession() {
  AUTH_KEYS.forEach(key => localStorage.removeItem(key));
}

/** Session expired: drop the token and come back to the same screen after signing in. */
export function expireSession() {
  clearSession();
  const here = window.location.pathname ? window.location.pathname + (window.location.search || '') : '';
  if (here.startsWith(LOGIN_PATH)) return;
  window.location.assign(loginUrl(here));
}

export async function logout() {
  const token = localStorage.getItem('admin_token');
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin',
      headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch { /* Signing out locally must still happen when the server is unreachable. */ }
  finally { clearSession(); window.location.assign(LOGIN_PATH); }
}
