import { describe, expect, it } from 'vitest';
import { findCreatedPurchase, validityText } from './model';

describe('lost package-sale response', () => {
  const rows = [{ id: 4, makh: 1, magoi: 2, status: 'paid' }, { id: 5, makh: 1, magoi: 2, status: 'pending' },
    { id: 6, makh: 1, magoi: 3, status: 'pending' }, { id: 7, makh: 9, magoi: 2, status: 'pending' }];
  it('reuses only the new pending purchase for the same customer and package', () => {
    expect(findCreatedPurchase([4], rows, 1, 2)?.id).toBe(5);
    expect(findCreatedPurchase([4, 5], rows, 1, 2)).toBeNull();
    expect(findCreatedPurchase([], [{ id: 8, makh: 1, magoi: 2, status: 'paid' }], 1, 2)).toBeNull();
  });
  it('describes validity', () => {
    expect(validityText(null)).toBe('Không giới hạn thời gian');
    expect(validityText(6)).toBe('Dùng trong 6 tháng từ khi kích hoạt');
  });
});
