declare global {
  interface Window {
    CustomerAuth: { fetch: typeof fetch; getAccessToken: () => string | null; restoreAccessToken: (force?: boolean) => Promise<string | null>; redirectToLogin: (message?: string) => void; isAuthFailure?: (response: Response, data?: unknown) => Promise<boolean> };
    LoyaltyPayment: { openCustomerInvoice: (id: number) => Promise<void> };
    CustomerRecommendations?: { track: (action: string, target: { madv: number }) => Promise<void> };
  }
}
export class CustomerApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function customerApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  else options.signal?.addEventListener('abort', abort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), 20000);
  try {
    if (!window.CustomerAuth) throw new CustomerApiError('Chưa tải được phiên đăng nhập. Vui lòng tải lại trang.', 0);
    const headers = new Headers(options.headers);
    if (!headers.has('Accept')) headers.set('Accept', 'application/json');
    if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await window.CustomerAuth.fetch(path, { ...options, signal: controller.signal,
      credentials: 'same-origin', headers });
    const data = await response.json().catch(() => { throw new CustomerApiError('Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.', response.status); });
    if (!data || typeof data !== 'object') throw new CustomerApiError('Chưa nhận được dữ liệu từ máy chủ. Vui lòng thử lại.', response.status);
    if (!response.ok || data.success === false) {
      const authFailure = window.CustomerAuth.isAuthFailure
        ? await window.CustomerAuth.isAuthFailure(response, data) : response.status === 401;
      if (authFailure) window.CustomerAuth.redirectToLogin('Vui lòng đăng nhập lại để tiếp tục.');
      throw new CustomerApiError(data.message || data.msg || 'Không thể thực hiện yêu cầu.', response.status);
    }
    return data as T;
  } catch (e) {
    if (e instanceof CustomerApiError) throw e;
    throw new CustomerApiError('Không thể kết nối máy chủ. Vui lòng thử lại.', 0);
  } finally { window.clearTimeout(timeout); options.signal?.removeEventListener('abort', abort); }
}
export const customerPost = <T>(path: string, data: unknown) => customerApi<T>(path, { method: 'POST', body: JSON.stringify(data) });
