import { describe, expect, it } from 'vitest';
import { dayText, imageError, packageItemsError, packageQuote, progress, saleState } from './model';

describe('package sale state', () => {
  it('reads the two sale channels and the active switch', () => {
    expect(saleState({ active: false, customer_sale_enabled: true, staff_sale_enabled: true })).toBe('inactive');
    expect(saleState({ active: true, customer_sale_enabled: true, staff_sale_enabled: true })).toBe('both');
    expect(saleState({ active: true, customer_sale_enabled: false, staff_sale_enabled: true })).toBe('staff');
    expect(saleState({ active: true, customer_sale_enabled: true, staff_sale_enabled: false })).toBe('customer');
    expect(saleState({ active: true, customer_sale_enabled: false, staff_sale_enabled: false })).toBe('stopped');
  });
});

describe('package form', () => {
  const services = [{ madv: 1, gia: '300000' }, { madv: 2, gia: '500000' }];
  it('computes retail, savings and warns when the package costs more than retail', () => {
    expect(packageQuote([{ madv: 1, total_sessions: 5 }, { madv: 2, total_sessions: 2 }], services, 2000000)).toEqual({ retail: 2500000, savings: 500000, overpriced: false });
    expect(packageQuote([{ madv: 1, total_sessions: 1 }], services, 400000)).toMatchObject({ savings: 0, overpriced: true });
    expect(packageQuote([{}], services, 100)).toMatchObject({ retail: 0, overpriced: false });
  });
  it('rejects empty, invalid and duplicated rows like the server', () => {
    expect(packageItemsError([])).toContain('ít nhất');
    expect(packageItemsError([{ madv: 1, total_sessions: 0 }])).toContain('số buổi');
    expect(packageItemsError([{ madv: 1, total_sessions: 1.5 }])).toContain('số buổi');
    expect(packageItemsError([{ madv: 1, total_sessions: 2 }, { madv: 1, total_sessions: 3 }])).toContain('nhiều lần');
    expect(packageItemsError([{ madv: 1, total_sessions: 2 }, { madv: 2, total_sessions: 3 }])).toBe('');
  });
});

describe('treatments', () => {
  it('sums used sessions across package and gift items', () => {
    expect(progress({ items: [{ consumed: 2, total_sessions: 5 }, { consumed: 1, total_sessions: 1 }] as never })).toEqual({ used: 3, total: 6, percent: 50 });
    expect(progress({ items: [] })).toEqual({ used: 0, total: 0, percent: 0 });
  });
  it('shows spa-local dates and "no limit" for open-ended expiry', () => {
    expect(dayText('2026-10-31T23:59:59')).toBe('31/10/2026');
    expect(dayText(null)).toBe('Không giới hạn');
  });
  it('checks image type and size before upload', () => {
    expect(imageError(new File(['x'], 'a.gif', { type: 'image/gif' }))).toContain('định dạng');
    expect(imageError(new File(['x'], 'a.png', { type: 'image/png' }))).toBe('');
  });
});
