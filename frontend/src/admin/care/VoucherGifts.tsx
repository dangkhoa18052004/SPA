import { useRef, useState } from 'react';
import { Alert, App, Button, Card, Form, Input, InputNumber, Modal, Pagination, Select, Space, Tag } from 'antd';
import { ApiError, api, post } from '../../api';
import { ResourceState, useResource } from '../../components';
import type { Me, Page } from '../../types';
import type { Reward } from './model';
import { options, redemptionGroups, redemptionLabels, utcDate } from './model';
import { vnd } from '../booking/model';

export const issuanceLabels: Record<string, string> = { points_redemption: 'Đổi bằng điểm', welcome: 'Quà chào mừng', staff_gift: 'Được spa tặng' };
export const voucherBenefit = (r: Reward) => r.reward_type === 'voucher_percent'
  ? `Giảm ${r.percentage_value}%${r.max_discount_amount ? ` · tối đa ${vnd(r.max_discount_amount)}` : ''}` : `Giảm ${vnd(r.reward_value)}`;
const scopes: Record<string, string> = { both: 'Dịch vụ và gói', service_invoice: 'Hóa đơn dịch vụ', package_purchase: 'Mua gói' };
type Gift = { id: number; code: string; reward: Reward; status: string; issuance_source: string; issued_at: string;
  expires_at: string | null; issued_by_name: string | null; gift_reason: string | null; customer_message: string | null;
  cancelled_at: string | null; cancel_reason: string | null; cancelled_by_name: string | null };
type Body = { reward_id: number; reason: string; customer_message: string };
type Pending = { key: string; body: Body };

