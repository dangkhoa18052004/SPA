export type Service = { madv: number; tendv: string; gia: string; thoiluong: number; mota: string; category_name: string | null; anhdichvu: string | null };
export type TreatmentItem = { id: number; madv: number; tendv: string; usable: boolean; available_sessions: number; source_type: string; valid_from: string | null; effective_expires_at: string | null };
export type Treatment = { mathe: number; tengoi: string; status: string; items: TreatmentItem[] };
export type Usage = { mathe: number; the_item_id: number; madv: number; quantity: 1 };
export type Slot = { time: string; available: boolean };
export type Slots = { slots: Slot[]; suggestions?: { date: string; time: string }[]; duration_minutes: number; day_status: string };
export type Staff = { manv: number; hoten: string; chucvu: string; available: boolean; message: string };
export type Booking = { malh: number; ngaygio: string; nhanvien: string | null; end_time?: string; invoice_id: number | null };

export const localDate = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const money = (value: number | string) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value));
// Appointment times are spa-local (UTC+7), regardless of the customer's device timezone.
export const isFutureBookingTime = (date: string, time: string, now = Date.now()) => Date.parse(`${date}T${time}:00+07:00`) > now;
export const availableBookingSlots = (slots: Slot[], date: string, now = Date.now()) => slots.filter(slot => slot.available && isFutureBookingTime(date, slot.time, now));
export function choices(treatments: Treatment[], serviceId: number, date: string) {
  return treatments.filter(t => t.status !== 'cancelled').flatMap(t => t.items.filter(i => i.madv === serviceId && i.usable !== false && i.available_sessions > 0
    && (!i.valid_from || i.valid_from.slice(0, 10) <= date) && (!i.effective_expires_at || i.effective_expires_at.slice(0, 10) >= date)).map(item => ({ treatment: t, item })));
}
export function subtotal(services: Service[], usages: Usage[]) {
  const covered = new Set(usages.map(u => u.madv));
  return services.reduce((sum, s) => sum + (covered.has(s.madv) ? 0 : Number(s.gia)), 0);
}
export function initialSelection(search: string, services: Service[], treatments: Treatment[], date: string) {
  const params = new URLSearchParams(search);
  if (['service', 'treatment', 'item'].some(k => params.has(k) && !/^[1-9]\d*$/.test(params.get(k)!)) || params.has('item') && !params.has('treatment')) {
    return { selected: [], usages: [], invalidEntitlement: true };
  }
  const id = Number(params.get('service'));
  const selected = services.some(s => s.madv === id) ? [id] : [];
  if (!params.has('treatment')) return { selected, usages: [], invalidEntitlement: params.has('service') && !selected.length };
  const available = services.flatMap(s => choices(treatments, s.madv, date)).filter(c => c.treatment.mathe === Number(params.get('treatment'))
    && (!params.has('service') || c.item.madv === id) && (!params.has('item') || c.item.id === Number(params.get('item'))));
  const choice = new Set(available.map(c => c.item.madv)).size === 1 ? [...available].sort((a, b) =>
    Number(b.item.source_type === 'package') - Number(a.item.source_type === 'package') ||
    (a.item.effective_expires_at || '9999').localeCompare(b.item.effective_expires_at || '9999') || a.item.id - b.item.id)[0] : undefined;
  const usages: Usage[] = choice ? [{ mathe: choice.treatment.mathe, the_item_id: choice.item.id, madv: choice.item.madv, quantity: 1 }] : [];
  return { selected: choice ? [choice.item.madv] : selected, usages, invalidEntitlement: !available.length };
}
