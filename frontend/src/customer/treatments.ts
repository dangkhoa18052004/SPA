import { escapeHtml as esc, price } from './catalog';

export type TreatmentItem = {
  id: number; madv: number; tendv: string; source_type?: 'package' | 'gift';
  total_sessions: number; consumed: number; reserved: number; available_sessions: number;
  usable: boolean; effective_expires_at?: string | null; valid_from?: string | null;
};
export type Treatment = {
  mathe: number; tengoi: string; status: string; image_url?: string;
  purchased_at: string; activated_at?: string; expires_at?: string | null; items: TreatmentItem[];
};
export type TreatmentUsage = {
  id: number; malh: number; the_item_id: number; tendv: string; source_type?: string;
  state: string; consumed_at?: string; released_at?: string; reserved_at?: string;
};
type Purchase = { id: number; tengoi: string; status: string; payable_amount?: number | string; amount: number | string };
const labels: Record<string, string> = { active: 'Đang sử dụng', used_up: 'Đã dùng hết', expired: 'Hết hạn', cancelled: 'Đã hủy', reserved: 'Đang giữ lượt', consumed: 'Đã sử dụng', released: 'Đã trả lại lượt' };
const number = (value: number) => Math.max(0, Number(value) || 0);
const date = (value?: string | null) => {
  if (!value) return 'Chưa cập nhật';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Chưa cập nhật' : parsed.toLocaleDateString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' });
};
const badge = (status: string) => `<span class="customer-treatment-badge customer-treatment-badge--${['active', 'cancelled', 'expired'].includes(status) ? status : 'neutral'}">${esc(labels[status] || 'Chưa xác định')}</span>`;

function itemHtml(item: TreatmentItem, treatment: Treatment) {
  const gift = item.source_type === 'gift';
  // Availability and effective expiry come from the server, including gifts
  // whose expiry differs from the original package. Never infer entitlement.
  const available = number(item.available_sessions), total = number(item.total_sessions);
  const canBook = treatment.status !== 'cancelled' && item.usable === true && available > 0;
  const href = `/appointments/create?treatment=${Number(treatment.mathe)}&service=${Number(item.madv)}&item=${Number(item.id)}`;
  return `<li class="customer-treatment-service">
    <h5>${esc(item.tendv)}</h5>${gift ? '<p class="customer-treatment-note">Dịch vụ tặng · Không thu thêm tiền cho lượt tặng hợp lệ.</p>' : ''}
    <dl class="customer-treatment-counts"><div><dt>${canBook ? 'Còn có thể đặt' : 'Lượt còn lại'}</dt><dd>${available}<small> buổi</small></dd></div><div><dt>Đang giữ</dt><dd>${number(item.reserved)}<small> buổi</small></dd></div><div><dt>Đã dùng</dt><dd>${number(item.consumed)}<small> / ${total}</small></dd></div></dl>
    <progress value="${Math.min(number(item.consumed), total)}" max="${Math.max(total, 1)}" aria-label="${esc(item.tendv)}: đã dùng ${number(item.consumed)} trên ${total} buổi"></progress>
    <div class="customer-treatment-item-footer"><div><p>Hạn sử dụng: <strong>${item.effective_expires_at ? date(item.effective_expires_at) : 'Vô thời hạn'}</strong></p>${gift && item.valid_from ? `<p>Được sử dụng từ ${date(item.valid_from)}</p>` : ''}${!canBook ? `<p class="customer-treatment-note">${treatment.status === 'cancelled' ? 'Liệu trình đã hủy.' : item.usable === false ? 'Lượt này hiện không khả dụng.' : 'Chưa còn lượt trống để đặt lịch.'}</p>` : ''}</div>${canBook ? `<a class="btn btn-primary" href="${href}" aria-label="Đặt lịch ${esc(item.tendv)}${gift ? ' bằng lượt tặng' : ' trong liệu trình'}">Đặt lịch${gift ? ' bằng lượt tặng' : ''}</a>` : ''}</div>
  </li>`;
}

