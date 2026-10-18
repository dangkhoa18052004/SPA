import type { Treatment as BaseTreatment, TreatmentItem as BaseItem } from '../../customer/booking-model';

export type TreatmentItem = BaseItem & { total_sessions?: number; consumed?: number; reserved?: number;
  gifted_by_name?: string | null; gift_note?: string | null };
export type Treatment = Omit<BaseTreatment, 'items'> & { expires_at?: string | null; items: TreatmentItem[] };

export type Permissions = { canView?: boolean; canConfirm?: boolean; canComplete?: boolean; canCancel?: boolean; canChangeServices?: boolean;
  canCheckIn?: boolean; canCreateInvoice?: boolean; canPayInvoice?: boolean; canViewInvoice?: boolean };
export type AppointmentRow = { malh: number; ngaygio: string; makh?: number | null; khachhang_hoten: string; khachhang_sdt?: string | null;
  dichvu_ten: string; nhanvien_hoten: string; manv: number | null; trangthai: string; trangthai_vi: string; ghichu: string;
  invoice: { mahd: number; trangthai: string; tongtien: string } | null; payment_status: string | null; prepaid: boolean; permissions: Permissions };
export type Coverage = { mathe: number; the_item_id: number; source_type: string; state: string; tengoi: string };
export type AppointmentDetail = Omit<AppointmentRow, 'khachhang_hoten' | 'dichvu_ten' | 'nhanvien_hoten'> & {
  khachhang: { makh: number; hoten: string; sdt: string | null; email: string | null } | null;
  nhanvien: { manv: number; hoten: string } | null;
  services: { madv: number; tendv: string; gia: string; thoiluong: number | null; coverage: Coverage | null }[];
  booking_source: string | null; created_by_staff_name: string | null };
export type Statistics = { total: number; pending: number; confirmed: number; in_progress: number; completed: number; cancelled: number };
export type AdminService = { madv: number; tendv: string; gia: string | number; thoiluong: number | null; active?: boolean; mota?: string | null;
  image_url?: string | null; anhdichvu?: string | null };
export type Customer = { makh: number; hoten: string; sdt: string | null; email: string | null; trangthai: string; anhdaidien?: string | null };
export type PackageChoice = { mathe: number; tengoi: string; item: TreatmentItem };

export const statusLabel: Record<string, string> = { pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', in_progress: 'Đang thực hiện',
  completed: 'Đã hoàn thành', cancelled: 'Đã hủy' };
export const statusColor: Record<string, string> = { pending: 'gold', confirmed: 'blue', in_progress: 'cyan', completed: 'green', cancelled: 'default' };
export const bookingSource: Record<string, string> = { admin: 'Bin Spa hỗ trợ đặt lịch', customer: 'Khách tự đặt', web: 'Khách tự đặt', ai: 'Trợ lý AI', legacy: 'Lịch cũ' };
export const treatmentStatus: Record<string, { label: string; color: string }> = { active: { label: 'Đang hoạt động', color: 'green' },
  used_up: { label: 'Đã dùng hết', color: 'default' }, expired: { label: 'Hết hạn', color: 'orange' }, cancelled: { label: 'Đã hủy', color: 'red' } };
export const customerStatus: Record<string, { label: string; color: string }> = {
  active: { label: 'Hoạt động', color: 'green' }, pending: { label: 'Chờ xác thực', color: 'default' }, blocked: { label: 'Đã khóa', color: 'red' } };

/** Spa opening slots used by the desk (same list as the legacy form). */
export const TIME_SLOTS = Array.from({ length: 23 }, (_, i) => {
  const minutes = 7 * 60 + 30 + i * 30;
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
});

