export type Reward = { id: number; name: string; description: string; reward_type: 'physical_gift' | 'voucher_amount' | 'voucher_percent';
  points_cost: number; reward_value: string | number; percentage_value?: string | number | null; max_discount_amount?: string | number | null;
  minimum_spend?: string | number | null; apply_to?: string; stock: number | null; validity_days: number | null; active: boolean };
export type Ledger = { id: number; makh: number; points_delta: number; description: string; created_at: string };
export type Redemption = { id: number; code: string; reward: Reward; status: string; points_spent: number; redeemed_at: string;
  expires_at: string | null; fulfilled_at: string | null; used_at: string | null; fulfilled_by_name: string | null;
  customer: { makh: number; hoten: string; sdt: string; email: string } };
export type Conversation = { maht: number; customer_name: string; customer_avatar?: string; last_message: string;
  last_message_time: string | null; unread_count: number; assigned_staff_id?: number | null; assigned_staff_name?: string | null };
export type ChatMessage = { matn: number; noidung: string; thoigian: string; is_from_staff: boolean; sender_staff_id?: number | null };
export const rewardKinds = { voucher_amount: 'Voucher giảm tiền', voucher_percent: 'Voucher giảm %', physical_gift: 'Quà tại cửa hàng' };
export const redemptionGroups = { all: 'Tất cả', pickup: 'Chờ nhận quà', usable: 'Voucher có thể dùng', applied: 'Đang áp dụng', done: 'Đã dùng / Đã giao', closed: 'Hết hạn / Đã hủy' };
export const redemptionLabels: Record<string, string> = { available: 'Chưa sử dụng', reserved: 'Đang áp dụng', used: 'Đã sử dụng', fulfilled: 'Đã giao quà', expired: 'Hết hạn', cancelled: 'Đã hủy' };
export const canFulfill = (r: Redemption) => r.reward.reward_type === 'physical_gift' && r.status === 'available';
export const utcDate = (value?: string | null) => value ? new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + 'Z').toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—';
export const options = (values: Record<string, string>) => Object.entries(values).map(([value, label]) => ({ value, label }));
export function rewardPayload(values: Record<string, unknown>) {
  const kind = values.reward_type;
  return { name: String(values.name || '').trim(), description: values.description || '', reward_type: kind,
    points_cost: values.points_cost, active: !!values.active, stock: values.stock ?? null, validity_days: values.validity_days ?? null,
    reward_value: kind === 'voucher_amount' ? values.reward_value : 0,
    ...(kind !== 'physical_gift' ? { apply_to: values.apply_to || 'both', minimum_spend: values.minimum_spend || 0 } : {}),
    ...(kind === 'voucher_percent' ? { percentage_value: values.percentage_value, max_discount_amount: values.max_discount_amount ?? null } : {}) };
}
/** Keep the current customer service picker photos; never embed SVG or executable schemes. */
export function safeImage(value: string) {
  if (value.length <= 4000000 && /^data:image\/(?:jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$/.test(value)) return value;
  if (value.startsWith('/static/') || value.startsWith('/api/profile/avatar/')) return value;
  try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password ? u.href : ''; } catch { return ''; }
}
export function richMessage(text: string) {
  const card = text.match(/^\[SERVICE_CARD:(\d+)\|([^|]+)\|([\d.]+)\|(\d+)\|([^\]]+)\]\s*([\s\S]*)$/);
  if (card && Number.isFinite(Number(card[3]))) return { serviceId: Number(card[1]), name: card[2], price: Number(card[3]), duration: Number(card[4]), image: safeImage(card[5]), text: card[6] };
  const img = text.match(/^\[IMG:([^\]]+)\]\s*([\s\S]*)$/);
  return img ? { image: safeImage(img[1]), text: img[2] } : { text };
}
export function reconcileMessage(messages: ChatMessage[], baseline: number[], text: string, actorId?: number) {
  return messages.filter(m => !baseline.includes(m.matn) && m.is_from_staff && m.noidung === text && (actorId == null || m.sender_staff_id === actorId));
}