function Nav({ data, change }: { data?: Page<unknown>; change: (page: number) => void }) {
  return data && data.total > data.per_page ? <Pagination current={data.page} total={data.total} pageSize={data.per_page} showSizeChanger={false} onChange={change} /> : null;
}
export function VoucherGiftDialog({ recipient, actorId, canManage, close, saved }: { recipient: { makh: number; hoten: string; sdt?: string | null }; actorId: number; canManage: boolean; close: () => void; saved: () => void }) {
  const storage = `binspa-voucher-gift:${actorId}:${recipient.makh}`;
  const [pending, setPending] = useState<Pending | null>(() => {
    try { const p = JSON.parse(sessionStorage.getItem(storage) || 'null'); return p?.key && p?.body?.reward_id ? p : null; } catch { return null; }
  });
  const [page, setPage] = useState(1); const [search, setSearch] = useState('');
  const templates = useResource<Page<Reward>>(`/api/admin/loyalty/gift-templates?${new URLSearchParams({ page: String(page), per_page: '10', search })}`);
  const [form] = Form.useForm<Body>(); const chosen = Form.useWatch('reward_id', form);
  const reward = templates.data?.items.find(r => r.id === chosen);
  const [busy, setBusy] = useState(false); const lock = useRef(false); const [error, setError] = useState(''); const { message } = App.useApp();
  function remember(value: Pending | null) {
    setPending(value);
    try { if (value) sessionStorage.setItem(storage, JSON.stringify(value)); else sessionStorage.removeItem(storage); } catch { /* In-memory retry remains available. */ }
  }
  async function submit(values: Body) {
    if (lock.current) return;
    const operation = pending || { key: crypto.randomUUID(), body: { reward_id: values.reward_id, reason: values.reason.trim(), customer_message: (values.customer_message || '').trim() } };
    remember(operation); lock.current = true; setBusy(true); setError('');
    try {
      const result = await api<{ redemption: Gift }>(`/api/admin/loyalty/customers/${recipient.makh}/voucher-gifts`, {
        method: 'POST', headers: { 'Idempotency-Key': operation.key }, body: JSON.stringify(operation.body) });
      remember(null); message.success(`Đã tặng voucher ${result.redemption.code}`); saved();
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status > 0 && e.status < 500) remember(null);
    } finally { lock.current = false; setBusy(false); }
  }
  return <Modal open centered title="Tặng voucher" styles={{ body: { maxHeight: 'calc(100dvh - 180px)', overflowY: 'auto' } }} onCancel={() => { if (!busy) close(); }} maskClosable={!busy} keyboard={!busy} footer={null}>
    <p><b>{recipient.hoten}</b> · KH #{recipient.makh} · {recipient.sdt ? `••••${recipient.sdt.slice(-4)}` : 'Chưa có SĐT'}</p>
    <p>Voucher được cấp vào Ưu đãi của tôi. Điểm của khách không thay đổi.</p>
    {error && <Alert type="error" showIcon message={error} />}
    {pending && <Alert type="warning" showIcon message="Đang giữ yêu cầu chưa rõ kết quả. Thử lại sẽ dùng cùng mã chống trùng, không tặng thêm voucher." />}
    <Form form={form} layout="vertical" initialValues={pending?.body} disabled={busy || !!pending} onFinish={submit}>
      <Input.Search aria-label="Tìm mẫu voucher" placeholder="Tìm mẫu voucher" onSearch={value => { setSearch(value); setPage(1); }} />
      <ResourceState {...templates} />
      {!templates.loading && !templates.error && !templates.data?.items.length && <Alert type="info" showIcon
        message="Không có mẫu voucher phù hợp để tặng"
        description={<>Có thể tặng voucher giảm tiền hoặc phần trăm còn tồn, kể cả mẫu tắt hoạt động. Hãy kiểm tra bộ lọc hoặc bổ sung mẫu/tồn kho.
          {canManage ? <p><Button href="/admin/loyalty?tab=rewards" target="_blank" rel="noopener noreferrer">Quản lý mẫu voucher</Button></p> : <p>Nhờ quản lý tạo hoặc bật mẫu voucher tặng.</p>}</>} />}
      <Form.Item name="reward_id" label="Mẫu voucher" rules={[{ required: true, message: 'Chọn mẫu voucher' }]}>
        <Select aria-label="Mẫu voucher" showSearch optionFilterProp="label" options={templates.data?.items.map(r => ({ value: r.id, label: `${r.name} · ${voucherBenefit(r)}` }))} />
      </Form.Item>
      <Nav data={templates.data} change={setPage} />
      {reward && <Card size="small"><p>{voucherBenefit(reward)} · {scopes[reward.apply_to || 'both']}</p><p>Đơn từ {vnd(reward.minimum_spend || 0)} · {reward.validity_days ? `Hạn ${reward.validity_days} ngày` : 'Không hết hạn'} · {reward.stock == null ? 'Tồn không giới hạn' : `Còn ${reward.stock}`}</p></Card>}
      <Form.Item name="reason" label="Lý do nội bộ" extra="Khách không nhìn thấy lý do này" rules={[{ required: true, whitespace: true, max: 2000 }]}><Input.TextArea aria-label="Lý do nội bộ" rows={3} maxLength={2000} /></Form.Item>
      <Form.Item name="customer_message" label="Lời nhắn cho khách (tùy chọn)" rules={[{ max: 1000 }]}><Input.TextArea aria-label="Lời nhắn cho khách (tùy chọn)" rows={2} maxLength={1000} /></Form.Item>
      <Space wrap><Button type="primary" loading={busy} disabled={busy || (!pending && (templates.loading || !!templates.error || !templates.data?.items.length))} onClick={() => pending ? void submit(pending.body) : form.submit()}>{pending ? 'Thử lại cùng yêu cầu' : 'Xác nhận tặng 1 voucher'}</Button><Button disabled={busy} onClick={close}>Đóng</Button></Space>
    </Form>
  </Modal>;
}

