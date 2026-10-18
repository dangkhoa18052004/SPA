import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Drawer, Empty, Form, Input, Modal, Result, Select, Space, Statistic, Table, Tag, TimePicker } from 'antd';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import { api, post, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { spaToday } from '../booking/model';
import { addDays, dmy, overnight, shiftHours, weekdayLabel, weekStart } from './model';
import type { Registration, ShiftRow, StaffMember } from './model';
import '../booking/booking.css';

const manage = (me: Me) => ['admin', 'manager'].includes(me.user.role);
const when = (s: { ngay: string; start_time: string; end_time: string }) => `${weekdayLabel(s.ngay)} ${dmy(s.ngay)} · ${s.start_time}–${s.end_time}${overnight(s.start_time, s.end_time) ? ' (hôm sau)' : ''}`;

function ShiftForm({ editing, onClose, onSaved }: { editing: ShiftRow | 'new' | null; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm<{ ngay: string; start: Dayjs; end: Dayjs }>();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const current = editing && editing !== 'new' ? editing : null;
  const start = Form.useWatch('start', form); const end = Form.useWatch('end', form);
  const hours = start && end ? shiftHours(start.format('HH:mm'), end.format('HH:mm')) : null;
  async function save(v: { ngay: string; start: Dayjs; end: Dayjs }) {
    const body = { ngay: v.ngay, giobatdau: v.start.format('HH:mm'), gioketthuc: v.end.format('HH:mm') };
    setBusy(true);
    try {
      const result = current ? await put<{ msg: string }>(`/api/admin/shifts/${current.maca}`, body) : await post<{ msg: string }>('/api/admin/shifts', body);
      message.success(result.msg); onSaved();
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  return <Modal open={editing !== null} title={current ? `Sửa ca #${current.maca}` : 'Tạo ca làm'} onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden>
    <Form form={form} layout="vertical" onFinish={save} disabled={busy} initialValues={current
      ? { ngay: current.ngay, start: dayjs(current.start_time, 'HH:mm'), end: dayjs(current.end_time, 'HH:mm') }
      : { ngay: spaToday(), start: dayjs('09:00', 'HH:mm'), end: dayjs('18:00', 'HH:mm') }}>
      <Form.Item label="Ngày" name="ngay" rules={[{ required: true, message: 'Chọn ngày' }]}><Input type="date" aria-label="Ngày ca" /></Form.Item>
      <div className="form-grid">
        <Form.Item label="Bắt đầu" name="start" rules={[{ required: true, message: 'Chọn giờ' }]}><TimePicker format="HH:mm" minuteStep={15} needConfirm={false} style={{ width: '100%' }} aria-label="Giờ bắt đầu" /></Form.Item>
        <Form.Item label="Kết thúc" name="end" rules={[{ required: true, message: 'Chọn giờ' }]}><TimePicker format="HH:mm" minuteStep={15} needConfirm={false} style={{ width: '100%' }} aria-label="Giờ kết thúc" /></Form.Item>
      </div>
      {hours !== null && <Alert showIcon type={overnight(start!.format('HH:mm'), end!.format('HH:mm')) ? 'warning' : 'info'} style={{ marginBottom: 16 }}
        message={`${hours} giờ${overnight(start!.format('HH:mm'), end!.format('HH:mm')) ? ' · ca qua đêm, kết thúc ngày hôm sau' : ''}`} />}
      <p className="muted">Ca thuộc kỳ công đã khóa không sửa được. Công chỉ được trả theo giờ chấm công đã duyệt.</p>
      <Space><Button onClick={onClose} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy} data-testid="shift-save">Lưu</Button></Space>
    </Form>
  </Modal>;
}

function ShiftDetail({ shift, staff, onClose, onChanged }: { shift: ShiftRow | null; staff: StaffMember[]; onClose: () => void; onChanged: () => void }) {
  const { message, modal } = App.useApp();
  const [pick, setPick] = useState<number>();
  const [busy, setBusy] = useState(false);
  useEffect(() => setPick(undefined), [shift?.maca]);
  if (!shift) return <Drawer open={false} />;
  const assignedIds = new Set(shift.assigned_staff.map(s => s.manv));
  const candidates = staff.filter(s => s.trangthai && !assignedIds.has(s.manv) && s.role !== 'admin');
  async function assign() {
    if (!pick || busy) return;
    setBusy(true);
    try { const r = await post<{ msg: string }>('/api/admin/shifts/assign', { maca: shift!.maca, manv: pick }); message.success(r.msg); setPick(undefined); onChanged(); }
    catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  function unassign(person: ShiftRow['assigned_staff'][number]) {
    modal.confirm({ title: `Bỏ ${person.hoten} khỏi ca #${shift!.maca}?`, content: 'Nhân viên sẽ không chấm công được cho ca này nữa.', okText: 'Bỏ phân ca', okButtonProps: { danger: true },
      cancelText: 'Quay lại', autoFocusButton: 'cancel', onOk: async () => {
        try { const r = await api<{ msg: string }>('/api/admin/shifts/unassign', { method: 'DELETE', body: JSON.stringify({ maca: shift!.maca, manv: person.manv }) }); message.success(r.msg); onChanged(); }
        catch (e) { message.error((e as Error).message); } } });
  }
  return <Drawer open onClose={onClose} width={520} title={`Ca #${shift.maca}`} destroyOnHidden>
    <p><strong>{when(shift)}</strong> · {Number(shift.sogio ?? shiftHours(shift.start_time, shift.end_time)).toFixed(1)} giờ</p>
    <h3 className="section-title">Nhân viên trong ca ({shift.assigned_staff.length})</h3>
    {!shift.assigned_staff.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa phân nhân viên" /> :
      <ul className="history-list">{shift.assigned_staff.map(p => <li key={p.manv}><span><strong>{p.hoten}</strong> <span className="muted">{p.chucvu}</span></span>
        <Button size="small" danger onClick={() => unassign(p)}>Bỏ phân ca</Button></li>)}</ul>}
    <h3 className="section-title">Phân thêm nhân viên</h3>
    <Space.Compact block><Select showSearch aria-label="Nhân viên cần phân" placeholder={candidates.length ? 'Chọn nhân viên' : 'Đã phân hết nhân viên đang hoạt động'} value={pick} onChange={setPick}
      optionFilterProp="label" options={candidates.map(s => ({ value: s.manv, label: `${s.hoten} · ${s.chucvu}` }))} style={{ width: '100%' }} disabled={!candidates.length} />
      <Button type="primary" onClick={assign} loading={busy} disabled={!pick}>Phân ca</Button></Space.Compact>
    <p className="muted section-title">Nhân viên được báo qua email nếu có địa chỉ email.</p>
  </Drawer>;
}

function ShiftList({ me }: { me: Me }) {
  const { message, modal } = App.useApp();
  const [query, setQuery] = useQuery();
  const today = spaToday();
  const from = query.get('from') ?? weekStart(today); const to = query.get('to') ?? addDays(weekStart(today), 13);
  const assignment = query.get('assignment') || '';
  const [draftFrom, setDraftFrom] = useState(from); const [draftTo, setDraftTo] = useState(to);
  useEffect(() => { setDraftFrom(from); setDraftTo(to); }, [from, to]);
  const params = new URLSearchParams({ ...(from ? { date_from: from } : {}), ...(to ? { date_to: to } : {}), ...(assignment ? { assignment } : {}) });
  const resource = useResource<ShiftRow[]>(`/api/admin/shifts?${params}`);
  const staff = useResource<StaffMember[]>('/api/admin/staff/list-all');
  const pending = useResource<Registration[]>('/api/admin/shifts/registrations/pending');
  const [editing, setEditing] = useState<ShiftRow | 'new' | null>(null);
  const viewingId = Number(query.get('maca')) || null;
  const rows = [...(resource.data || [])].sort((a, b) => a.ngay.localeCompare(b.ngay) || a.start_time.localeCompare(b.start_time));
  const viewing = rows.find(s => s.maca === viewingId) || null;
  function remove(s: ShiftRow) {
    modal.confirm({ title: `Xóa ca #${s.maca}?`, content: s.assigned_staff.length ? `Ca đang có ${s.assigned_staff.length} nhân viên; họ sẽ bị bỏ khỏi ca và đăng ký liên quan bị xóa.` : 'Đăng ký liên quan cũng bị xóa.',
      okText: 'Xóa ca', okButtonProps: { danger: true }, cancelText: 'Quay lại', autoFocusButton: 'cancel',
      onOk: async () => { try { const r = await api<{ msg: string }>(`/api/admin/shifts/${s.maca}`, { method: 'DELETE' }); message.success(r.msg); resource.reload(); } catch (e) { message.error((e as Error).message); } } });
  }
  const actions = (s: ShiftRow) => <Space wrap size={6}><Button size="small" type="primary" onClick={() => setQuery({ maca: s.maca })}>Phân ca</Button>
    <Button size="small" onClick={() => setEditing(s)}>Sửa</Button><Button size="small" danger onClick={() => remove(s)}>Xóa</Button></Space>;
  const staffCell = (s: ShiftRow) => s.assigned_staff.length ? s.assigned_staff.map(p => p.hoten).join(', ') : <Tag color="orange">Chưa có nhân viên</Tag>;
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Ca làm</h1><p>Tạo ca, phân nhân viên và duyệt đăng ký. Nhân viên chỉ chấm công được ca của mình.</p></div>
      <Space wrap><Button href="/admin/approve-shifts">Duyệt đăng ký{pending.data?.length ? ` (${pending.data.length})` : ''}</Button><Button type="primary" onClick={() => setEditing('new')} data-testid="shift-new">+ Tạo ca</Button></Space>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Ca trong khoảng" value={resource.data ? rows.length : '…'} /></Card>
      <Card><Statistic title="Chưa có nhân viên" value={resource.data ? rows.filter(s => !s.assigned_staff.length).length : '…'} /></Card>
      <Card><Statistic title="Đăng ký chờ duyệt" value={pending.data ? pending.data.length : '…'} /></Card>
    </div>
    <Card className="section-title">
      <form className="booking-custom-range" onSubmit={e => { e.preventDefault(); setQuery({ from: draftFrom, to: draftTo }); }}>
        <label>Từ ngày<Input type="date" value={draftFrom} max={draftTo || undefined} onChange={e => setDraftFrom(e.target.value)} aria-label="Từ ngày" /></label>
        <label>Đến ngày<Input type="date" value={draftTo} min={draftFrom || undefined} onChange={e => setDraftTo(e.target.value)} aria-label="Đến ngày" /></label>
        <label>Phân ca<Select aria-label="Tình trạng phân ca" value={assignment} onChange={v => setQuery({ assignment: v || null })} style={{ minWidth: 180 }}
          options={[{ value: '', label: 'Tất cả' }, { value: 'unassigned', label: 'Chưa có nhân viên' }, { value: 'assigned', label: 'Đã có nhân viên' }]} /></label>
        <Button htmlType="submit" type="primary">Lọc</Button>
        <Button onClick={() => setQuery({ from: weekStart(addDays(from || today, -7)), to: addDays(weekStart(addDays(from || today, -7)), 6) })}>‹ Tuần trước</Button>
        <Button onClick={() => setQuery({ from: weekStart(addDays(from || today, 7)), to: addDays(weekStart(addDays(from || today, 7)), 6) })}>Tuần sau ›</Button>
        <Button onClick={() => setQuery({ from: null, to: null, assignment: null })}>Hai tuần này</Button>
      </form>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Không có ca trong khoảng này" /> : <>
        <div className="desktop-table section-title"><Table rowKey="maca" dataSource={rows} pagination={{ pageSize: 20, showSizeChanger: false }} columns={[
          { title: 'Ca', render: (_: unknown, s: ShiftRow) => <><strong>{when(s)}</strong><div className="muted">#{s.maca} · {Number(s.sogio ?? 0).toFixed(1)} giờ</div></> },
          { title: 'Nhân viên', render: (_: unknown, s: ShiftRow) => staffCell(s) }, { title: 'Thao tác', render: (_: unknown, s: ShiftRow) => actions(s), width: 240 }]} /></div>
        <div className="mobile-cards section-title">{rows.map(s => <Card key={s.maca} className="small-card"><strong>{when(s)}</strong><p className="muted">#{s.maca} · {Number(s.sogio ?? 0).toFixed(1)} giờ</p><p>{staffCell(s)}</p>{actions(s)}</Card>)}</div>
      </>)}
    </Card>
    <ShiftForm key={editing === 'new' ? 'new' : editing?.maca ?? 'none'} editing={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); resource.reload(); }} />
    <ShiftDetail shift={viewing} staff={staff.data || []} onClose={() => setQuery({ maca: null })} onChanged={resource.reload} />
    {!manage(me) && null}
  </>;
}

function ApproveList() {
  const { message, modal } = App.useApp();
  const resource = useResource<Registration[]>('/api/admin/shifts/registrations/pending');
  const [busy, setBusy] = useState<number | null>(null);
  async function decide(r: Registration, action: 'approve' | 'reject') {
    setBusy(r.reg_id);
    try { const result = await put<{ msg: string }>(`/api/admin/shifts/registrations/${r.reg_id}/${action}`, {}); message.success(result.msg); resource.reload(); }
    catch (e) { message.error((e as Error).message); resource.reload(); } finally { setBusy(null); }
  }
  const actions = (r: Registration) => <Space wrap size={6}><Button size="small" type="primary" loading={busy === r.reg_id} onClick={() => decide(r, 'approve')}>Duyệt</Button>
    <Button size="small" danger disabled={busy === r.reg_id} onClick={() => modal.confirm({ title: `Từ chối đăng ký của ${r.nhanvien.hoten}?`, okText: 'Từ chối', okButtonProps: { danger: true },
      cancelText: 'Quay lại', onOk: () => decide(r, 'reject') })}>Từ chối</Button></Space>;
  const rows = resource.data || [];
  const shift = (r: Registration) => when({ ngay: r.calam.ngay, start_time: r.calam.giobatdau, end_time: r.calam.gioketthuc });
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Duyệt đăng ký ca</h1><p>Duyệt thì nhân viên được phân vào ca và chấm công được ca đó.</p></div>
      <Button href="/admin/shifts">Quản lý ca làm</Button>
    </div>
    <Card>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty description="Không có đăng ký nào chờ duyệt" /> : <>
        <div className="desktop-table"><Table rowKey="reg_id" dataSource={rows} pagination={false} columns={[
          { title: 'Nhân viên', render: (_: unknown, r: Registration) => <strong>{r.nhanvien.hoten}</strong> },
          { title: 'Ca', render: (_: unknown, r: Registration) => <>{shift(r)}<div className="muted">#{r.calam.maca}</div></> },
          { title: 'Gửi lúc', render: (_: unknown, r: Registration) => new Date(r.ngaydangky).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }) },
          { title: 'Thao tác', render: (_: unknown, r: Registration) => actions(r) }]} /></div>
        <div className="mobile-cards">{rows.map(r => <Card key={r.reg_id} className="small-card"><h2>{r.nhanvien.hoten}</h2><p>{shift(r)}</p>{actions(r)}</Card>)}</div>
      </>)}
    </Card>
  </>;
}

export function ApproveShifts({ me }: { me: Me }) {
  return manage(me) ? <ApproveList /> : <Result status="403" title="Chỉ quản lý duyệt đăng ký ca" />;
}

export default function Shifts({ me }: { me: Me }) {
  return manage(me) ? <ShiftList me={me} /> : <Result status="403" title="Chỉ quản lý tạo và phân ca" extra={<Button href="/admin/register-shift">Đăng ký ca</Button>} />;
}
