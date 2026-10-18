import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Form, Input, Pagination, Result, Select, Skeleton, Space, Statistic, Table, Tabs, Tag } from 'antd';
import { api, patch, post, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { navigate, useQuery } from '../../router';
import type { Me } from '../../types';
import { QuickCustomer } from './BookingDrawer';
import { customerStatus, treatmentStatus, dateTime, dayLabel, matchesCustomer, statusColor, statusLabel } from './model';
import type { AppointmentRow, Customer, Treatment } from './model';
import './booking.css';

const PAGE = 10;
type CustomerDetail = Customer & { diachi: string | null; taikhoan: string };
type FormValues = { hoten: string; sdt: string; email?: string; taikhoan: string; diachi?: string; matkhau?: string; trangthai: string };
const avatar = (c: Customer) => c.anhdaidien ? `/api/profile/avatar/${encodeURIComponent(c.anhdaidien)}` : '/static/images/default-avatar.svg';
const statusTag = (value: string) => <Tag color={customerStatus[value]?.color}>{customerStatus[value]?.label || value}</Tag>;

function CustomerForm({ editing, onClose, onSaved }: { editing: CustomerDetail | 'new' | null; onClose: () => void; onSaved: (makh?: number) => void }) {
  const [form] = Form.useForm<FormValues>();
  const { message, modal } = App.useApp();
  const [busy, setBusy] = useState(false);
  const isNew = editing === 'new';
  function close() {
    if (busy) return;
    if (!form.isFieldsTouched()) { onClose(); return; }
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: onClose });
  }
  async function save(values: FormValues) {
    setBusy(true);
    const body = { ...values, hoten: values.hoten.trim(), sdt: values.sdt.trim(), taikhoan: values.taikhoan.trim(), email: values.email?.trim() || null, diachi: values.diachi?.trim() || '' };
    if (!isNew && !body.matkhau) delete body.matkhau;
    try {
      const result = isNew ? await post<{ msg: string; makh?: number }>('/api/admin/customers/add', body)
        : await put<{ msg: string; makh?: number }>(`/api/admin/customers/edit/${(editing as CustomerDetail).makh}`, body);
      message.success(result.msg); onSaved(result.makh);
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  const initial = editing && editing !== 'new' ? { hoten: editing.hoten, sdt: editing.sdt || '', email: editing.email || '', taikhoan: editing.taikhoan,
    diachi: editing.diachi || '', trangthai: editing.trangthai } : { trangthai: 'active' };
  return <Drawer open={editing !== null} onClose={close} width={520} destroyOnHidden maskClosable={!busy} title={isNew ? 'Thêm khách hàng' : 'Sửa thông tin khách hàng'}>
    <Form form={form} layout="vertical" initialValues={initial} onFinish={save} disabled={busy}>
      <Form.Item label="Họ tên" name="hoten" rules={[{ required: true, whitespace: true, message: 'Nhập họ tên' }, { max: 100 }]}><Input /></Form.Item>
      <div className="form-grid">
        <Form.Item label="Số điện thoại" name="sdt" rules={[{ required: true, message: 'Nhập số điện thoại' }, { pattern: /^[0-9+ ]{8,15}$/, message: '8–15 chữ số' }]}><Input inputMode="tel" /></Form.Item>
        <Form.Item label="Email" name="email" rules={[{ type: 'email', message: 'Email chưa đúng định dạng' }]}><Input type="email" /></Form.Item>
      </div>
      <Form.Item label="Tên tài khoản" name="taikhoan" rules={[{ required: true, whitespace: true, message: 'Nhập tên tài khoản' }, { max: 50 }]}><Input autoComplete="off" /></Form.Item>
      <Form.Item label="Địa chỉ" name="diachi"><Input /></Form.Item>
      <div className="form-grid">
        <Form.Item label={isNew ? 'Mật khẩu' : 'Mật khẩu mới'} name="matkhau" extra={isNew ? undefined : 'Bỏ trống nếu không đổi'}
          rules={isNew ? [{ required: true, message: 'Nhập mật khẩu' }, { min: 6, message: 'Ít nhất 6 ký tự' }] : [{ min: 6, message: 'Ít nhất 6 ký tự' }]}>
          <Input.Password autoComplete="new-password" /></Form.Item>
        <Form.Item label="Trạng thái" name="trangthai" rules={[{ required: true }]}>
          <Select options={Object.entries(customerStatus).map(([value, s]) => ({ value, label: s.label }))} /></Form.Item>
      </div>
      <Space><Button onClick={close} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy}>Lưu</Button></Space>
    </Form>
  </Drawer>;
}

