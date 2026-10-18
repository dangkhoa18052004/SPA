import { useEffect, useRef, useState } from 'react';
import { Alert, App, Button, Card, Empty, Form, Input, Radio, Result, Select, Space, Table, Tag } from 'antd';
import { api, ApiError, post } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { QuickCustomer } from '../booking/BookingDrawer';
import { fold, vnd } from '../booking/model';
import { ReceiptModal } from './InvoicePayment';
import type { ReceiptTarget } from './InvoicePayment';
import { findCreatedPurchase, validityText } from './model';
import type { SalePackage } from './model';
import { PackagePayment, purchaseMethod, purchaseStatus } from './PackagePayment';
import type { Purchase } from './PackagePayment';
import '../booking/booking.css';

type SaleCustomer = { makh: number; hoten: string; sdt: string | null };
const when = (v: string | null) => v ? new Date(v).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }) : '—';

function PackageCard({ p }: { p: SalePackage }) {
  return <Card size="small" className="sale-package" data-testid="sale-package-preview">
    <div className="sale-package-head">{p.image_url && <img src={p.image_url} alt="" />}<div>
      <h3>{p.tengoi} <span className="muted">#{p.magoi}</span></h3>
      <p><strong>{vnd(p.giagoi)}</strong>{Number(p.savings) > 0 && <> · <s className="muted">{vnd(p.regular_total)}</s> <Tag color="green">Tiết kiệm {vnd(p.savings)}</Tag></>}</p>
      <p className="muted">{validityText(p.validity_months)}{!p.customer_sale_enabled && <> · <Tag>Chỉ bán tại quầy</Tag></>}</p></div></div>
    <ul className="invoice-lines">{p.items.map(i => <li key={i.madv}><span>{i.tendv}</span><span>{i.total_sessions} buổi</span></li>)}</ul>
  </Card>;
}

/**
 * Counter package sale: create a pending purchase, collect cash or VietQR, then the server activates
 * the treatment. A lost create response is matched against the history before another try.
 */
