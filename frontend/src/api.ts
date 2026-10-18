import { expireSession } from './session';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string, public data: Record<string, unknown> = {}) { super(message); }
}

export function requestStepUp(enrollment: boolean): Promise<void> {
  return new Promise((resolve, reject) => {
    const event = new CustomEvent('binspa:step-up', { cancelable: true, detail: { enrollment, resolve, reject } });
    window.dispatchEvent(event);
    if (!event.defaultPrevented) reject(new ApiError('Mở Bảo mật tài khoản để xác minh rồi thử lại.', 403, 'mfa_required'));
  });
}

// These endpoints answer 401 for a wrong current password while the session is still valid.
const PASSWORD_CHECKS = new Set(['/api/profile/change-password']);

export async function api<T>(path: string, options: RequestInit = {}, retried = false, timeoutMs = 20000): Promise<T> {
  const token = localStorage.getItem('admin_token');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal,
      headers: { Accept: 'application/json', ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers }, credentials: 'same-origin' });
    // Error pages from a proxy (413, 502…) may not be JSON; the status still tells the outcome.
    const result = response.ok ? await response.json() : await response.json().catch(() => ({}));
    if (!response.ok) {
      if (!retried && !path.startsWith('/api/me/security') && response.status === 403 && ['mfa_required', 'mfa_enrollment_required'].includes(result.code)) {
        // The server rejected this request before performing the operation.
        window.clearTimeout(timeout);
        await requestStepUp(result.code === 'mfa_enrollment_required');
        if (localStorage.getItem('admin_token') !== token) throw new ApiError('Tài khoản đăng nhập vừa thay đổi. Hãy tải lại trang trước khi thao tác.', 403, 'auth_changed');
        return api<T>(path, options, true, timeoutMs);
      }
      if (response.status === 401 && !PASSWORD_CHECKS.has(path)) { expireSession(); throw new ApiError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 401, 'session_expired'); }
      throw new ApiError(result.message || result.msg || (response.status === 413 ? 'Tệp quá lớn.' : 'Không thể thực hiện yêu cầu'), response.status, result.code || 'request_failed', result);
    }
    return result as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Không thể kết nối máy chủ. Vui lòng thử lại.', 0, 'network_error');
  } finally { window.clearTimeout(timeout); }
}

export const post = <T>(path: string, data: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(data) });
export const put = <T>(path: string, data: unknown) => api<T>(path, { method: 'PUT', body: JSON.stringify(data) });
export const patch = <T>(path: string, data: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(data) });
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' });
export const upload = <T>(path: string, data: FormData) => api<T>(path, { method: 'POST', body: data });

/** Download a file from an authenticated GET; a step-up challenge is answered once, then retried. */
export async function downloadFile(path: string, filename: string, retried = false): Promise<void> {
  const token = localStorage.getItem('admin_token');
  const response = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'same-origin' });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    if (!retried && response.status === 403 && ['mfa_required', 'mfa_enrollment_required'].includes(result.code)) {
      await requestStepUp(result.code === 'mfa_enrollment_required');
      if (localStorage.getItem('admin_token') !== token) throw new ApiError('Tài khoản đăng nhập vừa thay đổi. Hãy tải lại trang trước khi thao tác.', 403, 'auth_changed');
      return downloadFile(path, filename, true);
    }
    if (response.status === 401) expireSession();
    throw new ApiError(result.message || result.msg || 'Không thể tải tệp', response.status, result.code || 'download_failed');
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename;
  link.click(); URL.revokeObjectURL(url);
}

export const downloadCsv = (periodId: number) => downloadFile(`/api/admin/payroll-periods/${periodId}/export.csv`, `bang-luong-${periodId}.csv`);
