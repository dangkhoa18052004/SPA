import { useEffect, useRef, useState } from 'react';
import { Alert, App, Button, Checkbox, Descriptions, Divider, Image, InputNumber, Modal, Select, Skeleton, Space } from 'antd';
import { api, ApiError, del, post } from '../../api';
import { vnd } from '../booking/model';

type Summary = { original_total?: string | number; reward_discount?: string | number; loyalty_discount?: string | number;
  payable_amount?: string | number; points_used?: number; points_earned?: number; reward_name?: string | null; reward_code?: string | null;
  reward_redemption_id?: number | null };
type Invoice = Summary & { mahd: number; makh: number; malh: number | null; khachhang_hoten: string; tongtien: string; trangthai: string;
  chitiet: { tendv: string; soluong: number; dongia: string; thanhtien: string }[] };
type Loyalty = Summary & { wallet: { available_points: number; reserved_points: number }; redeem_enabled: boolean; max_points_allowed: number };
type Voucher = { id: number; code: string; status: string; reward: { name: string; reward_type: string; reward_value?: string; percentage_value?: string;
  max_discount_amount?: string | null; minimum_spend?: string | null; apply_to?: string | null } };
type Qr = { qrCodeUrl: string; bank: string; accountNo: string; accountName: string; description: string; amount: string | number };

export const PAID = 'Đã thanh toán';
const code = (id: number) => `HD${String(id).padStart(6, '0')}`;
const payable = (i: Summary & { tongtien?: string }) => Number(i.payable_amount ?? i.tongtien ?? 0);

function voucherTerms(v: Voucher['reward']) {
  const amount = v.reward_type === 'voucher_percent'
    ? `${Number(v.percentage_value)}%${v.max_discount_amount ? ` (tối đa ${vnd(v.max_discount_amount)})` : ''}` : vnd(v.reward_value || 0);
  const minimum = Number(v.minimum_spend || 0);
  return `Giảm ${amount} · ${minimum ? `đơn từ ${vnd(minimum)}` : 'không yêu cầu đơn tối thiểu'}`;
}

function Totals({ data }: { data: Summary & { tongtien?: string } }) {
  return <Descriptions size="small" column={1} items={[
    { key: 'subtotal', label: 'Tạm tính', children: vnd(data.original_total ?? data.tongtien ?? 0) },
    ...(Number(data.reward_discount) ? [{ key: 'voucher', label: `Voucher${data.reward_code ? ` (${data.reward_code})` : ''}`, children: `−${vnd(data.reward_discount!)}` }] : []),
    ...(Number(data.loyalty_discount) ? [{ key: 'points', label: `Điểm thưởng (${data.points_used} điểm)`, children: `−${vnd(data.loyalty_discount!)}` }] : []),
    { key: 'pay', label: 'Cần thanh toán', children: <strong data-testid="invoice-payable">{vnd(payable(data))}</strong> },
    ...(data.points_earned ? [{ key: 'earn', label: 'Điểm tích được', children: `+${data.points_earned} điểm` }] : [])]} />;
}