/** Profile: contact details, appointment history and treatments — each tab only calls APIs this role may use. */
function Profile({ makh, revision, me, onClose, onEdit }: { makh: number | null; revision: number; me: Me; onClose: () => void; onEdit: (c: CustomerDetail) => void }) {
  const [data, setData] = useState<CustomerDetail>();
  const [error, setError] = useState('');
  const [appointments, setAppointments] = useState<AppointmentRow[]>();
  const [treatments, setTreatments] = useState<Treatment[]>();
  const [tabError, setTabError] = useState('');
  const canManage = ['admin', 'manager'].includes(me.user.role);
  useEffect(() => {
    let active = true; setData(undefined); setError(''); setAppointments(undefined); setTreatments(undefined); setTabError('');
    if (makh === null) return;
    api<CustomerDetail>(`/api/admin/customers/detail/${makh}`).then(d => { if (active) setData(d); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [makh, revision]);
  async function load(tab: string) {
    if (makh === null) return;
    try {
      if (tab === 'appointments' && !appointments) setAppointments(await api<AppointmentRow[]>(`/api/admin/appointments?makh=${makh}`));
      if (tab === 'treatments' && !treatments) setTreatments((await api<{ treatments: Treatment[] }>(`/api/admin/appointments/customers/${makh}/treatments`)).treatments);
    } catch (e) { setTabError((e as Error).message); }
  }
  return <Drawer open={makh !== null} onClose={onClose} width={620} title="Hồ sơ khách hàng" destroyOnHidden>
    {error ? <Alert type="error" showIcon message={error} /> : !data ? <Skeleton active /> : <>
      <div className="profile-head"><img className="profile-avatar" src={avatar(data)} alt="" onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = '/static/images/default-avatar.svg'; }} />
        <div><h2>{data.hoten}</h2><p className="muted">#{data.makh} · {data.sdt || 'Chưa có SĐT'}</p>{statusTag(data.trangthai)}</div></div>
      <Space wrap className="section-title">
        <Button type="primary" onClick={() => navigate(`/admin/appointments?makh=${data.makh}&new=1`)}>Đặt lịch cho khách</Button>
        <Button onClick={() => navigate(`/admin/appointments?makh=${data.makh}`)}>Mở trong Lịch hẹn</Button>
        {canManage && <Button onClick={() => onEdit(data)}>Sửa thông tin</Button>}
      </Space>
      <Tabs className="section-title" onChange={key => { setTabError(''); void load(key); }} items={[
        { key: 'info', label: 'Thông tin', children: <Descriptions column={1} size="small" items={[
          { key: 'email', label: 'Email', children: data.email || 'Chưa có' }, { key: 'account', label: 'Tài khoản', children: data.taikhoan },
          { key: 'address', label: 'Địa chỉ', children: data.diachi || 'Chưa có' }]} /> },
        { key: 'appointments', label: 'Lịch hẹn', children: tabError ? <Alert type="error" showIcon message={tabError} /> : !appointments ? <Skeleton active /> : !appointments.length
          ? <Empty description="Khách chưa có lịch hẹn" /> : <ul className="history-list">{appointments.slice(0, 30).map(a => <li key={a.malh}>
            <div><strong>{dateTime(a.ngaygio)}</strong> · #{a.malh}<div className="muted">{a.dichvu_ten} · {a.nhanvien_hoten}</div></div>
            <Space size={4} wrap><Tag color={statusColor[a.trangthai]}>{statusLabel[a.trangthai] || a.trangthai_vi}</Tag>{a.payment_status && <Tag>{a.payment_status}</Tag>}</Space></li>)}</ul> },
        { key: 'treatments', label: 'Liệu trình', children: tabError ? <Alert type="error" showIcon message={tabError} /> : !treatments ? <Skeleton active /> : !treatments.length
          ? <Empty description="Khách chưa có gói/liệu trình" /> : treatments.map(t => <Card key={t.mathe} size="small" className="small-card" title={`${t.tengoi} · #${t.mathe}`}
            extra={<Tag color={treatmentStatus[t.status]?.color}>{treatmentStatus[t.status]?.label || t.status}</Tag>}>{t.items.map(i => <div key={i.id} className="ledger-row"><div><strong>{i.tendv}</strong>{i.source_type === 'gift' && <Tag color="magenta">Spa tặng</Tag>}
              <p>Còn {i.available_sessions}/{i.total_sessions ?? '—'} · Đã dùng {i.consumed ?? 0} · Đang giữ {i.reserved ?? 0}</p></div>
              <small className="muted">{i.effective_expires_at ? `Hạn ${dayLabel(i.effective_expires_at)}` : 'Không giới hạn'}</small></div>)}</Card>) }]} />
    </>}
  </Drawer>;
}

/**
 * Customer list for the desk. Buttons follow the server's real permissions: quick add for
 * admin/manager/front desk, full add/edit/lock for admin and manager.
 */
export default function Customers({ me }: { me: Me }) {
  if (!['admin', 'manager', 'letan'].includes(me.user.role)) return <Result status="403" title="Không có quyền xem danh sách khách hàng" />;
  return <CustomerList me={me} />;
}

function CustomerList({ me }: { me: Me }) {
  const { message, modal } = App.useApp();
  const [query, setQuery] = useQuery();
  const resource = useResource<Customer[]>('/api/admin/customers/list');
  const canManage = ['admin', 'manager'].includes(me.user.role);
  const canQuick = canManage || me.user.role === 'letan';
  const statusFilter = query.get('status') || '';
  const search = query.get('q') || '';
  const page = Math.max(1, Number(query.get('page')) || 1);
  const viewing = Number(query.get('view')) || null;
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const [editing, setEditing] = useState<CustomerDetail | 'new' | null>(null);
  const [quick, setQuick] = useState(false);
  const [revision, setRevision] = useState(0);
  const rows = (resource.data || []).filter(c => (!statusFilter || c.trangthai === statusFilter) && matchesCustomer(c, search))
    .sort((a, b) => b.makh - a.makh);
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);
  async function openEdit(makh: number) {
    try { setEditing(await api<CustomerDetail>(`/api/admin/customers/detail/${makh}`)); } catch (e) { message.error((e as Error).message); }
  }
  function toggleLock(c: Customer) {
    const lock = c.trangthai !== 'blocked';
    modal.confirm({ title: `${lock ? 'Khóa' : 'Mở khóa'} khách hàng #${c.makh}?`, content: lock ? `${c.hoten} sẽ không đăng nhập và đặt lịch trực tuyến được cho đến khi mở khóa.` : `${c.hoten} sẽ dùng lại được tài khoản.`,
      okText: lock ? 'Khóa' : 'Mở khóa', okButtonProps: { danger: lock }, cancelText: 'Quay lại', autoFocusButton: 'cancel',
      onOk: async () => { try { const r = await patch<{ msg: string }>(`/api/admin/customers/update-status/${c.makh}`, { trangthai: lock ? 'blocked' : 'active' });
        message.success(r.msg); resource.reload(); } catch (e) { message.error((e as Error).message); } } });
  }
  const actions = (c: Customer) => <Space wrap size={6}>
    <Button size="small" onClick={() => setQuery({ view: c.makh })}>Hồ sơ</Button>
    <Button size="small" onClick={() => navigate(`/admin/appointments?makh=${c.makh}`)}>Lịch hẹn</Button>
    {canManage && <Button size="small" onClick={() => openEdit(c.makh)}>Sửa</Button>}
    {canManage && <Button size="small" danger={c.trangthai !== 'blocked'} onClick={() => toggleLock(c)}>{c.trangthai === 'blocked' ? 'Mở khóa' : 'Khóa'}</Button>}
  </Space>;
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">VẬN HÀNH</span><h1>Khách hàng</h1><p>Tìm khách, thêm khách mới và xem lịch sử phục vụ.</p></div>
      <Space wrap>{canQuick && <Button onClick={() => setQuick(true)}>+ Khách vãng lai</Button>}{canManage && <Button type="primary" onClick={() => setEditing('new')}>+ Thêm khách hàng</Button>}</Space>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Tổng khách hàng" value={resource.data?.length ?? '…'} /></Card>
      <Card><Statistic title="Đang hoạt động" value={resource.data?.filter(c => c.trangthai === 'active').length ?? '…'} /></Card>
      <Card><Statistic title="Đã khóa" value={resource.data?.filter(c => c.trangthai === 'blocked').length ?? '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters customers">
        <Select aria-label="Trạng thái khách" value={statusFilter} onChange={v => setQuery({ status: v || null, page: null })}
          options={[{ value: '', label: 'Tất cả trạng thái' }, ...Object.entries(customerStatus).map(([value, s]) => ({ value, label: s.label }))]} />
        <Input.Search aria-label="Tìm khách hàng" placeholder="Tên, SĐT, email, mã khách…" allowClear value={draft}
          onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ q: null, page: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null, page: null })} />
        <Button onClick={() => setQuery({ status: null, q: null, page: null })} disabled={!statusFilter && !search}>Xóa bộ lọc</Button>
      </div>
      <p className="muted section-title" aria-live="polite">{rows.length} khách hàng{statusFilter || search ? ' · đang lọc' : ''}</p>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty description="Không tìm thấy khách hàng" /> : <>
        <div className="desktop-table"><Table rowKey="makh" dataSource={pageRows} pagination={false} columns={[
          { title: 'Khách hàng', render: (_: unknown, c: Customer) => <Space><img className="table-avatar" src={avatar(c)} alt="" onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = '/static/images/default-avatar.svg'; }} />
            <span><strong>{c.hoten}</strong><div className="muted">#{c.makh}</div></span></Space> },
          { title: 'Điện thoại', dataIndex: 'sdt', render: (v: string | null) => v || '—' }, { title: 'Email', dataIndex: 'email', render: (v: string | null) => v || '—' },
          { title: 'Trạng thái', dataIndex: 'trangthai', render: statusTag }, { title: 'Thao tác', render: (_: unknown, c: Customer) => actions(c), width: 300 }]} /></div>
        <div className="mobile-cards">{pageRows.map(c => <Card key={c.makh} className="small-card"><div className="card-head"><h2>{c.hoten}</h2>{statusTag(c.trangthai)}</div>
          <p>{c.sdt || 'Chưa có SĐT'}{c.email ? ` · ${c.email}` : ''}</p>{actions(c)}</Card>)}</div>
        {rows.length > PAGE && <Pagination className="pager" current={page} pageSize={PAGE} total={rows.length} showSizeChanger={false} onChange={n => setQuery({ page: n > 1 ? n : null })} />}
      </>)}
    </Card>
    <Profile makh={viewing} revision={revision} me={me} onClose={() => setQuery({ view: null })} onEdit={c => setEditing(c)} />
    <CustomerForm key={editing === 'new' ? 'new' : editing?.makh ?? 'none'} editing={editing} onClose={() => setEditing(null)}
      onSaved={makh => { setEditing(null); resource.reload(); setRevision(n => n + 1); if (makh) setQuery({ view: makh }); }} />
    <QuickCustomer open={quick} onClose={() => setQuick(false)} onCreated={makh => { setQuick(false); resource.reload(); setQuery({ view: makh }); }} />
  </>;
}
