import { useState } from 'react';
import { Alert, App, Button, Card, Form, Input, Pagination, Select, Switch } from 'antd';
import { put } from '../../api';
import { ResourceState, useResource } from '../../components';
import type { Page } from '../../types';
import type { Reward } from './model';
import { voucherBenefit } from './VoucherGifts';

type Config = { enabled: boolean; reward_id: number | null; starts_at: string | null; ends_at: string | null; updated_at: string | null };
const localDate = (value: string | null) => value ? new Date(value).toLocaleString('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh' }).replace(' ', 'T').slice(0, 16) : '';
const utc = (value: string) => value ? new Date(value + ':00+07:00').toISOString() : null;

export default function WelcomeVoucher() {
  const r = useResource<{ config: Config }>('/api/admin/loyalty/welcome-config');
  const [page, setPage] = useState(1); const rewards = useResource<Page<Reward>>(`/api/admin/loyalty/rewards?per_page=20&page=${page}`);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const { message } = App.useApp();
  const candidates = rewards.data?.items.filter(t => t.reward_type !== 'physical_gift');
  return <Card title="Voucher chào mừng" className="care-section">
    <p>Tặng một lần khi khách tự đăng ký từ mốc bắt đầu và kích hoạt OTP thành công. Thời gian dưới đây là giờ Việt Nam.</p>
    <Alert type="info" showIcon message="Có thể chọn Dành cho khách hàng mới ngay trong form tạo/sửa voucher. Tắt hoạt động chỉ ngừng đổi điểm, không ngừng tự tặng cho khách mới, tặng thủ công hoặc sử dụng voucher đã nhận. Muốn dừng tự tặng, tắt chương trình này." />
    <ResourceState {...r} />{error && <Alert type="error" message={error} />}
    {!r.loading && !r.error && r.data && <Form key={r.data.config.updated_at || 'new'} layout="vertical" disabled={busy}
      initialValues={{ ...r.data.config, starts_at: localDate(r.data.config.starts_at), ends_at: localDate(r.data.config.ends_at) }} onFinish={async v => {
        setBusy(true); setError(''); try { await put('/api/admin/loyalty/welcome-config', { enabled: !!v.enabled, reward_id: v.reward_id ?? null, starts_at: utc(v.starts_at), ends_at: utc(v.ends_at) }); r.reload(); message.success('Đã lưu chương trình chào mừng'); }
        catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }}>
      <Form.Item name="enabled" label="Bật chương trình" valuePropName="checked"><Switch /></Form.Item>
      <ResourceState {...rewards} />
      <Form.Item name="reward_id" label="Mẫu voucher chào mừng" extra="Mẫu thiếu hạn dùng vẫn hiện kèm lý do. Vào Quà và voucher → Sửa mẫu để nhập số ngày hiệu lực.">
        <Select showSearch optionFilterProp="label" allowClear options={candidates?.map(t => ({ value: t.id, disabled: !t.validity_days,
          label: `${t.name} · ${voucherBenefit(t)} · ${t.validity_days ? `${t.validity_days} ngày${t.active ? '' : ' · tắt đổi điểm, vẫn nhận quà'}` : 'chưa có hạn dùng — cần sửa mẫu'}` }))} />
      </Form.Item>
      {rewards.data && rewards.data.total > 20 && <Pagination current={page} total={rewards.data.total} pageSize={20} showSizeChanger={false} onChange={setPage} />}
      <Form.Item name="starts_at" label="Bắt đầu (giờ Việt Nam)" extra="Để trống để bắt đầu ngay khi bật và lưu."><Input type="datetime-local" /></Form.Item>
      <Form.Item name="ends_at" label="Kết thúc (tùy chọn, giờ Việt Nam)"><Input type="datetime-local" /></Form.Item>
      <Button type="primary" htmlType="submit" loading={busy}>Lưu chương trình chào mừng</Button>
    </Form>}
  </Card>;
}
