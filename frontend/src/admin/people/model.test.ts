import { describe, expect, it } from 'vitest';
import { overnight, registrationState, shiftHours, shiftStarted, weekDays, weekdayLabel, weekLabel, weekStart } from './model';
import type { MyShift } from './model';

describe('spa week', () => {
  it('starts on Monday and lists seven days', () => {
    expect(weekStart('2026-10-16')).toBe('2026-10-12');
    expect(weekStart('2026-10-18')).toBe('2026-10-12');
    expect(weekStart('2026-10-19')).toBe('2026-10-19');
    expect(weekDays('2026-10-12')).toEqual(['2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16', '2026-10-17', '2026-10-18']);
    expect(weekdayLabel('2026-10-18')).toBe('Chủ nhật');
    expect(weekLabel('2026-12-28')).toBe('28/12/2026 – 03/01/2027');
  });
});

describe('shift hours', () => {
  it('counts overnight shifts into the next day like the server', () => {
    expect(shiftHours('09:00', '18:00')).toBe(9);
    expect(shiftHours('22:00', '06:00')).toBe(8);
    expect(shiftHours('08:15', '12:45')).toBe(4.5);
    expect(overnight('22:00', '06:00')).toBe(true);
    expect(overnight('09:00', '18:00')).toBe(false);
  });
  it('knows when a shift has already started in spa time', () => {
    const now = Date.parse('2026-10-16T08:00:00Z'); // 15:00 Saigon
    expect(shiftStarted('2026-10-16', '14:00', now)).toBe(true);
    expect(shiftStarted('2026-10-16', '16:00', now)).toBe(false);
  });
});

describe('registration state', () => {
  const mine: MyShift[] = [{ ngay: '2026-10-17', ten_ca: 'Ca #5', maca: 5, giobatdau: '09:00', gioketthuc: '12:00', trangthai_code: 'pending', trangthai_text: '', colleagues: [] }];
  it('distinguishes assigned, pending and open shifts', () => {
    expect(registrationState(5, mine, [], 7)).toBe('pending');
    expect(registrationState(6, mine, [{ manv: 7 }], 7)).toBe('assigned');
    expect(registrationState(6, mine, [{ manv: 8 }], 7)).toBe('open');
  });
});