export default function VoucherGifts({ recipient, me }: { recipient: { makh: number; hoten: string; sdt?: string | null; trangthai: string }; me: Me }) {
  const [page, setPage] = useState(1); const [source, setSource] = useState(''); const [status, setStatus] = useState('all'); const [staff, setStaff] = useState<number | null>(null);
  const [open, setOpen] = useState(false); const [cancelling, cancel] = useState<Gift | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [form] = Form.useForm(); const lock = useRef(false);
  const r = useResource<Page<Gift>>(`/api/admin/loyalty/customers/${recipient.makh}/voucher-gifts?${new URLSearchParams({ page: String(page), issuance_source: source, status, ...(staff ? { issued_by_staff: String(staff) } : {}) })}`);
  const { message } = App.useApp(); const manager = ['admin', 'manager'].includes(me.user.role);
  return <section aria-label="Voucher tặng của khách">
    <Space wrap><Button type="primary" disabled={recipient.trangthai !== 'active'} onClick={() => setOpen(true)}>Tặng voucher</Button><Button onClick={r.reload}>Tải lại lịch sử</Button></Space>
    {recipient.trangthai !== 'active' && <p>Chỉ tặng voucher cho khách đang hoạt động.</p>}
    <h3>Lịch sử voucher được tặng</h3>
    <Space wrap className="care-section"><Select aria-label="Nguồn voucher" value={source} options={options({ '': 'Mọi nguồn tặng', welcome: 'Quà chào mừng', staff_gift: 'Được spa tặng' })} onChange={v => { setSource(v); setPage(1); }} /><Select aria-label="Trạng thái voucher" value={status} options={options(redemptionGroups)} onChange={v => { setStatus(v); setPage(1); }} /><InputNumber aria-label="Mã nhân viên tặng" placeholder="Mã nhân viên tặng" min={1} precision={0} value={staff} onChange={v => { setStaff(v); setPage(1); }} /></Space>
    <ResourceState {...r} empty={!r.data?.items.length} />
    {!r.loading && !r.error && r.data?.items.map(g => <Card key={g.id} size="small" className="care-section">
      <h4>{g.reward.name}</h4><Tag>{issuanceLabels[g.issuance_source]}</Tag><Tag>{redemptionLabels[g.status]}</Tag>
      <p><code>{g.code}</code> · {voucherBenefit(g.reward)}</p><p>{scopes[g.reward.apply_to || 'both']} · Đơn từ {vnd(g.reward.minimum_spend || 0)}</p>
      <p>Cấp lúc {utcDate(g.issued_at)} · Hạn {g.expires_at ? utcDate(g.expires_at) : 'Không hết hạn'}</p>
      {g.issued_by_name && <p>Người tặng: {g.issued_by_name}</p>}{g.gift_reason && <p>Lý do nội bộ: {g.gift_reason}</p>}{g.customer_message && <p>Lời nhắn: {g.customer_message}</p>}
      {g.cancelled_at && <p>Thu hồi lúc {utcDate(g.cancelled_at)} bởi {g.cancelled_by_name} · {g.cancel_reason}</p>}
      {manager && g.status === 'available' && <Button danger onClick={() => { cancel(g); form.resetFields(); setError(''); }}>Thu hồi voucher</Button>}
    </Card>)}<Nav data={r.data} change={setPage} />
    {open && <VoucherGiftDialog recipient={recipient} actorId={me.user.id} canManage={manager} close={() => setOpen(false)} saved={() => { setOpen(false); r.reload(); }} />}
    <Modal open={!!cancelling} centered title="Thu hồi voucher" styles={{ body: { maxHeight: 'calc(100dvh - 180px)', overflowY: 'auto' } }} footer={null} maskClosable={!busy} keyboard={!busy} onCancel={() => { if (!busy) cancel(null); }}>
      <p>{recipient.hoten} · {cancelling?.reward.name} · {cancelling?.code}</p><p>Voucher sẽ ngừng sử dụng; không hoàn tồn.</p>{error && <Alert type="error" message={error} />}
      <Form form={form} layout="vertical" disabled={busy} onFinish={async v => {
        if (lock.current || !cancelling) return; lock.current = true; setBusy(true); setError('');
        try { await post(`/api/admin/loyalty/voucher-gifts/${cancelling.id}/cancel`, { reason: v.reason }); cancel(null); r.reload(); message.success('Đã thu hồi voucher'); }
        catch (e) { setError((e as Error).message); r.reload(); } finally { lock.current = false; setBusy(false); }
      }}><Form.Item name="reason" label="Lý do thu hồi" rules={[{ required: true, whitespace: true, max: 2000 }]}><Input.TextArea aria-label="Lý do thu hồi" rows={3} maxLength={2000} /></Form.Item><Button danger type="primary" htmlType="submit" loading={busy}>Xác nhận thu hồi</Button></Form>
    </Modal>
  </section>;
}
