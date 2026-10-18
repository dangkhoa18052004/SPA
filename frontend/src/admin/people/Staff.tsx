import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Rate, Result, Select, Space, Statistic, Switch, Table, Tag } from 'antd';
import { api, del, post, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { fold, vnd } from '../booking/model';
import { imageError } from '../catalog/model';
import { FilePick } from '../catalog/ui';
import { avatarUrl, roleLabels } from './model';
import type { Position, StaffMember } from './model';
import '../booking/booking.css';
import '../catalog/catalog.css';

type StaffValues = { hoten: string; taikhoan: string; matkhau?: string; email?: string; sdt?: string; macv: number; role: string; trangthai: boolean };
const roleTag = (role: string) => <Tag color={roleLabels[role]?.color}>{roleLabels[role]?.label || role}</Tag>;
const statusTag = (active: boolean) => <Tag color={active ? 'green' : 'default'}>{active ? 'Đang hoạt động' : 'Đã vô hiệu'}</Tag>;
const STEP_UP_NOTE = 'Thay đổi tài khoản, vai trò và trạng thái nhân viên cần xác minh hai bước; dữ liệu đang nhập được giữ trong lúc xác minh.';

function StaffForm({ editing, positions, onClose, onSaved }: { editing: StaffMember | 'new' | null; positions: Position[]; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm<StaffValues>();
  const { message, modal } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const isNew = editing === 'new';
  const current = editing && editing !== 'new' ? editing : null;
  useEffect(() => { setFile(null); setPreview(current ? avatarUrl(current.anhnhanvien) : avatarUrl(null)); }, [editing]);
  function close() {
    if (busy) return;
    if (!form.isFieldsTouched() && !file) { onClose(); return; }
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: onClose });
  }
  async function save(v: StaffValues) {
    const body = new FormData();
    body.append('hoten', v.hoten.trim()); body.append('taikhoan', v.taikhoan.trim()); body.append('email', v.email?.trim() || '');
    body.append('sdt', v.sdt?.trim() || ''); body.append('macv', String(v.macv)); body.append('role', v.role); body.append('trangthai', String(v.trangthai));
    if (isNew) body.append('matkhau', v.matkhau || '');
    if (file) body.append('anhnhanvien', file);
    setBusy(true);
    try {
      // The API asks for step-up verification; api() shows the dialog and resends this same form.
      const result = await api<{ msg: string }>(isNew ? '/api/admin/staff/add' : `/api/admin/staff/${current!.manv}`, { method: isNew ? 'POST' : 'PUT', body });
      message.success(result.msg); onSaved();
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  const initial: Partial<StaffValues> = current ? { hoten: current.hoten, taikhoan: current.taikhoan, email: current.email || '', sdt: current.sdt || '',
    macv: current.macv ?? positions.find(p => p.tencv === current.chucvu)?.macv, role: current.role, trangthai: current.trangthai } : { trangthai: true, role: 'staff' };
  return <Drawer open={editing !== null} onClose={close} width={560} destroyOnHidden maskClosable={!busy} title={isNew ? 'Thêm nhân viên' : `Sửa nhân viên #${current?.manv}`}
    footer={<Space><Button onClick={close} disabled={busy}>Hủy</Button><Button type="primary" loading={busy} onClick={() => form.submit()} data-testid="staff-save">Lưu</Button></Space>}>
    <Alert type="info" showIcon message={STEP_UP_NOTE} style={{ marginBottom: 16 }} />
    <Form form={form} layout="vertical" initialValues={initial} onFinish={save} disabled={busy}>
      <Form.Item label="Ảnh đại diện"><div className="catalog-image-field"><img src={preview} alt="" style={{ borderRadius: '50%', width: 90 }} />
        <FilePick accept="image/jpeg,image/png,image/webp" label="Ảnh nhân viên" onPick={f => { if (!f) return; const e = imageError(f); if (e) { message.error(e); return; } setFile(f); setPreview(URL.createObjectURL(f)); }} /></div></Form.Item>
      <Form.Item label="Họ tên" name="hoten" rules={[{ required: true, whitespace: true, message: 'Nhập họ tên' }, { max: 100 }]}><Input autoComplete="off" /></Form.Item>
      <div className="form-grid">
        <Form.Item label="Tài khoản đăng nhập" name="taikhoan" rules={[{ required: true, whitespace: true, message: 'Nhập tài khoản' }, { max: 50 }]}><Input autoComplete="off" /></Form.Item>
        {isNew && <Form.Item label="Mật khẩu" name="matkhau" rules={[{ required: true, message: 'Nhập mật khẩu' }, { min: 6, message: 'Ít nhất 6 ký tự' }]}><Input.Password autoComplete="new-password" /></Form.Item>}
      </div>
      <div className="form-grid">
        <Form.Item label="Email" name="email" rules={[{ type: 'email', message: 'Email chưa đúng định dạng' }]}><Input type="email" /></Form.Item>
        <Form.Item label="Số điện thoại" name="sdt" rules={[{ pattern: /^[0-9+ ]{8,15}$/, message: '8–15 chữ số' }]}><Input inputMode="tel" /></Form.Item>
      </div>
      <div className="form-grid">
        <Form.Item label="Chức vụ" name="macv" rules={[{ required: true, message: 'Chọn chức vụ' }]}>
          <Select aria-label="Chức vụ" options={positions.map(p => ({ value: p.macv, label: `${p.tencv} · ${vnd(p.dongiagio)}/giờ` }))} /></Form.Item>
        <Form.Item label="Vai trò (quyền)" name="role" rules={[{ required: true }]}>
          <Select aria-label="Vai trò" options={Object.entries(roleLabels).map(([value, r]) => ({ value, label: r.label }))} /></Form.Item>
      </div>
      <Form.Item label="Đang hoạt động" name="trangthai" valuePropName="checked" extra="Tắt để khóa đăng nhập; lịch sử công và lương vẫn giữ."><Switch /></Form.Item>
    </Form>
  </Drawer>;
}

function StaffList() {
  const { message, modal } = App.useApp();
  const [query, setQuery] = useQuery();
  const resource = useResource<StaffMember[]>('/api/admin/staff/list-all');
  const positions = useResource<Position[]>('/api/admin/roles');
  const role = query.get('role') || ''; const status = query.get('status') || ''; const search = query.get('q') || '';
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const [editing, setEditing] = useState<StaffMember | 'new' | null>(null);
  const [viewing, setViewing] = useState<StaffMember | null>(null);
  const all = resource.data || [];
  const tokens = fold(search).split(/\s+/).filter(Boolean);
  const rows = all.filter(s => (!role || s.role === role) && (!status || String(s.trangthai) === status)
    && tokens.every(t => fold(`${s.manv} ${s.hoten} ${s.taikhoan} ${s.email || ''} ${s.sdt || ''} ${s.chucvu}`).includes(t)))
    .sort((a, b) => Number(b.trangthai) - Number(a.trangthai) || a.hoten.localeCompare(b.hoten, 'vi'));
  function toggle(s: StaffMember) {
    const activate = !s.trangthai;
    modal.confirm({ title: `${activate ? 'Kích hoạt lại' : 'Vô hiệu hóa'} ${s.hoten}?`, okText: activate ? 'Kích hoạt' : 'Vô hiệu hóa', okButtonProps: { danger: !activate },
      content: activate ? 'Nhân viên đăng nhập lại được.' : 'Nhân viên không đăng nhập được và mọi phiên xác minh đang có bị hủy. Lịch sử công và lương vẫn giữ.',
      cancelText: 'Quay lại', autoFocusButton: 'cancel', onOk: async () => {
        try {
          if (activate) { const body = new FormData(); body.append('trangthai', 'true'); await api(`/api/admin/staff/${s.manv}`, { method: 'PUT', body }); }
          else await del(`/api/admin/staff/${s.manv}`);
          message.success(activate ? 'Đã kích hoạt lại tài khoản.' : 'Đã vô hiệu hóa tài khoản.'); resource.reload();
        } catch (e) { message.error((e as Error).message); }
      } });
  }
  const actions = (s: StaffMember) => <Space wrap size={6}><Button size="small" onClick={() => setViewing(s)}>Xem</Button><Button size="small" onClick={() => setEditing(s)}>Sửa</Button>
    <Button size="small" danger={s.trangthai} onClick={() => toggle(s)}>{s.trangthai ? 'Vô hiệu hóa' : 'Kích hoạt'}</Button></Space>;
  const rating = (s: StaffMember) => s.rating_count ? <span aria-label={`Điểm ${s.rating_average} trên 5 từ ${s.rating_count} đánh giá`}>★ {s.rating_average} <small className="muted">({s.rating_count})</small></span> : <span className="muted">Chưa có</span>;
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Nhân viên</h1><p>Tài khoản, chức vụ, vai trò và trạng thái của nhân viên.</p></div>
      <Button type="primary" onClick={() => setEditing('new')} data-testid="staff-new">+ Thêm nhân viên</Button>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Tổng nhân viên" value={resource.data ? all.length : '…'} /></Card>
      <Card><Statistic title="Đang hoạt động" value={resource.data ? all.filter(s => s.trangthai).length : '…'} /></Card>
      <Card><Statistic title="Kỹ thuật viên hoạt động" value={resource.data ? all.filter(s => s.trangthai && s.role === 'staff').length : '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters">
        <Select aria-label="Lọc theo vai trò" value={role} onChange={v => setQuery({ role: v || null })} options={[{ value: '', label: 'Tất cả vai trò' }, ...Object.entries(roleLabels).map(([value, r]) => ({ value, label: r.label }))]} />
        <Select aria-label="Lọc theo trạng thái tài khoản" value={status} onChange={v => setQuery({ status: v || null })} options={[{ value: '', label: 'Tất cả trạng thái' }, { value: 'true', label: 'Đang hoạt động' }, { value: 'false', label: 'Đã vô hiệu' }]} />
        <Input.Search aria-label="Tìm nhân viên" placeholder="Tên, tài khoản, email, SĐT, chức vụ" allowClear value={draft}
          onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ q: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null })} />
        <Button disabled={!role && !status && !search} onClick={() => setQuery({ role: null, status: null, q: null })}>Xóa bộ lọc</Button>
      </div>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Không tìm thấy nhân viên" /> : <>
        <div className="desktop-table section-title"><Table rowKey="manv" dataSource={rows} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
          { title: 'Nhân viên', render: (_: unknown, s: StaffMember) => <Space><img className="table-avatar" src={avatarUrl(s.anhnhanvien)} alt="" onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = avatarUrl(null); }} />
            <span><strong>{s.hoten}</strong><div className="muted">#{s.manv} · {s.taikhoan}</div></span></Space> },
          { title: 'Liên hệ', render: (_: unknown, s: StaffMember) => <>{s.sdt || '—'}<div className="muted">{s.email || ''}</div></> },
          { title: 'Chức vụ', dataIndex: 'chucvu' }, { title: 'Vai trò', dataIndex: 'role', render: roleTag }, { title: 'Đánh giá', render: (_: unknown, s: StaffMember) => rating(s) },
          { title: 'Trạng thái', dataIndex: 'trangthai', render: statusTag }, { title: 'Thao tác', render: (_: unknown, s: StaffMember) => actions(s) }]} /></div>
        <div className="mobile-cards section-title">{rows.map(s => <Card key={s.manv} className="small-card"><div className="card-head"><Space><img className="table-avatar" src={avatarUrl(s.anhnhanvien)} alt="" /><h2>{s.hoten}</h2></Space>{statusTag(s.trangthai)}</div>
          <p>{roleTag(s.role)} {s.chucvu} · {rating(s)}</p><p className="muted">{s.sdt || ''} {s.email || ''}</p>{actions(s)}</Card>)}</div>
      </>)}
    </Card>
    <Drawer open={!!viewing} onClose={() => setViewing(null)} width={480} title={viewing?.hoten} destroyOnHidden extra={viewing && <Button onClick={() => { setEditing(viewing); setViewing(null); }}>Sửa</Button>}>
      {viewing && <><div className="profile-head"><img className="profile-avatar" src={avatarUrl(viewing.anhnhanvien)} alt="" /><div><h2>{viewing.hoten}</h2>{roleTag(viewing.role)}{statusTag(viewing.trangthai)}</div></div>
        <Descriptions className="profile-details" column={1} size="small" items={[{ key: 'id', label: 'Mã', children: `#${viewing.manv}` }, { key: 'acc', label: 'Tài khoản', children: viewing.taikhoan },
          { key: 'pos', label: 'Chức vụ', children: viewing.chucvu }, { key: 'mail', label: 'Email', children: viewing.email || '—' }, { key: 'phone', label: 'SĐT', children: viewing.sdt || '—' },
          { key: 'rate', label: 'Đánh giá', children: viewing.rating_count ? <Space><Rate disabled allowHalf value={Number(viewing.rating_average)} />{viewing.rating_average} ({viewing.rating_count})</Space> : 'Chưa có' }]} /></>}
    </Drawer>
    <StaffForm key={editing === 'new' ? 'new' : editing?.manv ?? 'none'} editing={editing} positions={positions.data || []} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); resource.reload(); }} />
  </>;
}

