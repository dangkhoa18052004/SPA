import { expect, it } from 'vitest';
import { customerTreatments, pendingPurchases, treatmentCard, treatmentHistory, type Treatment, type TreatmentItem } from './treatments';

const item: TreatmentItem = { id: 8, madv: 12, tendv: 'Chăm sóc da', source_type: 'package', total_sessions: 5, consumed: 2, reserved: 1, available_sessions: 2, usable: true, effective_expires_at: '2027-01-20T00:00:00' };
const treatment: Treatment = { mathe: 4, tengoi: 'Gói chăm sóc', status: 'active', purchased_at: '2026-10-01', activated_at: '2026-10-01', expires_at: '2027-01-20', items: [item] };

it('preserves all three booking identifiers and distinguishes reserved from consumed sessions', () => {
  const html = treatmentCard(treatment);
  expect(html).toContain('/appointments/create?treatment=4&service=12&item=8');
  expect(html).toContain('Còn có thể đặt</dt><dd>2');
  expect(html).toContain('Đang giữ</dt><dd>1');
  expect(html).toContain('Đã dùng</dt><dd>2');
});

it('keeps an independently usable gift bookable after the original package expires', () => {
  const html = treatmentCard({ ...treatment, status: 'expired', items: [
    { ...item, usable: false },
    { ...item, id: 9, source_type: 'gift', usable: true, effective_expires_at: '2027-03-20', valid_from: '2026-10-01' },
  ] });
  expect(html).not.toContain('service=12&item=8');
  expect(html).toContain('service=12&item=9');
  expect(html).toContain('Dịch vụ tặng');
  expect(html).toContain('20/3/2027');
  expect(html).toContain('20/1/2027');
});

it('does not offer booking for cancelled, unavailable or fully reserved items', () => {
  for (const row of [
    { ...treatment, status: 'cancelled' },
    { ...treatment, items: [{ ...item, usable: false }] },
    { ...treatment, items: [{ ...item, reserved: 3, available_sessions: 0 }] },
  ]) {
    expect(treatmentCard(row)).not.toContain('/appointments/create?');
    expect(treatmentCard(row)).not.toContain('Còn có thể đặt');
  }
});

it('escapes service, treatment, history and error text received from APIs', () => {
  const attack = '<img src=x onerror=alert(1)>';
  for (const html of [
    treatmentCard({ ...treatment, tengoi: attack, items: [{ ...item, tendv: attack }] }),
    treatmentHistory([{ id: 1, malh: 2, the_item_id: 8, tendv: attack, state: 'reserved', source_type: 'gift' }]),
    customerTreatments.error(attack, 'treatments'),
  ]) { expect(html).not.toContain(attack); expect(html).toContain('&lt;img'); }
});

it('resumes the pending purchase ID with server payable amount, never a paid purchase', () => {
  const html = pendingPurchases([
    { id: 11, tengoi: 'Gói mới', status: 'pending', amount: 600000, payable_amount: 450000 },
    { id: 12, tengoi: 'Gói đã thanh toán', status: 'paid', amount: 600000 },
  ]);
  expect(html).toContain('/packages?purchase=11');
  expect(html).toContain('450.000');
  expect(html).not.toContain('600.000');
  expect(html).not.toContain('purchase=12');
  expect(html).toContain('data-cancel-purchase="11"');
  expect(html).not.toContain('data-cancel-purchase="12"');
});

it('keeps empty history and an empty treatment list distinct from network errors', () => {
  expect(treatmentHistory([])).toContain('chưa có lịch sử');
  expect(customerTreatments.empty()).toContain('Bạn chưa có liệu trình');
  expect(customerTreatments.error('Không thể tải', 'purchases')).toContain('role="alert"');
  expect(customerTreatments.error('Không thể tải', 'purchases')).toContain('data-retry-purchases');
});
