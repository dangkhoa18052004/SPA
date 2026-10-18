import { useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Input, Pagination, Result, Select, Space, Statistic, Table, Tag } from 'antd';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { dateRange, spaToday, vnd } from '../booking/model';
import type { RangeKey } from '../booking/model';
import { InvoicePayment, PAID, ReceiptModal } from './InvoicePayment';
import type { ReceiptTarget, Transaction } from './InvoicePayment';
import { PackagePayment } from './PackagePayment';
import '../booking/booking.css';

const PAGE = 10;
type Stats = { total: number; paid: number; unpaid: number; revenue: string };
const when = (v: string | null) => v ? new Date(v).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }) : '—';
const statusTag = (s: string) => <Tag color={s === PAID ? 'green' : s === 'Chưa thanh toán' ? 'orange' : 'default'}>{s}</Tag>;
const related = (t: Transaction) => t.transaction_type === 'package' ? t.package_name
  : t.appointment_id ? <a href={`/admin/appointments?q=${t.appointment_id}`}>Lịch hẹn #{t.appointment_id}</a> : 'Dịch vụ riêng';

/**
 * Service invoices and counter package sales in one list (same /api/admin/billing source as before).
 * Paying routes to the right flow; both re-read the record before reporting an unclear outcome.
 */
function Billing({ me }: { me: Me }) {
  const [query, setQuery] = useQuery();
  const type = query.get('type') || 'all';
  const status = query.get('status') || 'all';
  const range = (query.get('range') || '') as RangeKey;
  const from = query.get('from') || ''; const to = query.get('to') || '';
  const search = query.get('q') || '';
  const page = Math.max(1, Number(query.get('page')) || 1);
  const [draft, setDraft] = useState(search);
  const [draftFrom, setDraftFrom] = useState(from); const [draftTo, setDraftTo] = useState(to);
  useEffect(() => setDraft(search), [search]);
  useEffect(() => { setDraftFrom(from); setDraftTo(to); }, [from, to]);
  const dates = dateRange(range, spaToday(), from, to);
  const params = new URLSearchParams({ type, status, search, ...(dates || {}) } as Record<string, string>);
  const resource = useResource<{ transactions: Transaction[]; stats: Stats }>(dates === null ? '' : `/api/admin/billing/transactions?${params}`);
  const rows = resource.data?.transactions || [];
  const stats = resource.data?.stats;
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);
  const [receipt, setReceipt] = useState<ReceiptTarget | null>(null);
  const [payInvoice, setPayInvoice] = useState<number | null>(null);
  const [payPackage, setPayPackage] = useState<number | null>(null);
  const canPay = ['admin', 'manager', 'letan'].includes(me.user.role);
  const pay = (t: ReceiptTarget) => t.kind === 'service' ? setPayInvoice(t.id) : setPayPackage(t.id);
  const active = type !== 'all' || status !== 'all' || !!range || !!search;
  const actions = (t: Transaction) => <Space wrap size={6}>
    <Button size="small" onClick={() => setReceipt({ kind: t.transaction_type, id: t.id })}>Xem</Button>
    {t.can_pay && canPay && <Button size="small" type="primary" onClick={() => pay({ kind: t.transaction_type, id: t.id })}>Thu tiền</Button>}
  </Space>;
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">VẬN HÀNH</span><h1>Hóa đơn</h1><p>Hóa đơn dịch vụ và phiếu bán gói: tra cứu, thu tiền, in phiếu.</p></div>
      <Button href="/admin/package-sales">Bán gói tại quầy</Button>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Tổng giao dịch" value={stats?.total ?? '…'} /></Card>
      <Card><Statistic title="Đã thanh toán" value={stats?.paid ?? '…'} /></Card>
      <Card><Statistic title="Chưa thanh toán" value={stats?.unpaid ?? '…'} /></Card>
      <Card><Statistic title="Đã thu" value={stats ? vnd(stats.revenue) : '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters billing">
        <Select aria-label="Loại hóa đơn" value={type} onChange={v => setQuery({ type: v === 'all' ? null : v, page: null })}
          options={[{ value: 'all', label: 'Tất cả loại' }, { value: 'service', label: 'Dịch vụ riêng lẻ' }, { value: 'package', label: 'Gói dịch vụ' }]} />
        <Select aria-label="Thời gian" value={range} onChange={v => setQuery({ range: v || null, from: null, to: null, page: null })}
          options={[{ value: '', label: 'Toàn bộ thời gian' }, { value: 'today', label: 'Hôm nay' }, { value: 'week', label: 'Tuần này' },
            { value: 'month', label: 'Tháng này' }, { value: 'custom', label: 'Chọn ngày…' }]} />
        <Select aria-label="Trạng thái thanh toán" value={status} onChange={v => setQuery({ status: v === 'all' ? null : v, page: null })}
          options={[{ value: 'all', label: 'Tất cả trạng thái' }, { value: 'Đã thanh toán', label: 'Đã thanh toán' }, { value: 'Chưa thanh toán', label: 'Chưa thanh toán' },
            { value: 'Thất bại', label: 'Thất bại' }, { value: 'Đã hủy', label: 'Đã hủy' }]} />
        <Input.Search aria-label="Tìm hóa đơn" placeholder="Mã HD/PG, tên khách, SĐT, mã lịch hẹn" allowClear value={draft}
          onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ q: null, page: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null, page: null })} />
        <Button disabled={!active} onClick={() => setQuery({ type: null, status: null, range: null, from: null, to: null, q: null, page: null })}>Xóa bộ lọc</Button>
      </div>
      {range === 'custom' && <form className="booking-custom-range" onSubmit={e => { e.preventDefault(); setQuery({ from: draftFrom || null, to: draftTo || null, page: null }); }}>
        <label>Từ ngày<Input type="date" value={draftFrom} max={draftTo || undefined} onChange={e => setDraftFrom(e.target.value)} /></label>
        <label>Đến ngày<Input type="date" value={draftTo} min={draftFrom || undefined} onChange={e => setDraftTo(e.target.value)} /></label>
        <Button htmlType="submit" type="primary" disabled={!draftFrom}>Lọc</Button></form>}
      {dates === null && <Alert className="section-title" type="warning" showIcon message="Chọn ngày bắt đầu, và ngày kết thúc không trước ngày bắt đầu, rồi bấm Lọc." />}
      <p className="muted section-title" aria-live="polite">{rows.length} giao dịch{active ? ' · đang lọc' : ''}</p>
      {dates !== null && <ResourceState {...resource} />}
      {dates !== null && !resource.loading && !resource.error && (!rows.length ? <Empty description="Không tìm thấy giao dịch" /> : <>
        <div className="desktop-table"><Table rowKey={(t: Transaction) => `${t.transaction_type}-${t.id}`} dataSource={pageRows} pagination={false} columns={[
          { title: 'Mã', dataIndex: 'code', render: (v: string) => <strong>{v}</strong> },
          { title: 'Loại', render: (_: unknown, t: Transaction) => <Tag color={t.transaction_type === 'package' ? 'purple' : 'blue'}>{t.transaction_type === 'package' ? 'Gói dịch vụ' : 'Dịch vụ'}</Tag> },
          { title: 'Khách hàng', render: (_: unknown, t: Transaction) => <>{t.customer_name}<div className="muted">{t.customer_phone || ''}</div></> },
          { title: 'Liên quan', render: (_: unknown, t: Transaction) => related(t) },
          { title: 'Cần thanh toán', align: 'right' as const, render: (_: unknown, t: Transaction) => <strong>{vnd(t.payable_amount ?? t.total_amount)}</strong> },
          { title: 'Trạng thái', dataIndex: 'status', render: statusTag }, { title: 'Ngày tạo', dataIndex: 'created_at', render: when },
          { title: 'Thao tác', render: (_: unknown, t: Transaction) => actions(t) }]} /></div>
        <div className="mobile-cards">{pageRows.map(t => <Card key={`${t.transaction_type}-${t.id}`} className="small-card">
          <div className="card-head"><strong>{t.code}</strong>{statusTag(t.status)}</div>
          <h2>{t.customer_name}</h2><p>{related(t)} · <strong>{vnd(t.payable_amount ?? t.total_amount)}</strong></p><p className="muted">{when(t.created_at)}</p>{actions(t)}</Card>)}</div>
        {rows.length > PAGE && <Pagination className="pager" current={page} pageSize={PAGE} total={rows.length} showSizeChanger={false} onChange={n => setQuery({ page: n > 1 ? n : null })} />}
      </>)}
    </Card>
    <ReceiptModal target={receipt} onClose={() => setReceipt(null)} onPay={canPay ? pay : undefined} />
    <InvoicePayment invoiceId={payInvoice} onClose={() => { setPayInvoice(null); resource.reload(); }} onPaid={resource.reload} />
    <PackagePayment purchaseId={payPackage} onClose={() => { setPayPackage(null); resource.reload(); }} onPaid={resource.reload}
      onReceipt={id => { setPayPackage(null); setReceipt({ kind: 'package', id }); }} />
  </>;
}

export default function Invoices({ me }: { me: Me }) {
  if (!['admin', 'manager', 'letan'].includes(me.user.role)) return <Result status="403" title="Không có quyền xem hóa đơn" />;
  return <Billing me={me} />;
}
