import type { PunchBody, Shift } from './types';

export function punchAction(shift: Shift, now = Date.now()): 'check-in' | 'check-out' | null {
  if (!shift.gps_enabled || now < Date.parse(shift.checkin_opens_at) || now > Date.parse(shift.checkout_closes_at)) return null;
  if (shift.attendance?.actual_end) return null;
  if (shift.attendance) return 'check-out';
  return now < Date.parse(shift.end_at) ? 'check-in' : null;
}

export function getPosition(): Promise<GeolocationPosition> {
  if (!window.isSecureContext) return Promise.reject(new Error('Cần mở trang qua HTTPS để sử dụng GPS.'));
  if (!navigator.geolocation) return Promise.reject(new Error('Thiết bị chưa hỗ trợ định vị.'));
  return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve,
    error => reject(new Error(({ 1: 'Cần bật quyền vị trí để chấm công.', 2: 'Chưa lấy được vị trí. Vui lòng thử lại.',
      3: 'Lấy vị trí quá lâu. Vui lòng thử lại.' } as Record<number, string>)[error.code] || 'Không lấy được GPS.')),
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }));
}

export function punchBody(shift: Shift, position: GeolocationPosition): PunchBody {
  return { shift_assignment_id: shift.shift_assignment_id, latitude: position.coords.latitude,
    longitude: position.coords.longitude, accuracy: position.coords.accuracy,
    location_timestamp: new Date(position.timestamp).toISOString(), idempotency_key: crypto.randomUUID() };
}

export const time = (value: string | null) => value ? new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—';
export const dateLabel = (value: string) => new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
export const vnd = (value: string | number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value));
export const statusLabel: Record<string, string> = { OPEN: 'Đang làm', SUBMITTED: 'Chờ duyệt', APPROVED: 'Đã duyệt',
  REJECTED: 'Không duyệt', LOCKED: 'Đã chốt', DRAFT: 'Bản nháp', PENDING: 'Chờ xử lý' };

/** First shift that has not ended yet, to tell staff when they can check in next. */
export function nextShift(shifts: Shift[], now = Date.now()) {
  return [...shifts].filter(s => Date.parse(s.end_at) > now).sort((a, b) => Date.parse(a.start_at) - Date.parse(b.start_at))[0] || null;
}
