import { useRef, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Pagination, Result, Select, Space, Statistic, Switch, Tabs, Tag } from 'antd';
import { ApiError, api, del, post, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me, Page } from '../../types';
import { vnd } from '../booking/model';
import { canFulfill, options, redemptionGroups, redemptionLabels, rewardKinds, rewardPayload, utcDate } from './model';
import type { Ledger, Redemption, Reward } from './model';
import './care.css';

type Wallet = { available_points: number; reserved_points: number; lifetime_earned: number; lifetime_redeemed: number };
type Customer = Wallet & { makh: number; hoten: string; sdt: string; email: string };
const walletLabels: Record<keyof Wallet, string> = { available_points: 'Điểm có thể dùng', reserved_points: 'Điểm đang áp dụng', lifetime_earned: 'Tổng đã tích', lifetime_redeemed: 'Tổng đã dùng' };
const benefit = (r: Reward) => r.reward_type === 'physical_gift' ? 'Nhận quà tại spa' : r.reward_type === 'voucher_percent'
  ? `Giảm ${r.percentage_value}%${r.max_discount_amount ? ` · tối đa ${vnd(r.max_discount_amount)}` : ''}` : `Giảm ${vnd(r.reward_value)}`;
function PageNav({ data, onChange }: { data?: Page<unknown>; onChange: (n: number) => void }) {
  return data && data.total > data.per_page ? <Pagination className="care-section" current={data.page} total={data.total} pageSize={data.per_page} showSizeChanger={false} onChange={onChange} /> : null;
}
function LedgerList({ rows }: { rows: Ledger[] }) {
  return <div className="care-list">{rows.length ? rows.map(r => <Card size="small" key={r.id}><b>{r.points_delta > 0 ? '+' : ''}{r.points_delta.toLocaleString('vi-VN')} điểm</b><p className="care-text">{r.description}</p><small>Khách #{r.makh} · {utcDate(r.created_at)}</small></Card>) : <Empty description="Chưa có giao dịch điểm" />}</div>;
}
function Overview() {
  const r = useResource<{ overview: Wallet & { wallets: number } }>('/api/admin/loyalty/overview');
  return <><ResourceState {...r} />{!r.loading && !r.error && r.data && <div className="kpi-grid">{Object.entries({ wallets: 'Ví khách hàng', ...walletLabels }).map(([k, title]) => <Card key={k}><Statistic title={title} value={r.data!.overview[k as keyof typeof r.data.overview]} /></Card>)}</div>}</>;
}
function Rules() {
  const r = useResource<{ config: Record<string, number | string | boolean | null> }>('/api/admin/loyalty/config');
  const tier = useResource<{ policy: { tiers: { code: string; name: string; min_points: number }[]; count_adjustments: boolean } }>('/api/admin/loyalty/tiers');
  const { message, modal } = App.useApp(); const [busy, setBusy] = useState(false);
  const fields = { earn_amount_unit: 'Mỗi bao nhiêu tiền được tích điểm (đ)', earn_points: 'Số điểm tích mỗi lần', point_value: 'Giá trị một điểm khi dùng (đ)', minimum_redeem_points: 'Số điểm dùng tối thiểu', maximum_redeem_percent: 'Giảm bằng điểm tối đa (%)' };
  const switches = { earn_on_service_invoice: 'Tích điểm khi trả tiền dịch vụ', earn_on_package_purchase: 'Tích điểm khi mua gói', redeem_on_service_invoice: 'Cho dùng điểm trả tiền dịch vụ', redeem_on_package_purchase: 'Cho dùng điểm mua gói' };
  async function save(path: string, body: unknown) { setBusy(true); try { await put(path, body); message.success('Đã lưu quy tắc'); r.reload(); tier.reload(); } catch (e) { message.error((e as Error).message); } finally { setBusy(false); } }
  return <><ResourceState {...r} />{!r.loading && !r.error && r.data && <Card title="Tích và dùng điểm"><p>Điểm hiện không hết hạn. Thay đổi quy tắc áp dụng cho những giao dịch tiếp theo.</p>
    <Form layout="vertical" initialValues={r.data.config} disabled={busy} onFinish={v => modal.confirm({ title: 'Lưu quy tắc tích và dùng điểm?', content: 'Kiểm tra các giá trị trước khi áp dụng cho khách hàng.', okText: 'Lưu quy tắc', cancelText: 'Kiểm tra lại', onOk: () => save('/api/admin/loyalty/config', v) })}>
      <div className="care-rule-grid">{Object.entries(fields).map(([name, label]) => <Form.Item key={name} name={name} label={label} rules={[{ required: true }]}><InputNumber min={['earn_points', 'maximum_redeem_percent'].includes(name) ? 0 : 1} max={name === 'maximum_redeem_percent' ? 100 : 1000000000} precision={name === 'maximum_redeem_percent' ? 2 : 0} /></Form.Item>)}</div>
      {Object.entries(switches).map(([name, label]) => <Form.Item key={name} name={name} label={label} valuePropName="checked"><Switch /></Form.Item>)}<Button type="primary" htmlType="submit" loading={busy}>Lưu quy tắc</Button>
    </Form></Card>}
    <div className="care-section"><ResourceState {...tier} />{!tier.loading && !tier.error && tier.data && <Card title="Hạng thành viên"><p>Hạng dựa vào điểm tích từ thanh toán. Đổi thưởng không làm giảm hạng; thu hồi điểm tích do hoàn tiền có thể giảm hạng.</p>
      <Form layout="vertical" initialValues={tier.data.policy} disabled={busy} onFinish={v => save('/api/admin/loyalty/tiers', v)}>
        <Form.List name="tiers">{(fields, { add, remove }) => <>{fields.map(({ key, name }) => <Card key={key} size="small" className="care-section">
          <Form.Item name={[name, 'name']} label="Tên hạng" rules={[{ required: true, max: 50 }]}><Input /></Form.Item>
          <Form.Item name={[name, 'code']} label="Mã hạng" extra="Ví dụ: thanh_vien, bac, vang" rules={[{ required: true, max: 30 }]}><Input /></Form.Item>
          <Form.Item name={[name, 'min_points']} label="Điểm tối thiểu" rules={[{ required: true }]}><InputNumber min={0} precision={0} /></Form.Item><Button danger onClick={() => remove(name)} disabled={fields.length === 1}>Bỏ hạng này</Button>
        </Card>)}<Button className="care-section" onClick={() => add({ code: '', name: '', min_points: 0 })} disabled={fields.length >= 10}>Thêm hạng</Button></>}</Form.List>
        <Form.Item className="care-section" name="count_adjustments" label="Tính điều chỉnh điểm thủ công vào hạng" valuePropName="checked"><Switch /></Form.Item><Button type="primary" htmlType="submit" loading={busy}>Lưu hạng thành viên</Button>
      </Form></Card>}</div>
  </>;
}
function RewardEditor({ reward, close, saved }: { reward: Reward | 'new'; close: () => void; saved: () => void }) {
  const [form] = Form.useForm(); const [busy, setBusy] = useState(false); const { message, modal } = App.useApp();
  const kind = Form.useWatch('reward_type', form) || (reward === 'new' ? 'voucher_amount' : reward.reward_type);
  const numeric = (r: Reward) => Object.fromEntries(Object.entries(r).map(([k, v]) => ['reward_value', 'percentage_value', 'max_discount_amount', 'minimum_spend'].includes(k) ? [k, v == null ? null : Number(v)] : [k, v]));
  const onClose = () => { if (busy) return; if (!form.isFieldsTouched()) close(); else modal.confirm({ title: 'Bỏ thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: close }); };
  return <Drawer open title={reward === 'new' ? 'Thêm quà hoặc voucher' : 'Sửa quà đổi thưởng'} onClose={onClose} width={560} maskClosable={!busy}>
    <Form form={form} layout="vertical" disabled={busy} initialValues={reward === 'new' ? { active: true, reward_type: 'voucher_amount', apply_to: 'both', minimum_spend: 0 } : numeric(reward)} onFinish={async v => {
      setBusy(true); try { await api('/api/admin/loyalty/rewards' + (reward === 'new' ? '' : '/' + reward.id), { method: reward === 'new' ? 'POST' : 'PUT', body: JSON.stringify(rewardPayload(v)) }); saved(); message.success('Đã lưu quà đổi thưởng'); } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
    }}>
      <Form.Item name="reward_type" label="Loại quà" rules={[{ required: true }]}><Select options={options(rewardKinds)} /></Form.Item>
      <Form.Item name="name" label={kind === 'physical_gift' ? 'Tên quà' : 'Tên voucher'} rules={[{ required: true, whitespace: true, max: 200 }]}><Input /></Form.Item>
      <Form.Item name="description" label="Mô tả"><Input.TextArea rows={3} maxLength={5000} /></Form.Item>
      <Form.Item name="points_cost" label="Điểm cần đổi" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>
      {kind === 'voucher_amount' && <Form.Item name="reward_value" label="Số tiền giảm (đ)" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>}
      {kind === 'voucher_percent' && <><Form.Item name="percentage_value" label="Phần trăm giảm (%)" rules={[{ required: true }]}><InputNumber min={0.01} max={100} precision={2} /></Form.Item><Form.Item name="max_discount_amount" label="Giảm tối đa (đ)" extra="Để trống nếu không giới hạn"><InputNumber min={1} precision={0} /></Form.Item></>}
      {kind !== 'physical_gift' && <><Form.Item name="minimum_spend" label="Đơn tối thiểu (đ)"><InputNumber min={0} precision={0} /></Form.Item><Form.Item name="apply_to" label="Áp dụng cho"><Select options={options({ both: 'Dịch vụ và gói', service_invoice: 'Hóa đơn dịch vụ', package_purchase: 'Mua gói' })} /></Form.Item></>}
      <Form.Item name="stock" label="Số lượng còn cho đổi" extra="Để trống nếu không giới hạn"><InputNumber min={0} precision={0} /></Form.Item>
      <Form.Item name="validity_days" label="Hiệu lực từ lúc đổi (ngày)" extra="Để trống nếu không hết hạn"><InputNumber min={1} precision={0} /></Form.Item>
      <Form.Item name="active" label="Đang cho đổi" valuePropName="checked"><Switch /></Form.Item><Space><Button type="primary" htmlType="submit" loading={busy}>Lưu quà</Button><Button onClick={onClose}>Hủy</Button></Space>
    </Form>
  </Drawer>;
}
function Rewards() {
  const [q, query] = useQuery(); const [editing, edit] = useState<Reward | 'new' | null>(null); const { modal, message } = App.useApp();
  const r = useResource<Page<Reward>>(`/api/admin/loyalty/rewards?page=${q.get('page') || 1}`);
  return <><div className="section-toolbar"><p>Voucher và quà khách có thể đổi bằng điểm.</p><Button type="primary" onClick={() => edit('new')}>Thêm quà / voucher</Button></div><ResourceState {...r} empty={!r.data?.items.length} />
    {!r.loading && !r.error && <div className="care-list">{r.data?.items.map(reward => <Card key={reward.id}><div className="card-head"><h3>{reward.name}</h3><Tag>{reward.active ? 'Đang cho đổi' : 'Đã ngừng'}</Tag></div><p>{rewardKinds[reward.reward_type]} · {benefit(reward)}</p><p>{reward.points_cost} điểm · {reward.stock == null ? 'Không giới hạn số lượng' : `Còn ${reward.stock}`} · {reward.validity_days == null ? 'Không hết hạn' : `Hiệu lực ${reward.validity_days} ngày`}</p><p className="care-text">{reward.description}</p><Space wrap><Button onClick={() => edit(reward)}>Sửa quà</Button>{reward.active && <Button danger onClick={() => modal.confirm({ title: `Ngừng cho đổi “${reward.name}”?`, content: 'Quà khách đã đổi vẫn giữ điều kiện và lịch sử.', okText: 'Ngừng cho đổi', cancelText: 'Quay lại', onOk: async () => { try { await del(`/api/admin/loyalty/rewards/${reward.id}`); r.reload(); } catch (e) { message.error((e as Error).message); } } })}>Ngừng cho đổi</Button>}</Space></Card>)}</div>}<PageNav data={r.data} onChange={page => query({ page })} />
    {editing && <RewardEditor key={editing === 'new' ? 'new' : editing.id} reward={editing} close={() => edit(null)} saved={() => { edit(null); r.reload(); }} />}
  </>;
}
function CustomerDetail({ id, close }: { id: number; close: () => void }) {
  const [page, setPage] = useState(1); const r = useResource<Page<Ledger> & { customer: Customer; wallet: Wallet; tier: { tier: { name: string }; qualifying_points: number; points_to_next: number; next_tier: { name: string } | null } }>(`/api/admin/loyalty/customers/${id}?page=${page}`);
  return <Drawer open title="Điểm và hạng thành viên" onClose={close} width={600}><ResourceState {...r} />{!r.loading && !r.error && r.data && <><h2>{r.data.customer.hoten}</h2><p>{r.data.customer.sdt}</p><p>Hạng {r.data.tier.tier.name} · {r.data.tier.qualifying_points} điểm xét hạng</p>{r.data.tier.next_tier && <p>Còn {r.data.tier.points_to_next} điểm lên {r.data.tier.next_tier.name}</p>}<Descriptions column={1} items={Object.entries(walletLabels).map(([k, label]) => ({ key: k, label, children: r.data!.wallet[k as keyof Wallet] }))} /><h3>Lịch sử điểm</h3><LedgerList rows={r.data.items} /><PageNav data={r.data} onChange={setPage} /></>}</Drawer>;
}
function Customers({ actorId }: { actorId: number }) {
  const [q, query] = useQuery(); const [adjusting, adjust] = useState<Customer | null>(null); const [busy, setBusy] = useState(false); const [form] = Form.useForm(); const [error, setError] = useState('');
  const pending = useRef<{ key: string; body: string } | null>(null); const [uncertain, setUncertain] = useState(false); const { message } = App.useApp();
  const storageKey = (id: number) => `binspa-point-adjustment:${actorId}:${id}`;
  function open(c: Customer) {
    adjust(c); form.resetFields(); setError(''); pending.current = null;
    try { const v = JSON.parse(sessionStorage.getItem(storageKey(c.makh)) || 'null'); if (v?.key && v?.body) { const body = JSON.parse(v.body); pending.current = v; form.setFieldsValue({ direction: body.points_delta < 0 ? -1 : 1, points: Math.abs(body.points_delta), reason: body.reason }); } } catch { /* Optional recovery storage. */ }
    setUncertain(!!pending.current);
  }
  const r = useResource<Page<Customer>>(`/api/admin/loyalty/customers?${new URLSearchParams({ search: q.get('search') || '', page: q.get('page') || '1' })}`);
  return <><Input.Search key={q.get('search')} aria-label="Tìm khách có điểm" placeholder="Tên, số điện thoại hoặc email" defaultValue={q.get('search') || ''} onSearch={search => query({ search, page: 1 })} enterButton="Tìm khách" className="care-section" /><ResourceState {...r} empty={!r.data?.items.length} />
    {!r.loading && !r.error && <div className="care-list care-section">{r.data?.items.map(c => <Card key={c.makh}><h3>{c.hoten}</h3><p>{c.sdt} · {c.available_points} điểm có thể dùng</p><Space><Button onClick={() => query({ view: c.makh })}>Xem điểm và hạng</Button><Button onClick={() => open(c)}>Điều chỉnh điểm</Button></Space></Card>)}</div>}<PageNav data={r.data} onChange={page => query({ page })} />
    {Number(q.get('view')) > 0 && <CustomerDetail key={q.get('view')} id={Number(q.get('view'))} close={() => query({ view: null })} />}
    <Modal open={!!adjusting} title={`Điều chỉnh điểm · ${adjusting?.hoten}`} footer={null} onCancel={() => { if (!busy) adjust(null); }}>
      <Form form={form} disabled={busy || uncertain} layout="vertical" initialValues={{ direction: 1 }} onFinish={async v => {
        const body = JSON.stringify({ points_delta: Number(v.points) * Number(v.direction), reason: v.reason });
        if (!pending.current || pending.current.body !== body) pending.current = { key: crypto.randomUUID(), body };
        const storage = storageKey(adjusting!.makh); try { sessionStorage.setItem(storage, JSON.stringify(pending.current)); } catch { /* The in-memory key still protects a retry. */ }
        setBusy(true); setError(''); try { await post(`/api/admin/loyalty/customers/${adjusting!.makh}/adjust`, { ...JSON.parse(body), idempotency_key: pending.current.key }); pending.current = null; try { sessionStorage.removeItem(storage); } catch { /* Optional storage. */ } setUncertain(false); adjust(null); r.reload(); message.success('Đã lưu điểm và lịch sử điều chỉnh'); } catch (e) { setError((e as Error).message); const unknown = !(e instanceof ApiError) || e.status === 0 || e.status >= 500; setUncertain(unknown); if (!unknown) { pending.current = null; try { sessionStorage.removeItem(storage); } catch { /* Optional storage. */ } } } finally { setBusy(false); }
      }}>
        {error && <Alert type="error" message={error} />}{uncertain && <Alert type="warning" message="Đang giữ lần điều chỉnh chưa rõ kết quả. Bấm Lưu điều chỉnh để kiểm tra lại cùng yêu cầu; điểm sẽ không bị cộng/trừ lần nữa." />}<Form.Item name="direction" label="Cách điều chỉnh"><Select options={[{ value: 1, label: 'Cộng điểm' }, { value: -1, label: 'Trừ điểm' }]} /></Form.Item><Form.Item name="points" label="Số điểm" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item><Form.Item name="reason" label="Lý do" rules={[{ required: true, whitespace: true, min: 3, max: 2000 }]}><Input.TextArea rows={3} /></Form.Item><Button type="primary" htmlType="submit" loading={busy} disabled={busy}>Lưu điều chỉnh</Button>
      </Form>
    </Modal>
  </>;
}
function Transactions() {
  const [q, query] = useQuery(); const r = useResource<Page<Ledger>>(`/api/admin/loyalty/transactions?${new URLSearchParams({ page: q.get('page') || '1', ...(q.get('makh') ? { makh: q.get('makh')! } : {}) })}`);
  return <><ResourceState {...r} />{!r.loading && !r.error && <LedgerList rows={r.data?.items || []} />}<PageNav data={r.data} onChange={page => query({ page })} /></>;
}
function Redemptions() {
  const [q, query] = useQuery(); const [selected, select] = useState<Redemption | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const { message } = App.useApp();
  const r = useResource<Page<Redemption>>(`/api/admin/loyalty/redemptions?${new URLSearchParams({ search: q.get('search') || '', status: q.get('status') || 'all', reward_type: q.get('reward_type') || '', page: q.get('page') || '1' })}`);
  return <><p>Tra tên khách hoặc mã quà. Chỉ xác nhận sau khi đã trao quà cho đúng khách.</p><div className="care-toolbar"><Input.Search key={q.get('search')} aria-label="Tra mã quà" placeholder="Tên, điện thoại hoặc mã BIN-…" defaultValue={q.get('search') || ''} onSearch={search => query({ search, page: 1 })} enterButton="Tìm" /><Select aria-label="Trạng thái đổi quà" value={q.get('status') || 'all'} options={options(redemptionGroups)} onChange={status => query({ status, page: 1 })} /><Select aria-label="Loại phần thưởng" value={q.get('reward_type') || ''} options={options({ '': 'Mọi loại', physical_gift: 'Quà tại cửa hàng', voucher: 'Voucher' })} onChange={reward_type => query({ reward_type, page: 1 })} /><Button onClick={() => query({ search: null, status: null, reward_type: null, page: 1 })}>Xóa bộ lọc</Button></div>
    <ResourceState {...r} empty={!r.data?.items.length} />{!r.loading && !r.error && <div className="care-list">{r.data?.items.map(item => <Card key={item.id} data-testid={`redemption-${item.id}`}><div className="card-head"><h3>{item.customer.hoten}</h3><Tag>{canFulfill(item) ? 'Chờ nhận quà' : redemptionLabels[item.status] || item.status}</Tag></div><p>{item.customer.sdt}</p><p><b>{item.reward.name}</b> · {benefit(item.reward)}</p><p>Mã <code className="care-code">{item.code}</code> · {item.points_spent} điểm</p><p>Đổi lúc {utcDate(item.redeemed_at)} · Hạn: {item.expires_at ? utcDate(item.expires_at) : 'Không hết hạn'}</p>{item.fulfilled_at && <p>Đã giao lúc {utcDate(item.fulfilled_at)} bởi {item.fulfilled_by_name || 'Nhân viên'}</p>}{item.used_at && <p>Đã dùng lúc {utcDate(item.used_at)}</p>}{canFulfill(item) && <Button type="primary" onClick={() => { select(item); setError(''); }}>Xác nhận giao quà</Button>}</Card>)}</div>}<PageNav data={r.data} onChange={page => query({ page })} />
    <Modal open={!!selected} title="Xác nhận đã giao quà" onCancel={() => { if (!busy) select(null); }} confirmLoading={busy} okText="Đã trao quà cho khách" cancelText="Chưa giao" onOk={async () => {
      setBusy(true); setError(''); try { const result = await post<{ already_fulfilled: boolean }>(`/api/admin/loyalty/redemptions/${selected!.id}/fulfill`, {}); select(null); r.reload(); message.success(result.already_fulfilled ? 'Quà đã được xác nhận giao trước đó' : 'Đã ghi nhận giao quà'); } catch (e) { setError((e as Error).message); r.reload(); } finally { setBusy(false); }
    }}><p>{selected?.customer.hoten} · {selected?.customer.sdt}</p><p>{selected?.reward.name} · <code>{selected?.code}</code></p><p>Kiểm tra khách và mã trước khi xác nhận.</p>{error && <Alert type="error" message={error} />}</Modal>
  </>;
}
export default function Loyalty({ me }: { me: Me }) {
  const [q, query] = useQuery(); const desk = me.user.role === 'letan';
  if (!['admin', 'manager', 'letan'].includes(me.user.role)) return <Result status="403" title="Bạn không có quyền quản lý điểm thưởng" />;
  const tabs: Record<string, string> = desk ? { redemptions: 'Tra mã và giao quà' } : { overview: 'Tổng quan', customers: 'Điểm của khách', redemptions: 'Tra mã và giao quà', rewards: 'Quà và voucher', transactions: 'Lịch sử điểm', config: 'Quy tắc và hạng' };
  const tab = q.get('tab') && q.get('tab')! in tabs ? q.get('tab')! : desk ? 'redemptions' : 'overview';
  const screens: Record<string, React.ReactNode> = { overview: <Overview />, customers: <Customers actorId={me.user.id} />, redemptions: <Redemptions />, rewards: <Rewards />, transactions: <Transactions />, config: <Rules /> };
  const changeTab = (tab: string) => query({ tab, page: null, view: null, search: null, status: null, reward_type: null, makh: null });
  return <><div className="page-heading"><h1>Điểm thưởng và quà tặng</h1><p>{desk ? 'Tra mã và xác nhận giao quà tại quầy.' : 'Xem điểm của khách, quản lý quà đổi thưởng và hạng thành viên.'}</p></div><Tabs className="care-tabs" activeKey={tab} items={Object.entries(tabs).map(([key, label]) => ({ key, label }))} onChange={changeTab} /><label className="care-mobile-tabs">Chọn mục cần làm<Select aria-label="Chọn mục điểm thưởng" value={tab} options={options(tabs)} onChange={changeTab} /></label><div key={tab}>{screens[tab]}</div></>;
}
