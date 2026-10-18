declare global {
  interface Window {
    CustomerAuth: { fetch: typeof fetch; getAccessToken: () => string | null; restoreAccessToken: (force?: boolean) => Promise<string | null>; redirectToLogin: (message?: string) => void };
    LoyaltyPayment: { openCustomerInvoice: (id: number) => Promise<void> };
    CustomerRecommendations?: { track: (action: string, target: { madv: number }) => Promise<void> };
  }
}
export class CustomerApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function customerApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20000);
  try {
    const response = await window.CustomerAuth.fetch(path, { ...options, signal: controller.signal,
      credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...options.headers } });
    const data = await response.json();
    if (!response.ok || data.success === false) {
      if (response.status === 401 || response.status === 422) window.CustomerAuth.redirectToLogin('Vui lòng đăng nhập lại để tiếp tục đặt lịch.');
      throw new CustomerApiError(data.message || data.msg || 'Không thể thực hiện yêu cầu.', response.status);
    }
    return data as T;
  } catch (e) {
    if (e instanceof CustomerApiError) throw e;
    throw new CustomerApiError('Không thể kết nối máy chủ. Vui lòng thử lại.', 0);
  } finally { window.clearTimeout(timeout); }
}
export const customerPost = <T>(path: string, data: unknown) => customerApi<T>(path, { method: 'POST', body: JSON.stringify(data) });