/** Calendar date at the spa (UTC+7), independent of the device timezone. */
export const spaToday = (now = new Date()) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
const shift = (day: string, days: number) => { const d = new Date(`${day}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0, 10); };

export type RangeKey = '' | 'today' | 'week' | 'month' | 'custom';
/** Whole week (Mon–Sun) and whole month, so upcoming bookings later in the period are included. */
export function dateRange(key: RangeKey, today: string, from = '', to = ''): { start_date?: string; end_date?: string } | null {
  if (key === 'today') return { start_date: today, end_date: today };
  if (key === 'week') {
    const weekday = (new Date(`${today}T00:00:00Z`).getUTCDay() + 6) % 7;
    const start = shift(today, -weekday);
    return { start_date: start, end_date: shift(start, 6) };
  }
  if (key === 'month') {
    const start = `${today.slice(0, 8)}01`;
    return { start_date: start, end_date: shift(shift(start, 32).slice(0, 8) + '01', -1) };
  }
  if (key === 'custom') {
    if (!from) return null;
    const end = to || from;
    return end < from ? null : { start_date: from, end_date: end };
  }
  return {};
}

const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
export { fold };
/** Matches customer name/phone, appointment id (with or without #), service and staff, ignoring accents. */
export function matchesAppointment(row: AppointmentRow, query: string) {
  const tokens = fold(query.trim().replace(/^#/, '')).split(/\s+/).filter(Boolean);
  const text = fold(`${row.malh} ${row.khachhang_hoten} ${row.khachhang_sdt || ''} ${row.dichvu_ten} ${row.nhanvien_hoten}`);
  return tokens.every(t => text.includes(t));
}
export function matchesCustomer(row: Customer, query: string) {
  const tokens = fold(query.trim()).split(/\s+/).filter(Boolean);
  const text = fold(`${row.makh} ${row.hoten} ${row.sdt || ''} ${row.email || ''}`);
  return tokens.every(t => text.includes(t));
}

export const duration = (s: AdminService | undefined) => Number(s?.thoiluong) > 0 ? Number(s!.thoiluong) : 60;
/** Quote shown before saving: package/gift sessions are not charged at the spa. */
export function quote(services: AdminService[], selected: number[], covered: Set<number>, start?: string) {
  const byId = new Map(services.map(s => [s.madv, s]));
  const rows = selected.map(id => byId.get(id)).filter((s): s is AdminService => !!s);
  const minutes = rows.reduce((sum, s) => sum + duration(s), 0);
  const list = rows.reduce((sum, s) => sum + (Number(s.gia) || 0), 0);
  const pay = rows.reduce((sum, s) => sum + (covered.has(s.madv) ? 0 : Number(s.gia) || 0), 0);
  let end = '';
  if (start && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(start)) {
    const total = Number(start.slice(11, 13)) * 60 + Number(start.slice(14, 16)) + minutes;
    end = `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  }
  return { minutes, list, pay, end };
}

/** Package/gift sessions usable for one service on the chosen spa day. */
export function packageChoices(treatments: Treatment[], madv: number, day: string): PackageChoice[] {
  return treatments.filter(t => t.status !== 'cancelled').flatMap(t => t.items
    .filter(i => i.madv === madv && i.usable !== false && i.available_sessions > 0
      && (!i.valid_from || !day || i.valid_from.slice(0, 10) <= day) && (!i.effective_expires_at || !day || i.effective_expires_at.slice(0, 10) >= day))
    .map(item => ({ mathe: t.mathe, tengoi: t.tengoi, item })));
}

export type PackageSelection = Map<number, PackageChoice>;
export const usagePayload = (selection: PackageSelection) => [...selection.values()].map(s => ({ mathe: s.mathe, the_item_id: s.item.id, madv: s.item.madv, quantity: 1 as const }));

/** Drops package picks that are no longer valid (date changed or entitlement refreshed). */
export function revalidate(selection: PackageSelection, treatments: Treatment[], day: string): { selection: PackageSelection; removed: number[] } {
  const next: PackageSelection = new Map(); const removed: number[] = [];
  for (const [madv, pick] of selection) {
    const still = packageChoices(treatments, madv, day).find(c => c.mathe === pick.mathe && c.item.id === pick.item.id);
    if (still) next.set(madv, still); else removed.push(madv);
  }
  return { selection: next, removed };
}

/**
 * After a create request whose outcome is unknown (network drop, 5xx), look for a booking that
 * did not exist before the request for the same customer and start time.
 */
export function findCreated(before: number[], rows: AppointmentRow[], customer: number, start: string) {
  const known = new Set(before);
  return rows.find(r => !known.has(r.malh) && r.makh === customer && r.ngaygio.slice(0, 16) === start) || null;
}

export const vnd = (value: number | string) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value) || 0);
export const dateTime = (iso: string) => iso ? `${iso.slice(11, 16)} · ${iso.slice(0, 10).split('-').reverse().join('/')}` : '';
export const dayLabel = (iso: string) => iso.slice(0, 10).split('-').reverse().join('/');
