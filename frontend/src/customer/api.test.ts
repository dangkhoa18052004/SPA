import { afterEach, describe, expect, it, vi } from 'vitest';
import { customerApi, CustomerApiError } from './api';

afterEach(() => vi.unstubAllGlobals());
function setup(body: unknown, status = 200) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  const redirectToLogin = vi.fn();
  vi.stubGlobal('window', { setTimeout, clearTimeout, CustomerAuth: { fetch, redirectToLogin } });
  return { fetch, redirectToLogin };
}
describe('customer API boundary', () => {
  it('keeps validation 422 in the form without logging out', async () => {
    const { redirectToLogin } = setup({ success: false, message: 'Ngày không hợp lệ' }, 422);
    await expect(customerApi('/api/appointments/create')).rejects.toMatchObject({ status: 422, message: 'Ngày không hợp lệ' });
    expect(redirectToLogin).not.toHaveBeenCalled();
  });
  it('redirects an unresolved authentication error once', async () => {
    const { fetch, redirectToLogin } = setup({ msg: 'Token has expired' }, 401);
    await expect(customerApi('/api/profile')).rejects.toBeInstanceOf(CustomerApiError);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(redirectToLogin).toHaveBeenCalledTimes(1);
  });
  it('preserves headers and lets the browser set multipart boundaries', async () => {
    const { fetch } = setup({ success: true });
    const body = new FormData();
    body.set('file', new Blob(['image']), 'avatar.jpg');
    await customerApi('/api/profile/upload-avatar', { method: 'POST', body, headers: new Headers({ 'X-Request-ID': 'test' }) });
    const options = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(options[1].headers).get('X-Request-ID')).toBe('test');
    expect(new Headers(options[1].headers).has('Content-Type')).toBe(false);
  });
  it('accepts the unwrapped invoice contract', async () => {
    setup({ mahd: 1, tongtien: '150000' });
    await expect(customerApi('/api/payment/invoices/1')).resolves.toEqual({ mahd: 1, tongtien: '150000' });
  });
  it('propagates external cancellation to the in-flight request', async () => {
    const { fetch } = setup({ success: true });
    const controller = new AbortController();
    await customerApi('/api/services', { signal: controller.signal });
    const [, options] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    // Listener removed when complete: a later caller abort must not touch the request.
    controller.abort();
    expect(options.signal?.aborted).toBe(false);
    const alreadyAborted = new AbortController();
    alreadyAborted.abort();
    await customerApi('/api/services', { signal: alreadyAborted.signal });
    expect((fetch.mock.calls[1] as unknown as [string, RequestInit])[1].signal?.aborted).toBe(true);
  });
  it('maps a non-JSON gateway failure to a recoverable error with its HTTP status', async () => {
    setup(null);
    window.CustomerAuth.fetch = vi.fn(async () => new Response('<html>Bad gateway</html>', { status: 502 }));
    await expect(customerApi('/api/appointments/create')).rejects.toMatchObject({ status: 502 });
  });
  it('aborts an outstanding resource request when its caller leaves', async () => {
    setup({success:true});
    window.CustomerAuth.fetch = vi.fn((_path, options) => new Promise<Response>((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted','AbortError')), {once:true});
    }));
    const controller = new AbortController();
    const request = customerApi('/api/services', {signal:controller.signal});
    controller.abort();
    await expect(request).rejects.toMatchObject({status:0});
  });
});