/** Points and vouchers: every limit comes from the server preview; reservations survive closing. */
export function LoyaltyEditor({ base, makh, kind, version, onChanged }: { base: string; makh: number; kind: 'service_invoice' | 'package_purchase';
  version: unknown; onChanged: () => Promise<void> }) {
  const [state, setState] = useState<Loyalty>();
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [points, setPoints] = useState<number | null>(null);
  const [usePoints, setUsePoints] = useState(false);
  const [voucher, setVoucher] = useState<number>();
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const loyalty = await api<Loyalty>(`${base}/loyalty`);
        if (!active) return;
        setState(loyalty); setUsePoints(!!loyalty.points_used); setPoints(loyalty.points_used || null);
        const list = await api<{ items: Voucher[] }>(`/api/admin/loyalty/customers/${makh}/vouchers?usable_for=${kind}&per_page=100`);
        if (active) setVouchers(list.items.filter(v => v.status === 'available' && ['voucher_amount', 'voucher_percent'].includes(v.reward.reward_type)
          && [undefined, null, 'both', kind].includes(v.reward.apply_to)));
      } catch (e) { if (active) setError((e as Error).message); }
    })();
    return () => { active = false; };
  }, [base, makh, kind, version]);
  async function run(action: () => Promise<unknown>, reload = true) {
    setBusy(true); setNote('');
    try { await action(); if (reload) await onChanged(); } catch (e) { setNote((e as Error).message); } finally { setBusy(false); }
  }
  if (error) return <Alert type="warning" showIcon message={`Chưa tải được điểm thưởng: ${error}`} />;
  if (!state) return <Skeleton active paragraph={{ rows: 1 }} />;
  const total = Number(state.original_total);
  return <section className="loyalty-editor" aria-label="Điểm thưởng và voucher">
    <Divider orientation="left" plain>Điểm thưởng và ưu đãi</Divider>
    <p className="muted">Khả dụng {state.wallet.available_points} điểm · Đang giữ {state.wallet.reserved_points} điểm</p>
    {state.redeem_enabled ? <>
      <Checkbox checked={usePoints} disabled={busy} onChange={e => setUsePoints(e.target.checked)}>Sử dụng điểm</Checkbox>
      {usePoints && <Space wrap className="loyalty-points">
        <InputNumber aria-label="Số điểm" min={1} max={state.max_points_allowed} precision={0} value={points} onChange={setPoints} disabled={busy} />
        <Button disabled={busy} onClick={() => setPoints(state.max_points_allowed)}>Tối đa ({state.max_points_allowed})</Button>
        <Button disabled={busy || !points} onClick={() => run(async () => {
          const preview = await post<{ points_allowed: number; discount_amount: string; payable_amount: string }>(`${base}/loyalty/preview`, { points });
          setNote(`Cho phép ${preview.points_allowed} điểm · Giảm ${vnd(preview.discount_amount)} · Còn trả ${vnd(preview.payable_amount)}`);
        }, false)}>Xem quy đổi</Button>
        <Button type="primary" disabled={busy || !points} onClick={() => run(() => post(`${base}/loyalty`, { points }))}>Áp dụng điểm</Button>
      </Space>}
      {!!state.points_used && <Button disabled={busy} onClick={() => run(() => del(`${base}/loyalty`))}>Bỏ sử dụng điểm</Button>}
    </> : <p className="muted">Quy tắc hiện tại không cho dùng điểm cho thanh toán này.</p>}
    {state.reward_redemption_id ? <p>Voucher đang áp dụng: <strong>{state.reward_name}</strong> · {state.reward_code}{' '}
      <Button size="small" disabled={busy} onClick={() => run(() => del(`${base}/reward`))}>Bỏ voucher</Button></p>
      : vouchers.length > 0 && <Space wrap className="loyalty-voucher">
        <Select aria-label="Voucher của khách" placeholder="Chọn voucher" style={{ minWidth: 260 }} value={voucher} onChange={setVoucher} disabled={busy}
          options={vouchers.map(v => { const short = Number(v.reward.minimum_spend || 0) > total;
            return { value: v.id, disabled: short, label: `${v.reward.name} · ${v.code} · ${voucherTerms(v.reward)}${short ? ' (chưa đạt đơn tối thiểu)' : ''}` }; })} />
        <Button disabled={busy || !voucher} onClick={() => run(() => post(`${base}/reward`, { redemption_id: voucher }))}>Áp dụng voucher</Button>
      </Space>}
    {note && <p role="status" className="muted">{note}</p>}
  </section>;
}

/**
 * Collects payment for one service invoice. The server locks the invoice and rejects a second
 * payment, so a lost response is resolved by reading the invoice again instead of resending.
 */
