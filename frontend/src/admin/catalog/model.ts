export type CatalogService = { madv: number; tendv: string; gia: string; thoiluong: number | null; mota: string | null; active: boolean;
  category_id: number | null; post_care_instructions: string; anhdichvu: string | null; commission_percent?: string | null; commission_fixed?: string | null };
export type Category = { id: number; name: string; slug: string };
export type PackageItem = { madv: number; tendv: string; total_sessions: number; regular_unit_price_snapshot: string; package_unit_value: string };
export type ServicePackage = { magoi: number; tengoi: string; mota: string | null; giagoi: string; validity_months: number | null; active: boolean;
  customer_sale_enabled: boolean; staff_sale_enabled: boolean; post_care_instructions: string; regular_total: string; savings: string;
  image_url: string | null; items: PackageItem[]; sold_count?: number; active_treatments?: number };
export type TreatmentItem = { id: number; madv: number; tendv: string; total_sessions: number; consumed: number; reserved: number; available_sessions: number;
  source_type: string; usable: boolean; effective_expires_at: string | null; valid_from: string | null; gifted_by_name: string | null; gift_note: string;
  created_at: string | null };
export type TreatmentUsage = { id: number; malh: number; madv: number; the_item_id: number; tendv: string; source_type: string; state: string;
  reserved_at: string; consumed_at: string | null; released_at: string | null };
export type CustomerTreatment = { mathe: number; makh: number; magoi: number; tengoi: string; status: string; image_url: string | null;
  purchased_at: string; activated_at: string; expires_at: string | null; customer_name: string; phone: string | null; items: TreatmentItem[];
  history?: TreatmentUsage[] };

export type SaleState = 'both' | 'staff' | 'customer' | 'stopped' | 'inactive';
export const saleLabels: Record<SaleState, { label: string; color: string }> = {
  both: { label: 'Web + tại quầy', color: 'green' }, staff: { label: 'Chỉ bán tại quầy', color: 'blue' },
  customer: { label: 'Chỉ bán online', color: 'cyan' }, stopped: { label: 'Ngừng bán', color: 'orange' }, inactive: { label: 'Ngừng hoạt động', color: 'default' } };
export const treatmentLabels: Record<string, { label: string; color: string }> = {
  active: { label: 'Đang sử dụng', color: 'green' }, used_up: { label: 'Đã dùng hết', color: 'default' },
  expired: { label: 'Hết hạn', color: 'orange' }, cancelled: { label: 'Đã hủy', color: 'red' } };
export const usageLabels: Record<string, string> = { reserved: 'Đã giữ buổi', consumed: 'Đã sử dụng', released: 'Đã hoàn buổi' };

export function saleState(p: Pick<ServicePackage, 'active' | 'customer_sale_enabled' | 'staff_sale_enabled'>): SaleState {
  if (!p.active) return 'inactive';
  if (p.customer_sale_enabled && p.staff_sale_enabled) return 'both';
  if (p.staff_sale_enabled) return 'staff';
  return p.customer_sale_enabled ? 'customer' : 'stopped';
}

export const validityLabel = (months: number | null) => months == null ? 'Không giới hạn' : `${months} tháng`;

/** Retail total of the chosen sessions against the package price (same rule the server stores). */
export function packageQuote(rows: { madv?: number; total_sessions?: number | null }[], services: { madv: number; gia: string }[], price: number) {
  const byId = new Map(services.map(s => [s.madv, Number(s.gia)]));
  const retail = rows.reduce((sum, r) => sum + (r.madv ? (byId.get(r.madv) || 0) * (Number(r.total_sessions) || 0) : 0), 0);
  return { retail, savings: Math.max(0, retail - price), overpriced: retail > 0 && price > retail };
}

/** Client-side mirror of the server checks, so mistakes show before saving. */
export function packageItemsError(rows: { madv?: number; total_sessions?: number | null }[]) {
  if (!rows.length) return 'Gói phải có ít nhất một dịch vụ.';
  if (rows.some(r => !r.madv || !Number.isInteger(r.total_sessions) || (r.total_sessions as number) < 1 || (r.total_sessions as number) > 10000))
    return 'Chọn dịch vụ và nhập số buổi từ 1 đến 10.000 cho mỗi dòng.';
  if (new Set(rows.map(r => r.madv)).size !== rows.length) return 'Một dịch vụ không thể xuất hiện nhiều lần trong cùng gói.';
  return '';
}

export function progress(t: Pick<CustomerTreatment, 'items'>) {
  const used = t.items.reduce((sum, i) => sum + Number(i.consumed || 0), 0);
  const total = t.items.reduce((sum, i) => sum + Number(i.total_sessions || 0), 0);
  return { used, total, percent: total ? Math.min(100, Math.round(used / total * 100)) : 0 };
}

export const serviceImage = (s: Pick<CatalogService, 'anhdichvu'>) => s.anhdichvu ? `data:image/jpeg;base64,${s.anhdichvu}` : '/static/images/default-service.jpg';
export const dayText = (iso: string | null, empty = 'Không giới hạn') => iso
  ? new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date(iso.length === 19 ? `${iso}+07:00` : iso)) : empty;

/** Image checks shared by service and package forms (the server validates again). */
export function imageError(file: File, types = ['image/jpeg', 'image/png', 'image/webp']) {
  if (!types.includes(file.type)) return 'Ảnh phải có định dạng JPG, PNG hoặc WEBP.';
  if (file.size > 5 * 1024 * 1024) return 'Ảnh không được lớn hơn 5 MB.';
  return '';
}
