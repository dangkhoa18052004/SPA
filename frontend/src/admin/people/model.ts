export type StaffMember = { manv: number; hoten: string; email: string | null; sdt: string | null; taikhoan: string; role: string; trangthai: boolean;
  chucvu: string; macv?: number | null; anhnhanvien: string | null; rating_average: number | null; rating_count: number };
export type Position = { macv: number; tencv: string; dongiagio: string };
export type ShiftRow = { maca: number; branch_id: number | null; ngay: string; start_time: string; end_time: string; sogio: number | null;
  assigned_staff: { manv: number; hoten: string; chucvu: string }[] };
export type Registration = { reg_id: number; ngaydangky: string; nhanvien: { manv: number; hoten: string };
  calam: { maca: number; ngay: string; giobatdau: string; gioketthuc: string } };
export type MyShift = { ngay: string; ten_ca: string; maca?: number; reg_id?: number; giobatdau: string; gioketthuc: string;
  trangthai_code: 'approved' | 'pending'; trangthai_text: string; colleagues: { hoten: string; chucvu: string }[] };
export type WeekShift = { maca: number; ngay: string; start_time: string; end_time: string; assigned_staff: { manv: number; hoten: string }[] };

export const roleLabels: Record<string, { label: string; color: string }> = { admin: { label: 'Quản trị viên', color: 'purple' },
  manager: { label: 'Quản lý', color: 'blue' }, letan: { label: 'Lễ tân', color: 'cyan' }, staff: { label: 'Kỹ thuật viên', color: 'green' } };

const addDays = (day: string, n: number) => { const d = new Date(`${day}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
export { addDays };
/** Monday of the spa-calendar week containing `day` (YYYY-MM-DD). */
export function weekStart(day: string) {
  const weekday = (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7;
  return addDays(day, -weekday);
}
export const weekDays = (monday: string) => Array.from({ length: 7 }, (_, i) => addDays(monday, i));
const WEEKDAY = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật'];
export const weekdayLabel = (day: string) => WEEKDAY[(new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7];
export const dmy = (day: string) => day.slice(0, 10).split('-').reverse().join('/');
export const weekLabel = (monday: string) => `${dmy(monday)} – ${dmy(addDays(monday, 6))}`;

/** Hours between two HH:MM times; an end at or before the start ends the next day (same rule as the server). */
export function shiftHours(start: string, end: string) {
  const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  let minutes = toMin(end) - toMin(start);
  if (minutes <= 0) minutes += 24 * 60;
  return Math.round(minutes / 6) / 10;
}
export const overnight = (start: string, end: string) => end <= start;

/** Status of one shift for the signed-in staff member on the registration page. */
export function registrationState(maca: number, mine: MyShift[], assigned: { manv: number }[], me: number): 'assigned' | 'pending' | 'open' {
  if (assigned.some(s => s.manv === me) || mine.some(m => m.maca === maca && m.trangthai_code === 'approved')) return 'assigned';
  if (mine.some(m => m.maca === maca && m.trangthai_code === 'pending')) return 'pending';
  return 'open';
}

/** Shift start in spa time is in the past (registering for it makes no sense). */
export const shiftStarted = (day: string, start: string, now = Date.now()) => Date.parse(`${day}T${start}:00+07:00`) <= now;

export const avatarUrl = (file: string | null) => file ? `/api/profile/avatar/${encodeURIComponent(file)}` : '/static/images/default-avatar.svg';
