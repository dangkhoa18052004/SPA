import { useRef, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Form, Input, Space, Tabs } from 'antd';
import { put, upload } from '../api';
import { ResourceState, useResource } from '../components';
import { useQuery } from '../router';
import type { Me } from '../types';
import { roleLabel } from './navigation';

type StaffProfile = { manv: number; hoten: string; sdt: string | null; diachi: string | null; email: string | null;
  taikhoan: string; anhnhanvien: string | null; role: string; chucvu: string | null };
type Editable = Pick<StaffProfile, 'hoten' | 'sdt' | 'email' | 'diachi'>;
const avatarUrl = (file: string | null) => file ? `/api/profile/avatar/${encodeURIComponent(file)}` : '/static/images/default-avatar.svg';

function EditProfile({ profile, open, onClose, onSaved }: { profile: StaffProfile; open: boolean; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm<Editable>();
  const { message, modal } = App.useApp();
  const [busy, setBusy] = useState(false);
  function close() {
    if (busy) return;
    if (!form.isFieldsTouched()) { onClose(); return; }
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: onClose });
  }
  async function save(values: Editable) {
    setBusy(true);
    try {
      const result = await put<{ message?: string }>('/api/profile/update', values);
      message.success(result.message || 'Đã cập nhật thông tin.'); onSaved();
    } catch (e) { message.error((e as Error).message); }
    finally { setBusy(false); }
  }
  return <Drawer title="Sửa thông tin cá nhân" open={open} onClose={close} width={480} destroyOnHidden maskClosable={!busy}>
    <Form form={form} layout="vertical" className="profile-form" disabled={busy} onFinish={save}
      initialValues={{ hoten: profile.hoten, sdt: profile.sdt || '', email: profile.email || '', diachi: profile.diachi || '' }}>
      <Form.Item label="Họ tên" name="hoten" rules={[{ required: true, whitespace: true, message: 'Nhập họ tên' }, { max: 100 }]}><Input autoComplete="name" /></Form.Item>
      <Form.Item label="Số điện thoại" name="sdt" rules={[{ pattern: /^[0-9+ ]{8,15}$/, message: 'Số điện thoại gồm 8–15 chữ số' }]}><Input inputMode="tel" autoComplete="tel" /></Form.Item>
      <Form.Item label="Email" name="email" rules={[{ type: 'email', message: 'Email chưa đúng định dạng' }]}><Input type="email" autoComplete="email" /></Form.Item>
      <Form.Item label="Địa chỉ" name="diachi" rules={[{ max: 255 }]}><Input.TextArea rows={2} autoComplete="street-address" /></Form.Item>
      <Space wrap><Button onClick={close} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy}>Lưu thay đổi</Button></Space>
    </Form>
  </Drawer>;
}

function Avatar({ profile, onSaved }: { profile: StaffProfile; onSaved: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  async function send(file?: File) {
    if (!file) return;
    if (!file.type.startsWith('image/')) { message.error('Chọn tệp ảnh (JPG, PNG, WEBP).'); return; }
    const data = new FormData(); data.append('file', file);
    setBusy(true);
    try { await upload('/api/profile/upload-avatar', data); message.success('Đã cập nhật ảnh đại diện.'); onSaved(); }
    catch (e) { message.error((e as Error).message); }
    finally { setBusy(false); if (input.current) input.current.value = ''; }
  }
  return <div className="profile-head">
    <img className="profile-avatar" src={avatarUrl(profile.anhnhanvien)} alt={`Ảnh đại diện của ${profile.hoten}`}
      onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = '/static/images/default-avatar.svg'; }} />
    <div><h2>{profile.hoten}</h2><p className="muted">{profile.chucvu || roleLabel[profile.role] || profile.role} · {profile.taikhoan}</p>
      <input ref={input} type="file" accept="image/*" hidden onChange={e => void send(e.target.files?.[0])} aria-label="Chọn ảnh đại diện" />
      <Button onClick={() => input.current?.click()} loading={busy}>Đổi ảnh đại diện</Button></div>
  </div>;
}

