import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { loginUrl, safeNext } from './session';

describe('post-login destination', () => {
  it('accepts only staff pages on this site', () => {
    expect(safeNext('/admin/operations/payroll?page=2')).toBe('/admin/operations/payroll?page=2');
    expect(safeNext('/employee/attendance')).toBe('/employee/attendance');
    for (const bad of ['https://evil.test/admin', '//evil.test/admin', '/\\evil.test', '/admin/login?next=/admin', '/booking', 'admin/dashboard', '', null])
      expect(safeNext(bad)).toBeNull();
    expect(loginUrl('/admin/crm?q=an')).toBe('/admin/login?next=%2Fadmin%2Fcrm%3Fq%3Dan');
    expect(loginUrl('//evil.test')).toBe('/admin/login');
  });
});

describe('expired session', () => {
  let values: Map<string, string>;
  let assign: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    values = new Map([['admin_token', 'old'], ['admin_role', 'manager'], ['admin_user', '{}']]);
    assign = vi.fn();
    const surface = new EventTarget();
    Object.assign(surface, { setTimeout, clearTimeout, location: { pathname: '/admin/crm', search: '?segment=lapsed', assign } });
    vi.stubGlobal('window', surface);
    vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, removeItem: (k: string) => values.delete(k) });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('clears every stored credential and returns to the same screen after login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ msg: 'Token has expired' }) }));
    await expect(api('/api/admin/crm/customers')).rejects.toMatchObject({ code: 'session_expired' });
    expect(values.size).toBe(0);
    expect(assign).toHaveBeenCalledWith('/admin/login?next=%2Fadmin%2Fcrm%3Fsegment%3Dlapsed');
  });
  it('treats a wrong current password as a form error, not an expired session', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ message: 'Mật khẩu hiện tại không chính xác' }) }));
    await expect(api('/api/profile/change-password', { method: 'PUT' })).rejects.toMatchObject({ message: 'Mật khẩu hiện tại không chính xác' });
    expect(assign).not.toHaveBeenCalled();
    expect(values.get('admin_token')).toBe('old');
  });
  it('reports a non-JSON error page by its status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 413, json: async () => { throw new SyntaxError('html'); } }));
    await expect(api('/api/profile/upload-avatar', { method: 'POST' })).rejects.toMatchObject({ status: 413, message: 'Tệp quá lớn.' });
  });
});