function PositionForm({ editing, onClose, onSaved }: { editing: Position | 'new' | null; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm<{ tencv: string; dongiagio: number }>();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const current = editing && editing !== 'new' ? editing : null;
  async function save(v: { tencv: string; dongiagio: number }) {
    setBusy(true);
    try {
      const body = { tencv: v.tencv.trim(), dongiagio: v.dongiagio };
      const result = current ? await put<{ msg: string }>(`/api/admin/roles/${current.macv}`, body) : await post<{ msg: string }>('/api/admin/roles', body);
      message.success(result.msg); onSaved();
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  return <Modal open={editing !== null} title={current ? `Sửa chức vụ #${current.macv}` : 'Thêm chức vụ'} onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden>
    <Form form={form} layout="vertical" onFinish={save} disabled={busy} initialValues={current ? { tencv: current.tencv, dongiagio: Number(current.dongiagio) } : undefined}>
      <Form.Item label="Tên chức vụ" name="tencv" rules={[{ required: true, whitespace: true, message: 'Nhập tên chức vụ' }, { min: 2, max: 50 }]}><Input placeholder="Ví dụ: Kỹ thuật viên chính" /></Form.Item>
      <Form.Item label="Đơn giá theo giờ (VNĐ)" name="dongiagio" rules={[{ required: true, message: 'Nhập đơn giá' }]} extra="Dùng cho bảng lương theo giờ công đã duyệt. Thay đổi cần xác minh hai bước.">
        <InputNumber<number> min={0} max={10000000} step={1000} precision={0} style={{ width: '100%' }} formatter={v => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.')} parser={v => Number((v || '').replace(/\./g, ''))} /></Form.Item>
      <Space><Button onClick={onClose} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy} data-testid="position-save">Lưu</Button></Space>
    </Form>
  </Modal>;
}

function PositionList() {
  const { message, modal } = App.useApp();
  const resource = useResource<Position[]>('/api/admin/roles');
  const staff = useResource<StaffMember[]>('/api/admin/staff/list-all');
  const [editing, setEditing] = useState<Position | 'new' | null>(null);
  const [search, setSearch] = useState('');
  const count = (p: Position) => (staff.data || []).filter(s => (s.macv ?? null) === p.macv || (s.macv == null && s.chucvu === p.tencv)).length;
  const rows = (resource.data || []).filter(p => fold(`${p.macv} ${p.tencv} ${p.dongiagio}`).includes(fold(search.trim())));
  function remove(p: Position) {
    if (count(p)) { message.warning(`Còn ${count(p)} nhân viên giữ chức vụ này; hãy đổi chức vụ cho họ trước.`); return; }
    modal.confirm({ title: `Xóa chức vụ "${p.tencv}"?`, okText: 'Xóa', okButtonProps: { danger: true }, cancelText: 'Quay lại', autoFocusButton: 'cancel',
      onOk: async () => { try { const r = await del<{ msg: string }>(`/api/admin/roles/${p.macv}`); message.success(r.msg); resource.reload(); } catch (e) { message.error((e as Error).message); } } });
  }
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Chức vụ</h1><p>Tên chức vụ và đơn giá theo giờ dùng để tính lương.</p></div>
      <Button type="primary" onClick={() => setEditing('new')} data-testid="position-new">+ Thêm chức vụ</Button>
    </div>
    <Card>
      <Input.Search aria-label="Tìm chức vụ" placeholder="Tên chức vụ hoặc đơn giá" allowClear value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 420 }} />
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Chưa có chức vụ" /> :
        <Table className="section-title" rowKey="macv" dataSource={rows} pagination={false} scroll={{ x: 520 }} columns={[
          { title: 'Chức vụ', render: (_: unknown, p: Position) => <><strong>{p.tencv}</strong><div className="muted">#{p.macv}</div></> },
          { title: 'Đơn giá/giờ', align: 'right' as const, render: (_: unknown, p: Position) => vnd(p.dongiagio) },
          { title: 'Nhân viên', render: (_: unknown, p: Position) => staff.data ? count(p) : '…' },
          { title: 'Thao tác', render: (_: unknown, p: Position) => <Space wrap size={6}><Button size="small" onClick={() => setEditing(p)}>Sửa</Button><Button size="small" danger onClick={() => remove(p)}>Xóa</Button></Space> }]} />)}
    </Card>
    <PositionForm key={editing === 'new' ? 'new' : editing?.macv ?? 'none'} editing={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); resource.reload(); }} />
  </>;
}

export function Positions({ me }: { me: Me }) {
  return me.user.role === 'admin' ? <PositionList /> : <Result status="403" title="Chỉ quản trị viên quản lý chức vụ" />;
}

export default function Staff({ me }: { me: Me }) {
  return me.user.role === 'admin' ? <StaffList /> : <Result status="403" title="Chỉ quản trị viên quản lý nhân viên" />;
}