export function InvoicePayment({ invoiceId, onClose, onPaid }: { invoiceId: number | null; onClose: () => void; onPaid?: () => void }) {
  const { message } = App.useApp();
  const [invoice, setInvoice] = useState<Invoice>();
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'choose' | 'cash' | 'qr'>('choose');
  const [cash, setCash] = useState<number | null>(null);
  const [qr, setQr] = useState<Qr>();
  const [qrStatus, setQrStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  async function load(id: number) {
    const data = await api<Invoice>(`/api/admin/invoices/${id}`);
    setInvoice(data); return data;
  }
  function finish(text: string) { message.success(text); onPaid?.(); onClose(); }
  useEffect(() => {
    const token = ++generation.current;
    setInvoice(undefined); setError(''); setMode('choose'); setQr(undefined); setQrStatus(''); setCash(null);
    if (invoiceId === null) return;
    load(invoiceId).then(data => {
      if (token !== generation.current) return;
      if (data.trangthai === PAID) finish('Hóa đơn đã được thanh toán.');
      else setCash(payable(data));
    }).catch(e => { if (token === generation.current) setError((e as Error).message); });
    return () => { generation.current++; };
  }, [invoiceId]);
  // VietQR: poll the invoice until the bank confirms (max 5 minutes); closing stops polling.
  useEffect(() => {
    if (mode !== 'qr' || !qr || invoiceId === null) return;
    const token = generation.current; const deadline = Date.now() + 300000; let timer = 0;
    const poll = async () => {
      try { const latest = await api<Invoice>(`/api/admin/invoices/${invoiceId}`); if (token !== generation.current) return;
        if (latest.trangthai === PAID) { finish('Thanh toán VietQR thành công!'); return; } } catch { /* retry while open */ }
      if (token !== generation.current) return;
      if (Date.now() < deadline) timer = window.setTimeout(poll, 3000);
      else setQrStatus('Chưa nhận được xác nhận. Bạn có thể đóng và tiếp tục thanh toán sau.');
    };
    timer = window.setTimeout(poll, 3000);
    return () => window.clearTimeout(timer);
  }, [mode, qr, invoiceId]);

  async function settle(action: () => Promise<unknown>, success: string) {
    if (!invoice || busy) return;
    setBusy(true);
    try { await action(); finish(success); }
    catch (e) {
      const err = e as ApiError;
      // Outcome unknown or "already paid": the invoice itself is the source of truth.
      try { const latest = await load(invoice.mahd); if (latest.trangthai === PAID) { finish(success); return; } } catch { /* keep the original error */ }
      message.error(err.status === 0 ? 'Chưa rõ kết quả thanh toán. Đã kiểm tra lại: hóa đơn vẫn chưa thanh toán.' : err.message);
    } finally { setBusy(false); }
  }
  async function startQr() {
    if (!invoice) return;
    setBusy(true);
    try { const data = await post<Qr>(`/api/admin/invoices/${invoice.mahd}/generate-qr`, {}); setQr(data); setMode('qr'); setQrStatus('Đang chờ ngân hàng xác nhận…'); }
    catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  const due = invoice ? payable(invoice) : 0;
  return <Modal open={invoiceId !== null} onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden maskClosable={!busy}
    title={invoiceId !== null ? `Thanh toán hóa đơn #${code(invoiceId)}` : ''} width={560}>
    {error ? <Alert type="error" showIcon message={error} action={<Button onClick={() => invoiceId !== null && load(invoiceId).then(() => setError('')).catch(e => setError(e.message))}>Thử lại</Button>} />
      : !invoice ? <Skeleton active /> : <div className="invoice-payment">
        <p>Khách hàng: <strong>{invoice.khachhang_hoten}</strong>{invoice.malh ? ` · Lịch #${invoice.malh}` : ''}</p>
        <ul className="invoice-lines">{invoice.chitiet.map((line, i) => <li key={i}><span>{line.tendv} × {line.soluong}</span><span>{vnd(line.thanhtien)}</span></li>)}</ul>
        <Totals data={invoice} />
        {mode === 'choose' && <>
          <LoyaltyEditor base={`/api/admin/invoices/${invoice.mahd}`} makh={invoice.makh} kind="service_invoice" version={invoice.payable_amount}
            onChanged={async () => { const data = await load(invoice.mahd); setCash(payable(data)); }} />
          <Divider />
          {due === 0 ? <Button type="primary" loading={busy} onClick={() => settle(() => post(`/api/admin/invoices/${invoice.mahd}/pay-points`, {}), 'Thanh toán bằng điểm thành công.')}>Thanh toán bằng điểm</Button>
            : <Space wrap><Button type="primary" onClick={() => setMode('cash')} disabled={busy}>Tiền mặt</Button><Button onClick={startQr} loading={busy}>Chuyển khoản VietQR</Button></Space>}
        </>}
        {mode === 'cash' && <form className="invoice-cash" onSubmit={e => { e.preventDefault();
          if ((cash ?? 0) < due) { message.error('Số tiền khách trả chưa đủ.'); return; }
          void settle(() => post(`/api/admin/invoices/${invoice.mahd}/record-payment`, { sotien: cash, phuongthuc: 'Tiền mặt' }), 'Đã ghi nhận thanh toán tiền mặt.'); }}>
          <label htmlFor="cash-received">Số tiền khách trả</label>
          <InputNumber id="cash-received" min={due} step={1000} precision={0} value={cash} onChange={setCash} style={{ width: '100%' }} disabled={busy}
            formatter={v => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.')} parser={v => Number((v || '').replace(/\./g, ''))} />
          <p data-testid="cash-change">Tiền thừa: <strong>{vnd(Math.max(0, (cash ?? 0) - due))}</strong></p>
          <Space wrap><Button onClick={() => setMode('choose')} disabled={busy}>Quay lại</Button><Button type="primary" htmlType="submit" loading={busy}>Xác nhận đã thu tiền</Button></Space>
        </form>}
        {mode === 'qr' && qr && <div className="invoice-qr">
          <Image src={qr.qrCodeUrl} alt="Mã VietQR" width={240} preview={false} />
          <Descriptions size="small" column={1} items={[{ key: 'bank', label: 'Ngân hàng', children: qr.bank },
            { key: 'acc', label: 'Tài khoản', children: `${qr.accountNo} — ${qr.accountName}` }, { key: 'amount', label: 'Số tiền', children: vnd(qr.amount) },
            { key: 'desc', label: 'Nội dung', children: <strong>{qr.description}</strong> }]} />
          <p role="status" className="muted">{qrStatus}</p>
          <Button onClick={() => { generation.current++; setMode('choose'); setQr(undefined); }}>Chọn cách khác</Button>
        </div>}
      </div>}
  </Modal>;
}

export type Transaction = { id: number; code: string; transaction_type: 'service' | 'package'; display_type_label?: string; customer_name: string;
  customer_phone: string | null; appointment_id: number | null; package_name?: string | null; validity_months?: number | null;
  items: { name: string; quantity?: number; sessions?: number; total?: string }[]; original_total?: string; total_amount: string;
  reward_discount?: string; reward_code?: string | null; loyalty_discount?: string; points_used?: number; payable_amount?: string; points_earned?: number;
  payment_method: string | null; status: string; cash_received?: string | null; change?: string | null; created_at: string | null; paid_at: string | null;
  source_label: string; payment_reference?: string | null; can_pay?: boolean };
export type ReceiptTarget = { kind: 'service' | 'package'; id: number };
const when = (v: string | null) => v ? new Date(v).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : 'Chưa có thông tin';
const escape = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
const isPackage = (t: Transaction) => t.transaction_type === 'package';
const itemLine = (t: Transaction, i: Transaction['items'][number]): [string, string] =>
  isPackage(t) ? [i.name, `${i.sessions ?? 0} buổi`] : [`${i.name} × ${i.quantity ?? 1}`, vnd(i.total ?? 0)];

export function receiptRows(t: Transaction): [string, string][] {
  const row = (label: string, value: string): [string, string] => [label, value];
  return [row('Mã phiếu', t.code), row('Khách hàng', t.customer_name), row('SĐT', t.customer_phone || 'Chưa có thông tin'),
    ...(t.appointment_id ? [row('Mã lịch hẹn', `#${t.appointment_id}`)] : []),
    ...(isPackage(t) ? [row('Gói', t.package_name || 'Gói dịch vụ'),
      row('Hiệu lực', t.validity_months == null ? 'Vô thời hạn' : `${t.validity_months} tháng từ khi kích hoạt`)] : []),
    row('Tạm tính', vnd(t.original_total ?? t.total_amount)),
    ...(Number(t.reward_discount) ? [row(`Voucher${t.reward_code ? ` (${t.reward_code})` : ''}`, `−${vnd(t.reward_discount!)}`)] : []),
    ...(Number(t.loyalty_discount) ? [row(`Điểm thưởng (${t.points_used} điểm)`, `−${vnd(t.loyalty_discount!)}`)] : []),
    row('Cần thanh toán', vnd(t.payable_amount ?? t.total_amount)),
    ...(t.points_earned ? [row('Điểm tích được', `+${t.points_earned} điểm`)] : []),
    row('Phương thức', t.payment_method || (t.status === PAID ? 'Chưa có thông tin' : 'Chưa chọn phương thức')), row('Trạng thái', t.status),
    ...(t.payment_method === 'Tiền mặt' && t.cash_received != null ? [row('Khách đưa', vnd(t.cash_received)), row('Tiền thối', vnd(t.change ?? 0))] : []),
    row('Ngày tạo', when(t.created_at)), row('Thanh toán', t.paid_at ? when(t.paid_at) : 'Chưa thanh toán'), row('Nhân viên / nguồn', t.source_label),
    ...(t.payment_reference ? [row('Mã chuyển khoản', t.payment_reference)] : [])];
}

/** Prints only the receipt in its own window, so the admin shell never ends up on paper. */
function printReceipt(t: Transaction) {
  const win = window.open('', '_blank', 'width=420,height=640');
  if (!win) return false;
  win.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>${escape(t.code)}</title><style>
    body{font-family:-apple-system,"Segoe UI",sans-serif;font-size:13px;margin:16px;color:#000}h1,h2{text-align:center;margin:4px 0}h1{font-size:18px}h2{font-size:14px}
    p{display:flex;justify-content:space-between;gap:12px;margin:4px 0}ul{padding:0;list-style:none;border-top:1px dashed #000;border-bottom:1px dashed #000;margin:8px 0}
    li{display:flex;justify-content:space-between;padding:4px 0}</style></head><body><h1>BIN SPA</h1><h2>PHIẾU THANH TOÁN ${isPackage(t) ? 'GÓI DỊCH VỤ' : 'DỊCH VỤ'}</h2>
    <ul>${t.items.map(i => itemLine(t, i)).map(([a, b]) => `<li><span>${escape(a)}</span><span>${escape(b)}</span></li>`).join('')}</ul>
    ${receiptRows(t).map(([k, v]) => `<p><span>${escape(k)}</span><strong>${escape(v)}</strong></p>`).join('')}
    <script>window.onload=()=>{window.print();}</script></body></html>`);
  win.document.close();
  return true;
}

export function ReceiptModal({ target, onClose, onPay }: { target: ReceiptTarget | null; onClose: () => void; onPay?: (target: ReceiptTarget) => void }) {
  const { message } = App.useApp();
  const [data, setData] = useState<Transaction>();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setData(undefined); setError('');
    if (target) api<{ transaction: Transaction }>(`/api/admin/billing/transactions/${target.kind}/${target.id}`)
      .then(r => { if (active) setData(r.transaction); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [target?.kind, target?.id]);
  return <Modal open={!!target} onCancel={onClose} title={data ? `Phiếu thanh toán ${data.code}` : 'Phiếu thanh toán'} destroyOnHidden width={480}
    footer={<Space wrap><Button onClick={onClose}>Đóng</Button>
      {onPay && data?.can_pay && <Button onClick={() => { const t = target!; onClose(); onPay(t); }}>Thanh toán ngay</Button>}
      <Button type="primary" disabled={!data} onClick={() => { if (data && !printReceipt(data)) message.error('Trình duyệt chặn cửa sổ in. Hãy cho phép cửa sổ bật lên rồi thử lại.'); }}>In phiếu</Button></Space>}>
    {error ? <Alert type="error" showIcon message={error} /> : !data ? <Skeleton active /> : <div className="receipt" data-testid="receipt">
      <ul className="invoice-lines">{data.items.length ? data.items.map((i, n) => { const [a, b] = itemLine(data, i); return <li key={n}><span>{a}</span><span>{b}</span></li>; })
        : <li>Chưa có chi tiết</li>}</ul>
      <Descriptions size="small" column={1} items={receiptRows(data).map(([label, value], n) => ({ key: n, label, children: value }))} />
    </div>}
  </Modal>;
}
