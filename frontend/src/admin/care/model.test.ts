import { describe, expect, it } from 'vitest';
import { canFulfill, reconcileMessage, rewardPayload, richMessage, safeImage } from './model';
import type { ChatMessage, Redemption } from './model';
describe('care parity', () => {
  it('only offers physical gift handover while available', () => {
    expect(canFulfill({ reward: { reward_type: 'physical_gift' }, status: 'available' } as Redemption)).toBe(true);
    expect(canFulfill({ reward: { reward_type: 'voucher_amount' }, status: 'available' } as Redemption)).toBe(false);
    expect(canFulfill({ reward: { reward_type: 'physical_gift' }, status: 'fulfilled' } as Redemption)).toBe(false);
  });
  it('does not send hidden required voucher fields when saving a physical gift', () => {
    const body = rewardPayload({ name: ' Khăn ', reward_type: 'physical_gift', points_cost: 20, reward_value: 999, percentage_value: 10, minimum_spend: 200000, active: true });
    expect(body.name).toBe('Khăn'); expect(body.reward_value).toBe(0); expect(body).not.toHaveProperty('percentage_value'); expect(body).not.toHaveProperty('minimum_spend');
  });
  it('preserves percentage cap and explicit zero stock', () => {
    expect(rewardPayload({ reward_type: 'voucher_percent', percentage_value: 20, max_discount_amount: 50000, stock: 0 })).toMatchObject({ percentage_value: 20, max_discount_amount: 50000, stock: 0, validity_days: null, reward_value: 0 });
  });
  it('embeds safe images while keeping customer content as plain text', () => {
    expect(safeImage('javascript:alert(1)')).toBe(''); expect(safeImage('//evil.example/pixel')).toBe('');
    expect(safeImage('data:image/jpeg;base64,YWJjZA==')).toBe('data:image/jpeg;base64,YWJjZA==');
    expect(safeImage('data:image/svg+xml;base64,YWJjZA==')).toBe('');
    expect(richMessage('[SERVICE_CARD:1|Massage|100000|60|/static/test.jpg] Xin chào')).toMatchObject({ serviceId: 1, name: 'Massage', image: '/static/test.jpg', text: 'Xin chào' });
    expect(richMessage('<script>alert(1)</script>')).toEqual({ text: '<script>alert(1)</script>' });
  });
  it('reconciles only new staff messages with exact content', () => {
    const rows = [{ matn: 1, noidung: 'test', is_from_staff: true }, { matn: 2, noidung: 'test', is_from_staff: false }, { matn: 3, noidung: 'test', is_from_staff: true }] as ChatMessage[];
    expect(reconcileMessage(rows, [1], 'test').map(m => m.matn)).toEqual([3]);
    expect(reconcileMessage([{ ...rows[2], sender_staff_id: 22 }], [], 'test', 21)).toEqual([]);
  });
});
