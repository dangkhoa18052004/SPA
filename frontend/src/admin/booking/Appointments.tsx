import { useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Input, Modal, Pagination, Result, Select, Skeleton, Space, Statistic, Table, Tag } from 'antd';
import { api, ApiError, post } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { InvoicePayment, ReceiptModal } from '../billing/InvoicePayment';
import { BookingDrawer } from './BookingDrawer';
import { ChangeServices } from './ChangeServices';
import { bookingSource, dateRange, dateTime, matchesAppointment, spaToday, statusColor, statusLabel, vnd } from './model';
import type { AdminService, AppointmentDetail, AppointmentRow, RangeKey, Statistics } from './model';
import './booking.css';

const PAGE = 10;
const RANGES: { value: RangeKey; label: string }[] = [{ value: '', label: 'Toàn bộ thời gian' }, { value: 'today', label: 'Hôm nay' },
  { value: 'week', label: 'Tuần này' }, { value: 'month', label: 'Tháng này' }, { value: 'custom', label: 'Chọn ngày…' }];
const status = (row: { trangthai: string; trangthai_vi?: string }) => <Tag color={statusColor[row.trangthai] || 'default'}>{statusLabel[row.trangthai] || row.trangthai_vi || row.trangthai}</Tag>;
const paymentTag = (row: AppointmentRow) => !row.payment_status ? null
  : <Tag color={['Đã thanh toán', 'Đã thanh toán bằng gói'].includes(row.payment_status) ? 'green' : 'orange'}>{row.payment_status}</Tag>;

