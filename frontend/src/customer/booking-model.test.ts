import { describe, expect, it } from 'vitest';
import { availableBookingSlots, choices, initialSelection, subtotal } from './booking-model';
import type { Service, Treatment } from './booking-model';

const services = [{ madv: 1, gia: '300000' }, { madv: 2, gia: '500000' }] as Service[];
describe('visible appointment times', () => {
  it('hides past starts and fully booked times, using Vietnam time even on devices abroad', () => {
    const slots = [{ time: '08:30', available: true }, { time: '09:00', available: true }, { time: '09:30', available: false }, { time: '10:00', available: true }];
    expect(availableBookingSlots(slots, '2026-10-15', Date.parse('2026-10-15T02:00:01Z')).map(s => s.time)).toEqual(['10:00']);
    expect(availableBookingSlots(slots, '2026-10-16', Date.parse('2026-10-15T02:00:01Z')).map(s => s.time)).toEqual(['08:30', '09:00', '10:00']);
  });
  it('expires a previously available start and handles the Vietnam date changing before UTC', () => {
    const slots = [{ time: '00:00', available: true }, { time: '00:30', available: true }];
    expect(availableBookingSlots(slots, '2026-10-16', Date.parse('2026-10-15T16:59:59Z'))).toHaveLength(2);
    expect(availableBookingSlots(slots, '2026-10-16', Date.parse('2026-10-15T17:00:00Z')).map(s => s.time)).toEqual(['00:30']);
    expect(availableBookingSlots(slots, '2026-10-15', Date.parse('2026-10-15T17:00:00Z'))).toEqual([]);
  });
});
const treatments = [{ mathe: 10, status: 'active', tengoi: 'Combo', items: [
  { id: 20, madv: 1, available_sessions: 2, usable: true, source_type: 'package', valid_from: null, effective_expires_at: '2026-10-31T23:59:59' },
  { id: 21, madv: 1, available_sessions: 1, usable: true, source_type: 'gift', valid_from: '2026-10-10T00:00:00', effective_expires_at: '2026-10-15T23:59:59' }
] }] as Treatment[];
describe('booking entitlement selection', () => {
  it('honors exact gift deep links and excludes gift value from retail subtotal', () => {
    const initial = initialSelection('?treatment=10&service=1&item=21', services, treatments, '2026-10-15');
    expect(initial.invalidEntitlement).toBe(false);
    expect(initial.usages[0].the_item_id).toBe(21);
    expect(subtotal(services, initial.usages)).toBe(500000);
  });
  it('never substitutes a paid package item for an expired gift in a deep link', () => {
    const initial = initialSelection('?treatment=10&service=1&item=21', services, treatments, '2026-10-16');
    expect(initial.invalidEntitlement).toBe(true);
    expect(initial.usages).toEqual([]);
    expect(choices(treatments, 1, '2026-10-16').map(c => c.item.id)).toEqual([20]);
  });
  it('selects the original package item for a single-service treatment-only link', () => {
    const initial = initialSelection('?treatment=10', services, treatments, '2026-10-15');
    expect(initial.selected).toEqual([1]);
    expect(initial.usages[0].the_item_id).toBe(20);
    expect(initial.invalidEntitlement).toBe(false);
  });
  it('rejects malformed identifiers and orphan entitlement items', () => {
    for (const query of ['?treatment=10&service=1.5', '?service=1&item=21', '?treatment=10&item=-1']) {
      expect(initialSelection(query, services, treatments, '2026-10-15').invalidEntitlement).toBe(true);
    }
  });
  it('excludes exhausted, cancelled, not yet valid and expired entitlement items', () => {
    expect(choices(treatments, 1, '2026-10-09').map(c => c.item.id)).toEqual([20]);
    expect(choices(treatments, 1, '2026-11-01')).toEqual([]);
    expect(choices([{ ...treatments[0], status: 'cancelled' }], 1, '2026-10-15')).toEqual([]);
    expect(choices([{ ...treatments[0], items: treatments[0].items.map(i => ({ ...i, available_sessions: 0 })) }], 1, '2026-10-15')).toEqual([]);
  });
});
