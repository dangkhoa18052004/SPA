import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';

const response = (status: number, data: unknown) => ({ ok: status < 400, status, json: async () => data });
let surface: EventTarget;
let values: Map<string, string>;
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  surface = new EventTarget(); values = new Map([['admin_token', 'original-token']]);
  Object.assign(surface, { setTimeout, clearTimeout, location: { assign: vi.fn() } });
  vi.stubGlobal('window', surface);
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, removeItem: (k: string) => values.delete(k) });
  fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('sensitive action verification', () => {
  it('retries the same action once only after an explicit server MFA rejection and completed proof', async () => {
    fetchMock.mockResolvedValueOnce(response(403, { code: 'mfa_required' })).mockResolvedValueOnce(response(200, { saved: true }));
    surface.addEventListener('binspa:step-up', e => { e.preventDefault(); (e as CustomEvent).detail.resolve(); });
    const body = JSON.stringify({ reason: 'keep this reason', version: 3 });
    expect(await api('/sensitive', { method: 'POST', body })).toEqual({ saved: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(c => c[1].body)).toEqual([body, body]);
  });
  it('keeps cancellation explicit and does not send another mutation', async () => {
    fetchMock.mockResolvedValue(response(403, { code: 'mfa_required' }));
    surface.addEventListener('binspa:step-up', e => { e.preventDefault(); (e as CustomEvent).detail.reject(new ApiError('cancelled', 403, 'mfa_cancelled')); });
    await expect(api('/sensitive', { method: 'POST' })).rejects.toMatchObject({ code: 'mfa_cancelled' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('never repeats a request after an unknown network outcome', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api('/sensitive', { method: 'POST' })).rejects.toMatchObject({ code: 'network_error' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('does not loop if permission/elevation still fails after proof', async () => {
    fetchMock.mockResolvedValue(response(403, { code: 'mfa_required' }));
    surface.addEventListener('binspa:step-up', e => { e.preventDefault(); (e as CustomEvent).detail.resolve(); });
    await expect(api('/sensitive', { method: 'POST' })).rejects.toMatchObject({ code: 'mfa_required' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('never carries a held action into a different account or JWT', async () => {
    fetchMock.mockResolvedValue(response(403, { code: 'mfa_required' }));
    surface.addEventListener('binspa:step-up', e => { e.preventDefault(); values.set('admin_token', 'another-token'); (e as CustomEvent).detail.resolve(); });
    await expect(api('/sensitive', { method: 'POST' })).rejects.toMatchObject({ code: 'auth_changed' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('shows proof failures directly without opening another verification dialog', async () => {
    fetchMock.mockResolvedValue(response(403, { code: 'mfa_enrollment_required' }));
    const handler = vi.fn(); surface.addEventListener('binspa:step-up', handler);
    await expect(api('/api/me/security/verify', { method: 'POST' })).rejects.toMatchObject({ code: 'mfa_enrollment_required' });
    expect(handler).not.toHaveBeenCalled();
  });
});