export function treatmentCard(treatment: Treatment) {
  const id = Number(treatment.mathe);
  const groups = ['package', 'gift'].map(source => {
    const items = treatment.items.filter(item => (item.source_type || 'package') === source);
    return items.length ? `<section class="customer-treatment-group" aria-label="${source === 'gift' ? 'Dịch vụ tặng' : 'Dịch vụ trong gói'}"><h4>${source === 'gift' ? 'Dịch vụ tặng' : 'Dịch vụ trong gói'}</h4><ul>${items.map(item => itemHtml(item, treatment)).join('')}</ul></section>` : '';
  }).join('');
  return `<article class="customer-treatment" aria-labelledby="treatment-title-${id}">
    <header class="customer-treatment-header"><img src="${esc(treatment.image_url || '/static/images/default-package.svg')}" alt="" width="96" height="72" loading="lazy" onerror="this.onerror=null;this.src='/static/images/default-package.svg'"><div><p class="customer-treatment-note">Liệu trình #${id}</p><h3 id="treatment-title-${id}">${esc(treatment.tengoi)}</h3></div>${badge(treatment.status)}</header>
    <dl class="customer-treatment-dates"><div><dt>Ngày mua</dt><dd>${date(treatment.purchased_at)}</dd></div><div><dt>Kích hoạt</dt><dd>${date(treatment.activated_at)}</dd></div><div><dt>Hạn gói gốc</dt><dd>${treatment.expires_at ? date(treatment.expires_at) : 'Vô thời hạn'}</dd></div></dl>
    ${groups}<footer class="customer-treatment-footer"><button type="button" class="btn btn-outline" data-history="${id}" aria-controls="history-${id}" aria-expanded="false">Xem lịch sử sử dụng</button><div id="history-${id}" class="customer-treatment-history" role="region" aria-label="Lịch sử liệu trình #${id}" hidden></div></footer>
  </article>`;
}

export function treatmentHistory(rows: TreatmentUsage[]) {
  return rows.length ? `<ol class="customer-treatment-timeline">${rows.map(row => `<li><div><strong>${esc(row.tendv)}</strong><span>${esc(labels[row.state] || 'Chưa xác định')}</span></div><p>${row.source_type === 'gift' ? 'Lượt tặng' : 'Lượt trong gói'} · Lịch hẹn #${Number(row.malh)} · ${date(row.consumed_at || row.released_at || row.reserved_at)}</p></li>`).join('')}</ol>` : '<p role="status">Liệu trình chưa có lịch sử sử dụng.</p>';
}

export function pendingPurchases(rows: Purchase[]) {
  const pending = rows.filter(row => row.status === 'pending');
  return pending.length ? `<section class="customer-treatment-purchases" aria-label="Gói chờ thanh toán"><h3>Gói đang chờ thanh toán</h3><p>Gói sẽ được kích hoạt sau khi thanh toán được xác nhận.</p><ul>${pending.map(row => `<li><div><strong>${esc(row.tengoi)}</strong><p>${price(row.payable_amount ?? row.amount)}</p></div><div class="package-pending-actions"><a class="btn btn-outline" href="/packages?purchase=${Number(row.id)}" aria-label="Tiếp tục thanh toán ${esc(row.tengoi)}">Tiếp tục thanh toán</a><button type="button" class="btn btn-outline" data-cancel-purchase="${Number(row.id)}" data-purchase-name="${esc(row.tengoi)}">Hủy mua gói</button></div></li>`).join('')}</ul></section>` : '';
}

export const customerTreatments = {
  card: treatmentCard, history: treatmentHistory, purchases: pendingPurchases,
  loading: (message = 'Đang tải liệu trình…') => `<div class="customer-treatment-state" role="status">${esc(message)}</div>`,
  error: (message: string, retry?: 'treatments' | 'purchases') => `<div class="customer-treatment-state" role="alert"><p>${esc(message)}</p>${retry ? `<button type="button" class="btn btn-outline" data-retry-${retry}>Thử lại</button>` : ''}</div>`,
  empty: () => '<div class="package-empty customer-treatment-state"><h3>Bạn chưa có liệu trình nào</h3><p>Các gói đã thanh toán và được kích hoạt sẽ hiển thị tại đây.</p><a class="btn btn-primary" href="/packages">Xem gói dịch vụ</a></div>',
};
declare global { interface Window { CustomerTreatments?: typeof customerTreatments } }
