import { useEffect, useRef, useState } from 'react';
import { Alert, App, Button, Descriptions, Divider, Image, InputNumber, Modal, Result, Skeleton, Space } from 'antd';
import { api, ApiError, post } from '../../api';
import { vnd } from '../booking/model';
import { LoyaltyEditor } from './InvoicePayment';

export type Purchase = { id: number; magoi: number; tengoi: string; makh: number; amount: string; status: string; payment_method: string;
  receipt_code: string; customer_name: string; phone: string | null; created_at: string; paid_at: string | null; staff_name: string | null;
  mathe: number | null; items: { madv: number; tendv: string; total_sessions: number }[]; validity_months: number | null; vietqr_available?: boolean;
  original_total?: string; reward_discount?: string; loyalty_discount?: string; payable_amount?: string; points_used?: number; points_earned?: number;
  reward_code?: string | null; payment?: { qrCodeUrl: string; account_name: string; account_no: string; bank_id: string; description: string; amount: string | number } };

export const purchaseStatus: Record<string, { label: string; color: string }> = { pending: { label: 'Chờ thanh toán', color: 'orange' },
  paid: { label: 'Đã thanh toán', color: 'green' }, failed: { label: 'Thất bại', color: 'red' }, cancelled: { label: 'Đã hủy', color: 'default' } };
export const purchaseMethod: Record<string, string> = { cash: 'Tiền mặt', vietqr: 'VietQR', points: 'Điểm thưởng' };
const due = (p: Purchase) => Number(p.payable_amount ?? p.amount);

/**
 * Collects payment for one counter package sale. Treatment sessions are activated by the server only
 * after payment; a repeated confirmation returns the already-paid purchase, so retries are safe.
 */