function Detail({ malh, revision, onClose, actions }: { malh: number | null; revision: number; onClose: () => void; actions: (row: AppointmentRow) => React.ReactNode }) {
  const [data, setData] = useState<AppointmentDetail>();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setData(undefined); setError('');
    if (malh !== null) api<{ appointment: AppointmentDetail }>(`/api/admin/appointments/${malh}`).then(r => { if (active) setData(r.appointment); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [malh, revision]);
  return <Drawer open={malh !== null} onClose={onClose} width={520} title={malh !== null ? `Chi tiết lịch hẹn #${malh}` : ''} destroyOnHidden>
    {error ? <Alert type="error" showIcon message={error} /> : !data ? <Skeleton active /> : <>
      <Descriptions column={1} size="small" items={[
        { key: 'customer', label: 'Khách hàng', children: data.khachhang ? <a href={`/admin/customers?view=${data.khachhang.makh}`}>{data.khachhang.hoten}</a> : 'Không có' },
        { key: 'phone', label: 'Điện thoại', children: data.khachhang?.sdt || 'Chưa có' },
        { key: 'time', label: 'Thời gian', children: dateTime(data.ngaygio) },
        { key: 'staff', label: 'Nhân viên', children: data.nhanvien?.hoten || 'Chưa gán' },
        { key: 'status', label: 'Trạng thái', children: <>{status(data)}{data.prepaid && <Tag color="green">Đã trả trước</Tag>}</> },
        { key: 'payment', label: 'Thanh toán', children: data.payment_status || '—' },
        { key: 'source', label: 'Nguồn đặt lịch', children: `${bookingSource[data.booking_source || ''] || 'Lịch cũ'}${data.created_by_staff_name ? ` · ${data.created_by_staff_name}` : ''}` },
        { key: 'note', label: 'Ghi chú', children: <span className="appointment-note">{data.ghichu || 'Không có ghi chú'}</span> }]} />
      <h3 className="section-title">Dịch vụ đã đặt</h3>
      <ul className="invoice-lines">{data.services.length ? data.services.map(s => <li key={s.madv}><span>{s.tendv}</span><span>{s.coverage
        ? `${s.coverage.state === 'reserved' ? 'Đã giữ buổi' : 'Đã dùng liệu trình'} · ${s.coverage.source_type === 'gift' ? 'Spa tặng' : 'Trong gói'} · ${s.coverage.tengoi}`
        : `Thanh toán riêng · ${vnd(s.gia)}`}</span></li>) : <li>Không có dịch vụ</li>}</ul>
      <Space wrap className="section-title">{actions({ ...data, khachhang_hoten: data.khachhang?.hoten || '', dichvu_ten: '', nhanvien_hoten: data.nhanvien?.hoten || '' })}</Space>
    </>}
  </Drawer>;
}

/**
 * Appointment desk: same API and server rules as the legacy page. Filters live in the URL so Back
 * and reload restore the view; every action button follows the permissions the server returns.
 */
export default function Appointments({ me }: { me: Me }) {
  const { message, modal } = App.useApp();
  const [query, setQuery] = useQuery();
  const staffOnly = me.user.role === 'staff';
  const desk = ['admin', 'manager', 'letan'].includes(me.user.role);
  const today = spaToday();
  const range = (query.get('range') || (staffOnly ? 'today' : '')) as RangeKey;
  const from = query.get('from') || ''; const to = query.get('to') || '';
  const statusFilter = query.get('status') || '';
  const search = query.get('q') || '';
  const customerId = Number(query.get('makh')) || null;
  const page = Math.max(1, Number(query.get('page')) || 1);
  const [draftFrom, setDraftFrom] = useState(from); const [draftTo, setDraftTo] = useState(to);
  const [searchDraft, setSearchDraft] = useState(search);
  useEffect(() => { setDraftFrom(from); setDraftTo(to); }, [from, to]);
  useEffect(() => setSearchDraft(search), [search]);
  const dates = dateRange(range, today, from, to);
  const params = new URLSearchParams(Object.entries({ ...(dates || {}), ...(statusFilter && !staffOnly ? { status: statusFilter } : {}),
    ...(customerId && !staffOnly ? { makh: String(customerId) } : {}) }).filter(([, v]) => v) as [string, string][]);
  // Staff see only their own schedule, which the server limits to a date range (default today).
  if (staffOnly && !params.has('start_date')) { params.set('start_date', today); params.set('end_date', today); }
  const listPath = dates === null ? '' : staffOnly ? `/api/admin/appointments/my-schedule?${params}` : `/api/admin/appointments?${params}`;
  const [revision, setRevision] = useState(0);
  const list = useResource<AppointmentRow[] | { appointments: AppointmentRow[] }>(listPath);
  const statsParams = new URLSearchParams(Object.entries(dates || {}).filter(([, v]) => v) as [string, string][]);
  const stats = useResource<{ statistics: Statistics }>(dates === null ? '' : `/api/admin/appointments/statistics?${statsParams}`);
  const servicesResource = useResource<AdminService[] | { services: AdminService[] }>('/api/admin/services');
  const services = useMemo(() => { const d = servicesResource.data; return Array.isArray(d) ? d : d?.services || []; }, [servicesResource.data]);
  const rows = useMemo(() => { const d = list.data; return !listPath || !d ? [] : Array.isArray(d) ? d : d.appointments || []; }, [list.data, listPath]);
  const visible = rows.filter(r => matchesAppointment(r, search) && (!staffOnly || !statusFilter || r.trangthai === statusFilter));
  const pageRows = visible.slice((page - 1) * PAGE, page * PAGE);
  const customerName = customerId ? rows.find(r => r.makh === customerId)?.khachhang_hoten : undefined;

  const [creating, setCreating] = useState(query.get('new') === '1');
  const [detail, setDetail] = useState<number | null>(null);
  const [changing, setChanging] = useState<number | null>(null);
  const [paying, setPaying] = useState<number | null>(null);
  const [receipt, setReceipt] = useState<number | null>(null);
  const [acting, setActing] = useState<string>('');
  const reload = () => { list.reload(); stats.reload(); setRevision(n => n + 1); };

  async function act(key: string, run: () => Promise<{ msg?: string }>, fallback: string) {
    if (acting) return;
    setActing(key);
    try { const result = await run(); message.success(result.msg || fallback); reload(); }
    catch (e) { message.error((e as Error).message); reload(); }
    finally { setActing(''); }
  }
  function confirmAction(row: AppointmentRow, kind: 'check-in' | 'confirm' | 'complete') {
    const texts = { 'check-in': ['Check-in khách', `Xác nhận khách đã đến: ${row.khachhang_hoten} – ${dateTime(row.ngaygio)}? Lịch chuyển sang "Đang thực hiện" và không còn bị tự hủy.`, 'Check-in'],
      confirm: ['Xác nhận lịch hẹn', `Xác nhận lịch #${row.malh} của ${row.khachhang_hoten}?`, 'Xác nhận'],
      complete: ['Hoàn thành lịch hẹn', `Khách ${row.khachhang_hoten} đã hoàn thành dịch vụ? Buổi gói đang giữ sẽ được trừ.`, 'Hoàn thành'] }[kind];
    modal.confirm({ title: texts[0], content: texts[1], okText: texts[2], cancelText: 'Quay lại',
      onOk: () => act(`${kind}-${row.malh}`, () => post(`/api/admin/appointments/${row.malh}/${kind}`, {}), texts[2]) });
  }
  function cancel(row: AppointmentRow) {
    let reason = '';
    modal.confirm({ title: `Hủy lịch #${row.malh}`, okText: 'Hủy lịch', okButtonProps: { danger: true }, cancelText: 'Quay lại', autoFocusButton: 'cancel',
      content: <><p>Lịch sẽ bị hủy và các buổi gói đang giữ được hoàn lại. Thao tác này không hoàn tác được.</p>
        <label>Lý do hủy (không bắt buộc)<Input.TextArea rows={3} maxLength={500} onChange={e => { reason = e.target.value; }} /></label></>,
      onOk: () => act(`cancel-${row.malh}`, () => post(`/api/admin/appointments/${row.malh}/cancel`, { reason: reason.trim() }), 'Đã hủy lịch hẹn') });
  }
  async function createInvoice(row: AppointmentRow) {
    if (acting) return;
    setActing(`invoice-${row.malh}`);
    try {
      const result = await post<{ invoice_id: number; msg: string }>(`/api/admin/appointments/${row.malh}/create-invoice`, {});
      message.success(result.msg); reload(); setPaying(result.invoice_id);
    } catch (e) {
      const err = e as ApiError;
      // An invoice created by an earlier (possibly lost) request is reused, never duplicated.
      if (err.data?.code === 'INVOICE_ALREADY_EXISTS' && err.data.invoice_id) { reload(); setPaying(Number(err.data.invoice_id)); }
      else message.error(err.message);
    } finally { setActing(''); }
  }
  const actions = (row: AppointmentRow) => {
    const p = row.permissions || {}; const busy = (k: string) => acting === `${k}-${row.malh}`;
    return <>
      {p.canCheckIn && <Button type="primary" size="small" loading={busy('check-in')} onClick={() => confirmAction(row, 'check-in')} aria-label={`Check-in lịch #${row.malh}`}>Check-in</Button>}
      {p.canConfirm && <Button type="primary" size="small" loading={busy('confirm')} onClick={() => confirmAction(row, 'confirm')}>Xác nhận</Button>}
      {p.canComplete && <Button size="small" loading={busy('complete')} onClick={() => confirmAction(row, 'complete')}>Hoàn thành</Button>}
      {p.canPayInvoice && row.invoice && <Button size="small" type="primary" onClick={() => setPaying(row.invoice!.mahd)}>Thu tiền</Button>}
      {p.canViewInvoice && row.invoice && <Button size="small" onClick={() => setReceipt(row.invoice!.mahd)}>Xem hóa đơn</Button>}
      {p.canCreateInvoice && <Button size="small" type="primary" loading={busy('invoice')} onClick={() => createInvoice(row)}>Tạo hóa đơn</Button>}
      {p.canChangeServices && <Button size="small" onClick={() => setChanging(row.malh)}>Đổi dịch vụ</Button>}
      {p.canCancel && <Button size="small" danger loading={busy('cancel')} onClick={() => cancel(row)}>Hủy</Button>}
      {p.canView && <Button size="small" onClick={() => setDetail(row.malh)} aria-label={`Xem chi tiết lịch #${row.malh}`}>Xem</Button>}
    </>;
  };
  const filtersActive = !!(range || statusFilter || search || customerId);
  const s = stats.data?.statistics;

  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">VẬN HÀNH</span><h1>{staffOnly ? 'Lịch hẹn của tôi' : 'Lịch hẹn'}</h1>
        <p>{staffOnly ? 'Các lịch khách đã được phân công cho bạn.' : 'Đặt lịch, đón khách, hoàn thành dịch vụ và thu tiền.'}</p></div>
      {desk && <Button type="primary" onClick={() => setCreating(true)} data-testid="appointment-new">+ Tạo lịch hẹn</Button>}
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Tổng lịch hẹn" value={s?.total ?? '…'} /></Card>
      <Card><Statistic title="Chờ xác nhận" value={s?.pending ?? '…'} /></Card>
      <Card><Statistic title="Đã xác nhận" value={s?.confirmed ?? '…'} /></Card>
      <Card><Statistic title="Chưa hoàn thành" value={s ? s.total - s.completed - s.cancelled : '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters">
        <Select aria-label="Khoảng thời gian" value={range} onChange={v => setQuery({ range: v || null, from: null, to: null, page: null })} options={RANGES} />
        {!staffOnly && <Select aria-label="Trạng thái" value={statusFilter} onChange={v => setQuery({ status: v || null, page: null })}
          options={[{ value: '', label: 'Tất cả trạng thái' }, ...Object.entries(statusLabel).map(([value, label]) => ({ value, label }))]} />}
        <Input.Search aria-label="Tìm lịch hẹn" placeholder="Tên, SĐT khách, mã lịch, dịch vụ…" allowClear value={searchDraft}
          onChange={e => { setSearchDraft(e.target.value); if (!e.target.value) setQuery({ q: null, page: null }, true); }}
          onSearch={v => setQuery({ q: v.trim() || null, page: null })} />
        <Button onClick={() => setQuery({ range: null, from: null, to: null, status: null, q: null, makh: null, page: null })} disabled={!filtersActive}>Xóa bộ lọc</Button>
      </div>
      {range === 'custom' && <form className="booking-custom-range" onSubmit={e => { e.preventDefault(); setQuery({ from: draftFrom || null, to: draftTo || null, page: null }); }}>
        <label>Từ ngày<Input type="date" value={draftFrom} max={draftTo || undefined} onChange={e => setDraftFrom(e.target.value)} /></label>
        <label>Đến ngày<Input type="date" value={draftTo} min={draftFrom || undefined} onChange={e => setDraftTo(e.target.value)} /></label>
        <Button htmlType="submit" type="primary" disabled={!draftFrom}>Lọc</Button>
      </form>}
      {customerId && <Alert className="section-title" type="info" showIcon message={`Đang xem lịch của khách ${customerName || `#${customerId}`}`}
        action={<Button size="small" onClick={() => setQuery({ makh: null, page: null })}>Xem tất cả khách</Button>} />}
      {dates === null && <Alert className="section-title" type="warning" showIcon message="Chọn ngày bắt đầu, và ngày kết thúc không trước ngày bắt đầu, rồi bấm Lọc." />}
      <p className="muted section-title" aria-live="polite">{visible.length} lịch hẹn{filtersActive ? ' · đang lọc' : ''}</p>
      {listPath && <ResourceState {...list} />}
      {listPath && !list.loading && !list.error && (!visible.length ? <Empty description={rows.length ? 'Không có lịch khớp bộ lọc' : 'Chưa có lịch hẹn trong khoảng này'} /> : <>
        <div className="desktop-table"><Table rowKey="malh" dataSource={pageRows} pagination={false} columns={[
          { title: 'Ngày giờ', dataIndex: 'ngaygio', render: (v: string, r: AppointmentRow) => <><strong>{dateTime(v)}</strong><div className="muted">#{r.malh}</div></>, width: 150 },
          { title: 'Khách hàng', render: (_: unknown, r: AppointmentRow) => <>{r.khachhang_hoten}<div className="muted">{r.khachhang_sdt || ''}</div></> },
          { title: 'Dịch vụ', dataIndex: 'dichvu_ten' }, { title: 'Nhân viên', dataIndex: 'nhanvien_hoten' },
          { title: 'Trạng thái', render: (_: unknown, r: AppointmentRow) => <Space direction="vertical" size={4}>{status(r)}{r.prepaid && <Tag color="green">Đã trả trước</Tag>}{paymentTag(r)}</Space> },
          { title: 'Thao tác', render: (_: unknown, r: AppointmentRow) => <Space wrap size={6}>{actions(r)}</Space>, width: 300 }]} /></div>
        <div className="mobile-cards">{pageRows.map(r => <Card key={r.malh} className="small-card appointment-card">
          <div className="card-head"><strong>{dateTime(r.ngaygio)} · #{r.malh}</strong><Space size={4} wrap>{status(r)}{r.prepaid && <Tag color="green">Đã trả trước</Tag>}{paymentTag(r)}</Space></div>
          <h2>{r.khachhang_hoten}</h2><p>{r.dichvu_ten}</p><p className="muted">{r.nhanvien_hoten}{r.khachhang_sdt ? ` · ${r.khachhang_sdt}` : ''}</p>
          <Space wrap size={6}>{actions(r)}</Space></Card>)}</div>
        {visible.length > PAGE && <Pagination className="pager" current={page} pageSize={PAGE} total={visible.length} showSizeChanger={false}
          onChange={n => setQuery({ page: n > 1 ? n : null })} />}
      </>)}
    </Card>
    {desk && <BookingDrawer open={creating} services={services} initialCustomer={customerId}
      onClose={() => { setCreating(false); if (query.get('new')) setQuery({ new: null }, true); }}
      onCreated={malh => { setCreating(false); if (query.get('new')) setQuery({ new: null }, true); reload(); setDetail(malh); }} />}
    <Detail malh={detail} revision={revision} onClose={() => setDetail(null)} actions={row => actions(row)} />
    <ChangeServices malh={changing} canUseTreatments={desk} services={services} onClose={() => setChanging(null)} onSaved={reload} />
    <InvoicePayment invoiceId={paying} onClose={() => { setPaying(null); reload(); }} onPaid={reload} />
    <ReceiptModal target={receipt !== null ? { kind: 'service', id: receipt } : null} onClose={() => setReceipt(null)} onPay={t => setPaying(t.id)} />
  </>;
}

export function AppointmentsGate({ me }: { me: Me }) {
  if (!['admin', 'manager', 'letan', 'staff'].includes(me.user.role)) return <Result status="403" title="Không có quyền xem lịch hẹn" />;
  return <Appointments me={me} />;
}