function ChangePassword() {
  const [form] = Form.useForm<{ current: string; next: string; confirm: string }>();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(values: { current: string; next: string }) {
    setBusy(true); setError('');
    try {
      const result = await put<{ message?: string }>('/api/profile/change-password', { matkhau_cu: values.current, matkhau_moi: values.next });
      message.success(result.message || 'Đã đổi mật khẩu.'); form.resetFields();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <Form form={form} layout="vertical" className="profile-form" disabled={busy} onFinish={save}>
    <Form.Item label="Mật khẩu hiện tại" name="current" rules={[{ required: true, message: 'Nhập mật khẩu hiện tại' }]}><Input.Password autoComplete="current-password" /></Form.Item>
    <Form.Item label="Mật khẩu mới" name="next" rules={[{ required: true, message: 'Nhập mật khẩu mới' }, { min: 6, message: 'Mật khẩu có ít nhất 6 ký tự' }]}><Input.Password autoComplete="new-password" /></Form.Item>
    <Form.Item label="Nhập lại mật khẩu mới" name="confirm" dependencies={['next']} rules={[{ required: true, message: 'Nhập lại mật khẩu mới' },
      ({ getFieldValue }) => ({ validator: (_, value) => !value || value === getFieldValue('next') ? Promise.resolve() : Promise.reject(new Error('Mật khẩu nhập lại chưa khớp')) })]}>
      <Input.Password autoComplete="new-password" /></Form.Item>
    {error && <Alert role="alert" type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
    <p className="muted">Sau khi đổi mật khẩu, các phiên xác minh hai bước đang có hiệu lực sẽ bị hủy.</p>
    <Button type="primary" htmlType="submit" loading={busy}>Đổi mật khẩu</Button>
  </Form>;
}

export default function Profile({ me }: { me: Me }) {
  const resource = useResource<{ user: StaffProfile }>('/api/profile');
  const [query, setQuery] = useQuery();
  const [editing, setEditing] = useState(false);
  const tab = query.get('tab') === 'password' ? 'password' : 'info';
  const profile = resource.data?.user;
  return <>
    <div className="page-heading section-toolbar"><div><span className="eyebrow">TÀI KHOẢN</span><h1>Trang cá nhân</h1><p>Thông tin liên hệ, ảnh đại diện và mật khẩu đăng nhập.</p></div>
      {me.features.employee_portal && me.features.attendance && <Button type="primary" size="large" href="/employee/attendance" data-testid="attendance-shortcut">Chấm công vào/ra</Button>}</div>
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && profile && <Card>
      <Tabs activeKey={tab} onChange={key => setQuery({ tab: key === 'info' ? null : key }, true)} items={[
        { key: 'info', label: 'Thông tin chung', children: <>
          <Avatar profile={profile} onSaved={resource.reload} />
          <Descriptions className="profile-details" column={{ xs: 1, md: 2 }} items={[
            { key: 'name', label: 'Họ tên', children: profile.hoten },
            { key: 'role', label: 'Vai trò', children: roleLabel[profile.role] || profile.role },
            { key: 'phone', label: 'Số điện thoại', children: profile.sdt || 'Chưa có' },
            { key: 'email', label: 'Email', children: profile.email || 'Chưa có' },
            { key: 'address', label: 'Địa chỉ', children: profile.diachi || 'Chưa có', span: 2 }]} />
          <Space wrap><Button type="primary" onClick={() => setEditing(true)}>Sửa thông tin</Button>
            {me.features.staff_security && <Button href="/admin/security">Bảo mật tài khoản</Button>}</Space>
          <EditProfile key={editing ? 'open' : 'closed'} profile={profile} open={editing} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); resource.reload(); }} />
        </> },
        { key: 'password', label: 'Đổi mật khẩu', children: <ChangePassword /> }]} />
    </Card>}
  </>;
}