export function PackagePayment({ purchaseId, onClose, onPaid, onReceipt }: { purchaseId: number | null; onClose: () => void;
  onPaid?: () => void; onReceipt?: (id: number) => void }) {
  const { message } = App.useApp();
  const [purchase, setPurchase] = useState<Purchase>();
  const [error, setError] = useState('');
  const [cash, setCash] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState('');
  const generation = useRef(0);
  const paidOnce = useRef(false);
  async function load(id: number) {
    const data = (await api<{ purchase: Purchase }>(`/api/admin/package-sales/${id}`)).purchase;
    setPurchase(data);
    if (data.status === 'paid' && !paidOnce.current) { paidOnce.current = true; onPaid?.(); }
    return data;
  }
  useEffect(() => {
    const token = ++generation.current; paidOnce.current = false;
    setPurchase(undefined); setError(''); setWaiting(''); setCash(null);
    if (purchaseId === null) return;
    load(purchaseId).then(p => { if (token === generation.current) setCash(due(p)); }).catch(e => { if (token === generation.current) setError(e.message); });
    return () => { generation.current++; };
  }, [purchaseId]);
  // VietQR: the bank webhook marks the purchase paid; poll for up to 5 minutes while open.
  useEffect(() => {
    if (!purchase || purchase.status !== 'pending' || purchase.payment_method !== 'vietqr' || !purchase.payment) return;
    const token = generation.current; const deadline = Date.now() + 300000; let timer = 0;
    setWaiting('Đang chờ ngân hàng xác nhận…');
    const poll = async () => {
      try { const latest = (await api<{ purchase: Purchase }>(`/api/admin/package-sales/${purchase.id}/status`)).purchase;
        if (token !== generation.current) return;
        if (latest.status !== 'pending') { await load(purchase.id); return; } } catch { /* retry while open */ }
      if (token !== generation.current) return;
      if (Date.now() < deadline) timer = window.setTimeout(poll, 5000);
      else setWaiting('Đã dừng chờ tự động. Bấm "Kiểm tra thanh toán" khi khách đã chuyển khoản.');
    };
    timer = window.setTimeout(poll, 5000);
    return () => window.clearTimeout(timer);
  }, [purchase?.id, purchase?.status, purchase?.payment?.description]);

  async function settle(action: () => Promise<unknown>) {
    if (!purchase || busy) return;
    setBusy(true);
    try { await action(); await load(purchase.id); }
    catch (e) {
      const err = e as ApiError;
      try { const latest = await load(purchase.id); if (latest.status === 'paid') return; } catch { /* keep the original error */ }
      message.error(err.status === 0 ? 'Chưa rõ kết quả. Đã kiểm tra lại: phiếu vẫn chờ thanh toán.' : err.message);
    } finally { setBusy(false); }
  }
  const p = purchase;
  return <Modal open={purchaseId !== null} onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden maskClosable={!busy} width={560}
    title={p ? `Thanh toán gói · ${p.receipt_code}` : 'Thanh toán gói'}>
    {error ? <Alert type="error" showIcon message={error} action={<Button onClick={() => purchaseId !== null && load(purchaseId).then(() => setError('')).catch(e => setError(e.message))}>Thử lại</Button>} />
      : !p ? <Skeleton active /> : p.status === 'paid' ? <div data-testid="package-paid"><Result status="success" title="Đã thanh toán"
        subTitle={`${p.tengoi} · ${p.customer_name}. Liệu trình${p.mathe ? ` #${p.mathe}` : ''} đã được kích hoạt.`}
        extra={<Space wrap>{onReceipt && <Button type="primary" onClick={() => onReceipt(p.id)}>Xem / in phiếu</Button>}<Button onClick={onClose}>Đóng</Button></Space>} /></div>
      : p.status !== 'pending' ? <Alert type="warning" showIcon message={`Phiếu ${purchaseStatus[p.status]?.label.toLowerCase() || p.status}; không thể thu tiền.`} />
      : <div className="invoice-payment">
        <p>Khách hàng: <strong>{p.customer_name}</strong>{p.phone ? ` · ${p.phone}` : ''}</p>
        <ul className="invoice-lines">{p.items.map(i => <li key={i.madv}><span>{i.tendv}</span><span>{i.total_sessions} buổi</span></li>)}</ul>
        <Descriptions size="small" column={1} items={[
          { key: 'pkg', label: 'Gói', children: p.tengoi }, { key: 'method', label: 'Phương thức', children: purchaseMethod[p.payment_method] || p.payment_method },
          { key: 'subtotal', label: 'Tạm tính', children: vnd(p.original_total ?? p.amount) },
          ...(Number(p.reward_discount) ? [{ key: 'v', label: `Voucher${p.reward_code ? ` (${p.reward_code})` : ''}`, children: `−${vnd(p.reward_discount!)}` }] : []),
          ...(Number(p.loyalty_discount) ? [{ key: 'pt', label: `Điểm thưởng (${p.points_used} điểm)`, children: `−${vnd(p.loyalty_discount!)}` }] : []),
          { key: 'due', label: 'Cần thanh toán', children: <strong data-testid="package-payable">{vnd(due(p))}</strong> }]} />
        <LoyaltyEditor base={`/api/admin/packages/purchases/${p.id}`} makh={p.makh} kind="package_purchase" version={p.payable_amount}
          onChanged={async () => { const data = await load(p.id); setCash(due(data)); }} />
        <Divider />
        {due(p) === 0 ? <Button type="primary" loading={busy} onClick={() => settle(() => post(`/api/admin/packages/purchases/${p.id}/pay-points`, {}))}>Thanh toán bằng điểm</Button>
          : p.payment_method === 'cash' ? <form className="invoice-cash" onSubmit={e => { e.preventDefault();
            if ((cash ?? 0) < due(p)) { message.error('Số tiền khách đưa chưa đủ.'); return; }
            void settle(() => post(`/api/admin/packages/purchases/${p.id}/confirm-payment`, { cash_received: cash })); }}>
            <label htmlFor="package-cash">Số tiền khách đưa</label>
            <InputNumber id="package-cash" min={due(p)} step={1000} precision={0} value={cash} onChange={setCash} style={{ width: '100%' }} disabled={busy}
              formatter={v => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.')} parser={v => Number((v || '').replace(/\./g, ''))} />
            <p data-testid="package-change">{(cash ?? 0) >= due(p) ? <>Tiền thối: <strong>{vnd((cash ?? 0) - due(p))}</strong></> : `Chưa đủ: ${vnd(due(p) - (cash ?? 0))}`}</p>
            <Button type="primary" htmlType="submit" loading={busy}>Xác nhận đã nhận tiền</Button>
          </form>
          : p.payment ? <div className="invoice-qr">
            <Image src={p.payment.qrCodeUrl} alt="Mã VietQR thanh toán gói" width={240} preview={false} />
            <Descriptions size="small" column={1} items={[{ key: 'acc', label: 'Tài khoản', children: `${p.payment.account_name} · ${p.payment.account_no} · ${p.payment.bank_id}` },
              { key: 'amount', label: 'Số tiền', children: vnd(p.payment.amount) }, { key: 'desc', label: 'Nội dung', children: <strong>{p.payment.description}</strong> }]} />
            <p className="muted">Liệu trình chỉ kích hoạt khi ngân hàng xác nhận.</p>
            <p role="status" className="muted">{waiting}</p>
            <Button loading={busy} onClick={() => settle(async () => undefined)}>Kiểm tra thanh toán</Button>
          </div>
          : <Alert type="warning" showIcon message="VietQR tạm thời chưa khả dụng. Hãy tạo phiếu tiền mặt hoặc thử lại sau." />}
      </div>}
  </Modal>;
}
