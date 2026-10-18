/**
 * After a sale request whose outcome is unknown, find the pending purchase it created: same customer
 * and package, not present before the request. Never pick an older or already-settled one.
 */
export function findCreatedPurchase<T extends { id: number; makh: number; magoi: number; status: string }>(before: number[], rows: T[], makh: number, magoi: number) {
  const known = new Set(before);
  return rows.filter(r => !known.has(r.id) && r.makh === makh && r.magoi === magoi && r.status === 'pending').sort((a, b) => b.id - a.id)[0] || null;
}

export type SalePackage = { magoi: number; tengoi: string; mota: string | null; giagoi: string; validity_months: number | null; customer_sale_enabled: boolean;
  regular_total: string; savings: string; image_url: string | null; items: { madv: number; tendv: string; total_sessions: number }[] };

export const validityText = (months: number | null) => months == null ? 'Không giới hạn thời gian' : `Dùng trong ${months} tháng từ khi kích hoạt`;
