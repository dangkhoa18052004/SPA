import { describe, expect, it } from 'vitest';
import { nextShift, punchAction, punchBody } from './attendance';
import type { Shift } from './types';

const shift = { shift_assignment_id: 1, gps_enabled: true, attendance: null,
  checkin_opens_at: '2026-10-14T00:30:00Z', start_at: '2026-10-14T01:00:00Z',
  end_at: '2026-10-14T09:00:00Z', checkout_closes_at: '2026-10-14T11:00:00Z' } as Shift;
describe('shift action windows', () => {
  it('blocks early and late punches and unconfigured GPS', () => {
    expect(punchAction(shift, Date.parse('2026-10-14T00:29:59Z'))).toBeNull();
    expect(punchAction(shift, Date.parse('2026-10-14T09:00:00Z'))).toBeNull();
    expect(punchAction({ ...shift, gps_enabled: false }, Date.parse(shift.start_at))).toBeNull();
  });
  it('allows checkout grace for an overnight/open session, then stops after checkout', () => {
    const checked = { ...shift, attendance: { actual_end: null } } as Shift;
    expect(punchAction(checked, Date.parse('2026-10-14T10:59:59Z'))).toBe('check-out');
    expect(punchAction(checked, Date.parse('2026-10-14T11:00:01Z'))).toBeNull();
    expect(punchAction({ ...checked, attendance: { actual_end: shift.end_at } } as Shift, Date.parse(shift.end_at))).toBeNull();
  });
  it('sends the position capture time separately from the eventual server punch time', () => {
    const payload = punchBody(shift, { coords: { latitude: 10.78686228650495, longitude: 106.5794979291708, accuracy: 25 }, timestamp: Date.parse(shift.start_at) } as GeolocationPosition);
    expect(payload.location_timestamp).toBe('2026-10-14T01:00:00.000Z');
    expect(payload.idempotency_key).toMatch(/^[\da-f-]{36}$/);
  });
});

describe('next shift hint', () => {
  const shift = (start: string, end: string) => ({ start_at: start, end_at: end } as unknown as Shift);
  it('skips ended shifts and picks the earliest upcoming one', () => {
    const now = Date.parse('2026-10-16T05:00:00Z');
    const list = [shift('2026-10-18T02:00:00Z', '2026-10-18T10:00:00Z'), shift('2026-10-15T00:00:00Z', '2026-10-15T16:45:00Z'), shift('2026-10-17T02:00:00Z', '2026-10-17T10:00:00Z')];
    expect(nextShift(list, now)?.start_at).toBe('2026-10-17T02:00:00Z');
    expect(nextShift([list[1]], now)).toBeNull();
  });
});
