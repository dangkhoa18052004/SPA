import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Input, Modal, Space } from 'antd';
import { api, ApiError, post } from './api';
import './security.css';
type SecurityStatus = { enabled: boolean; verified_until: string | null };
type GateRequest = { enrollment: boolean; resolve: () => void; reject: (error: Error) => void };
const help = 'Dùng mã 6 số từ ứng dụng xác thực hoặc một mã dự phòng. Mỗi mã chỉ dùng một lần.';

export function StepUpGate() {
  const waiting = useRef<GateRequest[]>([]);
  const [open, setOpen] = useState(false);
  const [enrollment, setEnrollment] = useState(false);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    function receive(event: Event) {
      event.preventDefault();
      const request = (event as CustomEvent<GateRequest>).detail;
      waiting.current.push(request); setEnrollment(request.enrollment); setOpen(true);
    }
    window.addEventListener('binspa:step-up', receive);
    return () => { window.removeEventListener('binspa:step-up', receive); waiting.current.splice(0).forEach(r => r.reject(new Error('Đã đóng xác minh.'))); };
  }, []);
  function cancel() {
    waiting.current.splice(0).forEach(r => r.reject(new ApiError('Đã hủy thao tác. Bạn có thể thực hiện lại khi sẵn sàng.', 403, 'mfa_cancelled')));
    setOpen(false); setCode(''); setError('');
  }
  async function verify() {
    setBusy(true); setError('');
    try {
      if (enrollment) {
        const state = await api<SecurityStatus>('/api/me/security');
        if (!state.enabled || !state.verified_until) throw new Error('Hãy hoàn tất thiết lập và xác minh trong trang Bảo mật tài khoản.');
      } else await post('/api/me/security/verify', { code });
      waiting.current.splice(0).forEach(r => r.resolve()); setOpen(false); setCode('');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <Modal title="Xác minh thao tác" open={open} onCancel={() => { if (!busy) cancel(); }} footer={null} maskClosable={false} closable={!busy} destroyOnHidden>
    <form className="security-form" onSubmit={e => { e.preventDefault(); void verify(); }}>
      <p>{enrollment ? 'Thiết lập xác thực hai bước để tiếp tục. Trang đang thao tác sẽ giữ nguyên dữ liệu bạn đã nhập.' : 'Xác minh để tiếp tục với thao tác vừa chọn. Hiệu lực 10 phút trong phiên đăng nhập này.'}</p>
      {enrollment ? <Button href="/admin/security" target="_blank" rel="noopener noreferrer">Mở Bảo mật tài khoản</Button> : <label htmlFor="step-up-code">Mã xác thực<Input id="step-up-code" autoFocus autoComplete="one-time-code" maxLength={32} value={code} onChange={e => setCode(e.target.value)} disabled={busy} required aria-describedby="step-up-help" /></label>}
      {!enrollment && <p id="step-up-help" className="muted">{help}</p>}
      {error && <Alert role="alert" type="error" showIcon message={error} />}
      <Space wrap><Button onClick={cancel} disabled={busy}>Hủy thao tác</Button><Button type="primary" htmlType="submit" loading={busy}>{enrollment ? 'Đã thiết lập, tiếp tục' : 'Xác minh và tiếp tục'}</Button></Space>
    </form>
  </Modal>;
}