function Sales({ me }: { me: Me }) {
  const { message } = App.useApp();
  const [query, setQuery] = useQuery();
  const historySearch = query.get('q') || '';
  const historyStatus = query.get('status') || '';
  const [historyDraft, setHistoryDraft] = useState(historySearch);
  useEffect(() => setHistoryDraft(historySearch), [historySearch]);
  const packages = useResource<{ packages: SalePackage[] }>('/api/admin/package-sales/packages');
  const options = useResource<{ vietqr_available: boolean }>('/api/packages/payment-options');
  const history = useResource<{ purchases: Purchase[] }>(`/api/admin/package-sales?${new URLSearchParams({ search: historySearch, status: historyStatus })}`);
  const [customers, setCustomers] = useState<SaleCustomer[]>([]);
  const [customer, setCustomer] = useState<number>();
  const [magoi, setMagoi] = useState<number>();
  const [method, setMethod] = useState<'cash' | 'vietqr'>('cash');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState<{ before: number[]; makh: number; magoi: number } | null>(null);
  const [quick, setQuick] = useState(false);
  const [paying, setPaying] = useState<number | null>(null);
  const [receipt, setReceipt] = useState<ReceiptTarget | null>(null);
  const searchVersion = useRef(0);
  const searchTimer = useRef(0);
  async function searchCustomers(term: string, select?: number) {
    const version = ++searchVersion.current;
    try {
      const result = await api<{ customers: SaleCustomer[] }>(`/api/admin/package-sales/customers?search=${encodeURIComponent(term)}`);
      if (version !== searchVersion.current) return;
      setCustomers(result.customers); if (select) setCustomer(select);
    } catch (e) { if (version === searchVersion.current) setError((e as Error).message); }
  }
  useEffect(() => { void searchCustomers(''); }, []);
  const list = packages.data?.packages || [];
  const chosen = list.find(p => p.magoi === magoi);
  const vietqr = options.data?.vietqr_available ?? false;
  const customerLabel = customers.find(c => c.makh === customer);

  async function customerSales(makh: number) {
    const phone = customers.find(c => c.makh === makh)?.sdt || '';
    const rows = (await api<{ purchases: Purchase[] }>(`/api/admin/package-sales?search=${encodeURIComponent(phone)}`)).purchases;
    return rows.filter(r => r.makh === makh);
  }
  async function reconcile(marker = pending) {
    if (!marker) return;
    setBusy(true);
    try {
      const found = findCreatedPurchase(marker.before, await customerSales(marker.makh), marker.makh, marker.magoi);
      setPending(null);
      if (found) { message.success(`Phiếu ${found.receipt_code} đã được tạo trước đó — tiếp tục thu tiền.`); history.reload(); setPaying(found.id); }
      else setError('Đã kiểm tra: phiếu chưa được tạo. Bạn có thể tạo lại.');
    } catch { setError('Vẫn chưa kiểm tra được. Kiểm tra kết nối rồi bấm "Kiểm tra phiếu đã tạo" lần nữa.'); }
    finally { setBusy(false); }
  }
  async function create() {
    if (busy || pending) return;
    setError('');
    if (!customer || !magoi) { setError('Chọn khách hàng và gói dịch vụ.'); return; }
    setBusy(true);
    let marker: { before: number[]; makh: number; magoi: number } | null = null;
    try {
      marker = { before: (await customerSales(customer)).map(r => r.id), makh: customer, magoi };
      const { purchase } = await post<{ purchase: Purchase }>('/api/admin/package-sales', { makh: customer, magoi, payment_method: method });
      message.success(`Đã tạo phiếu ${purchase.receipt_code}. Liệu trình chỉ kích hoạt sau khi thanh toán.`);
      history.reload(); setMagoi(undefined); setPaying(purchase.id);
    } catch (e) {
      const err = e as ApiError;
      if (marker && (err.status === 0 || err.status >= 500 && err.status !== 503)) {
        setPending(marker); setError('Chưa nhận được kết quả tạo phiếu. Đang kiểm tra để tránh tạo trùng…');
        setBusy(false); await reconcile(marker); return;
      }
      setError(err.message);
    } finally { setBusy(false); }
  }
  const rows = history.data?.purchases || [];
  const actions = (p: Purchase) => <Space wrap size={6}>
    <Button size="small" onClick={() => setReceipt({ kind: 'package', id: p.id })}>Xem phiếu</Button>
    {p.status === 'pending' && <Button size="small" type="primary" onClick={() => setPaying(p.id)}>Thu tiền</Button>}
  </Space>;
  const statusTag = (s: string) => <Tag color={purchaseStatus[s]?.color}>{purchaseStatus[s]?.label || s}</Tag>;
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">VẬN HÀNH</span><h1>Bán gói tại quầy</h1><p>Tạo phiếu, thu tiền mặt hoặc VietQR; liệu trình kích hoạt sau khi thanh toán.</p></div>
      <Space wrap><Button href="/admin/packages">Gói dịch vụ</Button><Button href="/admin/invoices?type=package">Hóa đơn gói</Button></Space>
    </div>
    <Card title="Tạo phiếu bán gói">
      <Form layout="vertical" onFinish={create} disabled={busy} className="sale-form">
        <div className="form-grid">
          <Form.Item label="Khách hàng" required extra={<Button type="link" className="booking-quick-add" onClick={() => setQuick(true)}>+ Thêm khách vãng lai</Button>}>
            <Select showSearch aria-label="Khách hàng" placeholder="Gõ tên hoặc số điện thoại" value={customer} onChange={setCustomer} filterOption={false}
              onSearch={term => { window.clearTimeout(searchTimer.current); searchTimer.current = window.setTimeout(() => void searchCustomers(term.trim()), 250); }}
              notFoundContent="Không tìm thấy khách đang hoạt động" options={customers.map(c => ({ value: c.makh, label: `${c.hoten}${c.sdt ? ` · ${c.sdt}` : ''}` }))} />
          </Form.Item>
          <Form.Item label="Gói dịch vụ" required>
            <Select showSearch aria-label="Gói dịch vụ" placeholder="Tên gói hoặc mã #" value={magoi} onChange={setMagoi} loading={packages.loading}
              filterOption={(input, option) => { const term = fold(input.replace(/^#/, '')); return fold(String(option?.label || '')).includes(term) || String(option?.value) === term; }}
              notFoundContent={packages.error || 'Không có gói đang bán tại quầy'}
              options={list.map(p => ({ value: p.magoi, label: `#${p.magoi} · ${p.tengoi} · ${vnd(p.giagoi)}` }))} />
          </Form.Item>
        </div>
        {chosen && <PackageCard p={chosen} />}
        <Form.Item label="Phương thức thanh toán" className="section-title">
          <Radio.Group value={method} onChange={e => setMethod(e.target.value)} optionType="button" options={[{ value: 'cash', label: 'Tiền mặt' },
            { value: 'vietqr', label: vietqr ? 'VietQR' : 'VietQR (tạm chưa khả dụng)', disabled: !vietqr }]} />
        </Form.Item>
        {error && <Alert role="alert" type={pending ? 'warning' : 'error'} showIcon message={error} style={{ marginBottom: 16 }} />}
        <Space wrap>
          {pending ? <Button type="primary" loading={busy} onClick={() => reconcile()}>Kiểm tra phiếu đã tạo</Button>
            : <Button type="primary" htmlType="submit" loading={busy} disabled={!customer || !magoi} data-testid="sale-create">Tạo phiếu và thu tiền</Button>}
          {customerLabel && chosen && <span className="muted">{customerLabel.hoten} · {chosen.tengoi} · {vnd(chosen.giagoi)}</span>}
        </Space>
      </Form>
    </Card>
    <Card className="section-title" title="Phiếu bán gói">
      <div className="booking-filters customers">
        <Select aria-label="Trạng thái phiếu" value={historyStatus} onChange={v => setQuery({ status: v || null })}
          options={[{ value: '', label: 'Tất cả trạng thái' }, ...Object.entries(purchaseStatus).map(([value, s]) => ({ value, label: s.label }))]} />
        <Input.Search aria-label="Tìm phiếu" placeholder="Tên, SĐT, mã phiếu (PG…)" allowClear value={historyDraft}
          onChange={e => { setHistoryDraft(e.target.value); if (!e.target.value) setQuery({ q: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null })} />
        <Button disabled={!historySearch && !historyStatus} onClick={() => setQuery({ q: null, status: null })}>Xóa bộ lọc</Button>
      </div>
      <ResourceState {...history} />
      {!history.loading && !history.error && (!rows.length ? <Empty className="section-title" description="Chưa có phiếu bán gói" /> : <>
        <div className="desktop-table section-title"><Table rowKey="id" dataSource={rows} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
          { title: 'Mã phiếu', dataIndex: 'receipt_code', render: (v: string) => <strong>{v}</strong> },
          { title: 'Khách hàng', render: (_: unknown, p: Purchase) => <>{p.customer_name}<div className="muted">{p.phone || ''}</div></> },
          { title: 'Gói', dataIndex: 'tengoi' }, { title: 'Số tiền', align: 'right' as const, render: (_: unknown, p: Purchase) => vnd(p.payable_amount ?? p.amount) },
          { title: 'Phương thức', dataIndex: 'payment_method', render: (v: string) => purchaseMethod[v] || v },
          { title: 'Trạng thái', dataIndex: 'status', render: statusTag },
          { title: 'Tạo / thanh toán', render: (_: unknown, p: Purchase) => <>{when(p.created_at)}<div className="muted">{p.paid_at ? when(p.paid_at) : ''}</div></> },
          { title: 'Nhân viên', dataIndex: 'staff_name', render: (v: string | null) => v || 'Online' },
          { title: 'Thao tác', render: (_: unknown, p: Purchase) => actions(p) }]} /></div>
        <div className="mobile-cards section-title">{rows.slice(0, 30).map(p => <Card key={p.id} className="small-card">
          <div className="card-head"><strong>{p.receipt_code}</strong>{statusTag(p.status)}</div>
          <h2>{p.customer_name}</h2><p>{p.tengoi} · <strong>{vnd(p.payable_amount ?? p.amount)}</strong> · {purchaseMethod[p.payment_method] || p.payment_method}</p>
          <p className="muted">{when(p.created_at)}</p>{actions(p)}</Card>)}</div>
      </>)}
    </Card>
    <QuickCustomer open={quick} onClose={() => setQuick(false)} onCreated={async makh => {
      setQuick(false);
      // Show the new (or existing) customer in the list, then select it.
      try { const d = await api<SaleCustomer>(`/api/admin/customers/detail/${makh}`); await searchCustomers(d.sdt || d.hoten, makh); }
      catch (e) { setError((e as Error).message); } }} />
    <PackagePayment purchaseId={paying} onClose={() => { setPaying(null); history.reload(); }} onPaid={history.reload}
      onReceipt={id => { setPaying(null); setReceipt({ kind: 'package', id }); }} />
    <ReceiptModal target={receipt} onClose={() => setReceipt(null)} onPay={t => setPaying(t.id)} />
  </>;
}

export default function PackageSales({ me }: { me: Me }) {
  if (!['admin', 'manager', 'letan'].includes(me.user.role)) return <Result status="403" title="Không có quyền bán gói tại quầy" />;
  return <Sales me={me} />;
}
