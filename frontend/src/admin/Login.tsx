import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input } from 'antd';
import { safeNext } from '../session';
import './admin.css';

type LoginResult = { success?: boolean; message?: string; access_token?: string; redirect_url?: string;
  user?: { manv: number; hoten: string; role: string } };

export default function Login() {
  const params = new URLSearchParams(window.location.search);
  const next = safeNext(params.get('next'));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { document.title = 'Bin Spa · Đăng nhập nhân viên'; }, []);
  async function submit(values: { taikhoan: string; matkhau: string }) {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/auth/login/staff', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(values) });
      const result: LoginResult = await response.json().catch(() => ({}));
      if (!response.ok || !result.success || !result.access_token || !result.user) {
        setError(result.message || (response.status === 429 ? 'Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.' : 'Tài khoản hoặc mật khẩu không đúng.'));
        return;
      }
      localStorage.setItem('admin_token', result.access_token);
      localStorage.setItem('admin_role', result.user.role);
      localStorage.setItem('admin_user', JSON.stringify(result.user));
      // A fresh load picks up the new account's role and menu.
      window.location.assign(next || result.redirect_url || '/admin/profile');
    } catch {
      setError('Không thể kết nối máy chủ. Vui lòng thử lại.');
    } finally { setBusy(false); }
  }
  return <main className="admin-login"><Card className="admin-login-card">
    <div className="brand"><span className="brand-mark">B</span><b>Bin Spa</b></div>
    <h1>Đăng nhập nhân viên</h1><p className="muted">Dùng tài khoản được quản lý cấp.</p>
    {next && <Alert type="info" showIcon message="Phiên đăng nhập đã hết hạn. Đăng nhập lại để quay về trang đang làm." style={{ marginBottom: 16 }} />}
    {error && <Alert role="alert" type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
    <Form layout="vertical" onFinish={submit} disabled={busy} requiredMark={false}>
      <Form.Item label="Tài khoản" name="taikhoan" rules={[{ required: true, whitespace: true, message: 'Nhập tài khoản' }]}><Input autoComplete="username" autoFocus /></Form.Item>
      <Form.Item label="Mật khẩu" name="matkhau" rules={[{ required: true, message: 'Nhập mật khẩu' }]}><Input.Password autoComplete="current-password" /></Form.Item>
      <Button type="primary" htmlType="submit" block loading={busy}>Đăng nhập</Button>
    </Form>
  </Card></main>;
}
