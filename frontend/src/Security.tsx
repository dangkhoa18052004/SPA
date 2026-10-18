import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Checkbox, Input, QRCode, Space, Tag } from 'antd';
import { post } from './api';
import { ResourceState, useResource } from './components';
import type { Me } from './types';
import './security.css';

type SecurityStatus = { enabled: boolean; verified_until: string | null; recovery_codes_remaining: number; sensitive_actions_required: boolean };
type Setup = { secret: string; provisioning_uri: string; expires_in: number };
type Proof = { recovery_codes?: string[] };
const help = 'Dùng mã 6 số từ ứng dụng xác thực hoặc một mã dự phòng. Mỗi mã chỉ dùng một lần.';

export default function Security({ me }: { me: Me }) {
  const resource = useResource<SecurityStatus>('/api/me/security');
  const { message } = App.useApp();
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [setup, setSetup] = useState<Setup | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [action, setAction] = useState<'verify' | 'recovery-codes' | 'disable'>('verify');
  const [, tick] = useState(0);
  useEffect(() => { const id = window.setInterval(() => tick(n => n + 1), 10000); return () => window.clearInterval(id); }, []);
  const state = resource.data;
  const verified = !!state?.verified_until && Date.parse(state.verified_until) > Date.now();
  async function perform(name: string) {
    setBusy(true); setError('');
    try {
      const result = await post<Proof & Setup>('/api/me/security/' + name, { password, code });
      if (name === 'enroll') setSetup(result);
      else {
        setSetup(null); setPassword(''); setCode(''); setAction('verify'); resource.reload();
        if (result.recovery_codes) { setCodes(result.recovery_codes); setSaved(false); }
        void message.success(name === 'disable' ? 'Đã tắt ứng dụng xác thực. Cần thiết lập lại trước thao tác nhạy cảm.' : name === 'lock' ? 'Đã kết thúc xác minh cho phiên này.' : 'Xác minh thành công.');
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function downloadCodes() {
    const blob = new Blob(['Bin Spa - Mã dự phòng cho ' + me.user.name + '\nMỗi mã chỉ dùng một lần. Lưu ở nơi riêng tư.\n\n' + codes.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'binspa-ma-du-phong.txt'; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <><div className="page-heading"><h1>Bảo mật tài khoản</h1><p>Xác minh hai bước trước khi thay đổi công, lương, quyền nhân viên và chính sách quan trọng.</p></div>
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && state && <div className="security-content">
      <Card><div className="section-toolbar"><h2>Ứng dụng xác thực</h2><Tag color={state.enabled ? 'green' : 'default'}>{state.enabled ? 'Đã bật' : 'Chưa thiết lập'}</Tag></div>
        <p>Dùng ứng dụng Authenticator trên điện thoại. Mã được tạo trong ứng dụng, không gửi qua email.</p>
        {state.sensitive_actions_required && <Alert type="info" showIcon message="Cần xác minh trước khi chốt công/lương, điều chỉnh hoặc xuất lương, đổi quyền nhân viên và cấu hình GPS. Xác minh có hiệu lực 10 phút; quyền truy cập vẫn được kiểm tra ở từng thao tác." />}
        {state.enabled && <p>Còn {state.recovery_codes_remaining} mã dự phòng. {verified ? 'Phiên này đã xác minh đến ' + new Date(state.verified_until!).toLocaleTimeString('vi-VN') + '.' : 'Phiên này chưa xác minh hoặc đã hết thời hạn.'}</p>}
        {!codes.length && <form className="security-form" onSubmit={e => { e.preventDefault(); void perform(setup ? 'confirm' : state.enabled ? action : 'enroll'); }}>
          {!state.enabled && !setup && <><p>Mở ứng dụng xác thực trên điện thoại, rồi nhập mật khẩu hiện tại để bắt đầu.</p><label htmlFor="security-password">Mật khẩu hiện tại<Input.Password id="security-password" autoComplete="current-password" maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required /></label></>}
          {setup && <><p>Trong ứng dụng, chọn thêm tài khoản rồi quét mã QR hoặc nhập khóa bên dưới.</p><div className="security-setup"><QRCode value={setup.provisioning_uri} size={184} /><div><b>Bin Spa · {me.user.name}</b><p className="security-secret">{setup.secret}</p><p className="muted">Khóa riêng tư chỉ hiện trong lần thiết lập này. Hoàn tất trong 10 phút.</p></div></div></>}
          {state.enabled && <Space wrap><Button type={action === 'verify' ? 'primary' : 'default'} disabled={busy} onClick={() => { setAction('verify'); setError(''); }}>Xác minh phiên</Button><Button disabled={busy} onClick={() => { setAction('recovery-codes'); setError(''); }}>Đổi mã dự phòng</Button><Button danger disabled={busy} onClick={() => { setAction('disable'); setError(''); }}>Tắt ứng dụng xác thực</Button></Space>}
          {state.enabled && action !== 'verify' && <><Alert type="warning" showIcon message={action === 'disable' ? 'Tắt sẽ xóa khóa xác thực, mã dự phòng và hiệu lực xác minh ở mọi phiên. Bạn cần thiết lập lại trước thao tác nhạy cảm.' : 'Mã dự phòng cũ sẽ hết hiệu lực ngay khi tạo bộ mới.'} /><label htmlFor="security-password">Mật khẩu hiện tại<Input.Password id="security-password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required /></label></>}
          {(setup || state.enabled) && <label htmlFor="security-code">{setup ? 'Mã 6 số từ ứng dụng' : 'Mã xác thực hoặc mã dự phòng'}<Input id="security-code" autoComplete="one-time-code" maxLength={setup ? 6 : 32} value={code} onChange={e => setCode(e.target.value)} disabled={busy} required aria-describedby="security-code-help" /></label>}
          {(setup || state.enabled) && <p id="security-code-help" className="muted">{setup ? 'Chỉ bật sau khi xác nhận đúng mã.' : help + ' Nếu vừa dùng mã này, chờ ứng dụng đổi mã mới.'}</p>}
          {error && <Alert type="error" role="alert" showIcon message={error} />}
          <Space wrap><Button type="primary" danger={state.enabled && action === 'disable'} htmlType="submit" loading={busy}>{setup ? 'Xác nhận và bật' : !state.enabled ? 'Thiết lập ứng dụng' : action === 'verify' ? 'Xác minh 10 phút' : action === 'disable' ? 'Xác nhận tắt' : 'Tạo bộ mã mới'}</Button>
            {setup && <Button disabled={busy} onClick={() => { setSetup(null); setCode(''); setPassword(''); setError(''); }}>Hủy thiết lập</Button>}
            {state.enabled && verified && <Button disabled={busy} onClick={() => void perform('lock')}>Kết thúc xác minh</Button>}</Space>
        </form>}
      </Card>
      {!!codes.length && <Card data-testid="recovery-codes"><h2>Lưu mã dự phòng</h2><Alert type="warning" showIcon message="Các mã này chỉ hiển thị một lần. Lưu ở nơi riêng tư để dùng khi mất điện thoại. Không gửi cho người khác." /><div className="security-codes">{codes.map(c => <code key={c}>{c}</code>)}</div><Space wrap><Button onClick={downloadCodes}>Tải mã dự phòng</Button><Checkbox checked={saved} onChange={e => setSaved(e.target.checked)}>Tôi đã lưu mã</Checkbox><Button type="primary" disabled={!saved} onClick={() => setCodes([])}>Đã lưu, đóng mã</Button></Space></Card>}
      <Card><h2>Khi mất điện thoại</h2><p>Dùng một mã dự phòng để xác minh. Muốn chuyển điện thoại: tắt ứng dụng bằng mật khẩu hiện tại và mã dự phòng, sau đó thiết lập trên máy mới. Nếu mất cả hai, liên hệ người phụ trách để xác minh danh tính theo quy trình khôi phục.</p><p className="muted">Đăng nhập và chấm công vẫn dùng luồng hiện tại. Xác thực hai bước trong bản này bảo vệ các thao tác nhạy cảm.</p></Card>
    </div>}
  </>;
}
