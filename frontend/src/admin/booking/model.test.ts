import { describe, expect, it } from 'vitest';
import { dateRange, findCreated, matchesAppointment, matchesCustomer, packageChoices, quote, revalidate, spaToday, TIME_SLOTS, usagePayload } from './model';
import type { AppointmentRow, PackageSelection, Treatment } from './model';

const row = (over: Partial<AppointmentRow>): AppointmentRow => ({ malh: 1, ngaygio: '2026-10-16T09:00:00', makh: 7, khachhang_hoten: 'Nguyễn Thị Hoa',
  khachhang_sdt: '0901234567', dichvu_ten: 'Chăm sóc da', nhanvien_hoten: 'Lan', manv: 2, trangthai: 'pending', trangthai_vi: '', ghichu: '',
  invoice: null, payment_status: null, prepaid: false, permissions: {}, ...over });
const treatment = (items: Partial<Treatment['items'][number]>[], status = 'active'): Treatment => ({ mathe: 3, tengoi: 'Gói da 10 buổi', status,
  items: items.map((i, n) => ({ id: 10 + n, madv: 5, tendv: 'Chăm sóc da', usable: true, available_sessions: 2, source_type: 'package',
    valid_from: null, effective_expires_at: null, ...i })) });

describe('date filters use the spa calendar', () => {
  it('derives today in Asia/Ho_Chi_Minh, not the device timezone', () => {
    expect(spaToday(new Date('2026-10-15T18:30:00Z'))).toBe('2026-10-16');
  });
  it('covers the whole week and month so later bookings are not hidden', () => {
    expect(dateRange('today', '2026-10-16')).toEqual({ start_date: '2026-10-16', end_date: '2026-10-16' });
    expect(dateRange('week', '2026-10-16')).toEqual({ start_date: '2026-10-12', end_date: '2026-10-18' });
    expect(dateRange('week', '2026-10-18')).toEqual({ start_date: '2026-10-12', end_date: '2026-10-18' });
    expect(dateRange('month', '2026-02-10')).toEqual({ start_date: '2026-02-01', end_date: '2026-02-28' });
    expect(dateRange('month', '2026-12-31')).toEqual({ start_date: '2026-12-01', end_date: '2026-12-31' });
    expect(dateRange('', '2026-10-16')).toEqual({});
  });
  it('rejects an empty or reversed custom range', () => {
    expect(dateRange('custom', '2026-10-16', '')).toBeNull();
    expect(dateRange('custom', '2026-10-16', '2026-10-20', '2026-10-19')).toBeNull();
    expect(dateRange('custom', '2026-10-16', '2026-10-20')).toEqual({ start_date: '2026-10-20', end_date: '2026-10-20' });
  });
  it('offers the same half-hour desk slots as before', () => {
    expect(TIME_SLOTS[0]).toBe('07:30'); expect(TIME_SLOTS.at(-1)).toBe('18:30'); expect(TIME_SLOTS).toHaveLength(23);
  });
});

describe('search', () => {
  it('ignores accents and matches phone, id and every word', () => {
    expect(matchesAppointment(row({}), 'hoa da')).toBe(true);
    expect(matchesAppointment(row({}), '#1')).toBe(true);
    expect(matchesAppointment(row({}), '0901234')).toBe(true);
    expect(matchesAppointment(row({}), 'massage')).toBe(false);
    expect(matchesCustomer({ makh: 9, hoten: 'Trần Đức', sdt: null, email: 'duc@x.vn', trangthai: 'active' }, 'duc tran')).toBe(true);
  });
});

describe('quote and package sessions', () => {
  const services = [{ madv: 5, tendv: 'Da', gia: '300000', thoiluong: 60 }, { madv: 6, tendv: 'Gội', gia: '100000', thoiluong: null }];
  it('does not charge services covered by a package and computes the end time', () => {
    expect(quote(services, [5, 6], new Set([5]), '2026-10-16T17:30')).toEqual({ minutes: 120, list: 400000, pay: 100000, end: '19:30' });
  });
  it('only offers sessions that are left and valid on the chosen day', () => {
    const t = treatment([{}, { id: 11, available_sessions: 0 }, { id: 12, effective_expires_at: '2026-10-15T23:59:59' }, { id: 13, valid_from: '2026-10-20' }]);
    expect(packageChoices([t], 5, '2026-10-16').map(c => c.item.id)).toEqual([10]);
    expect(packageChoices([treatment([{}], 'cancelled')], 5, '2026-10-16')).toEqual([]);
  });
  it('drops picks that a new day or refreshed entitlement no longer allows', () => {
    const t = treatment([{ effective_expires_at: '2026-10-17T00:00:00' }]);
    const selection: PackageSelection = new Map([[5, packageChoices([t], 5, '2026-10-16')[0]]]);
    expect(revalidate(selection, [t], '2026-10-16').removed).toEqual([]);
    expect(revalidate(selection, [t], '2026-10-18').removed).toEqual([5]);
    expect(usagePayload(selection)).toEqual([{ mathe: 3, the_item_id: 10, madv: 5, quantity: 1 }]);
  });
});

describe('lost response reconciliation', () => {
  it('finds only a new booking for the same customer and start time', () => {
    const rows = [row({ malh: 1 }), row({ malh: 2, ngaygio: '2026-10-16T10:00:00' }), row({ malh: 3, makh: 8, ngaygio: '2026-10-16T10:00:00' })];
    expect(findCreated([1], rows, 7, '2026-10-16T10:00')?.malh).toBe(2);
    expect(findCreated([1, 2], rows, 7, '2026-10-16T10:00')).toBeNull();
    expect(findCreated([], rows, 7, '2026-10-16T11:00')).toBeNull();
  });
});
