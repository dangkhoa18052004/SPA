import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Form, Input, InputNumber, Modal, Progress, Radio, Result, Select, Skeleton, Space, Statistic, Table, Tabs, Tag } from 'antd';
import { api, post } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { fold, spaToday, vnd } from '../booking/model';
import { dayText, progress, saleLabels, saleState, treatmentLabels, usageLabels, validityLabel } from './model';
import type { CustomerTreatment, SaleState, ServicePackage } from './model';
import { AppLink } from './ui';
import '../booking/booking.css';
import './catalog.css';

const fallbackImage = '/static/images/default-package.svg';
export const saleTag = (p: ServicePackage) => { const s = saleLabels[saleState(p)]; return <Tag color={s.color}>{s.label}</Tag>; };
const treatmentTag = (status: string) => <Tag color={treatmentLabels[status]?.color}>{treatmentLabels[status]?.label || status}</Tag>;

function GiftForm({ treatment, services, onClose, onDone }: { treatment: CustomerTreatment; services: { madv: number; tendv: string }[]; onClose: () => void; onDone: () => void }) {
  const [form] = Form.useForm<{ madv: number; quantity: number; mode: 'unlimited' | 'days' | 'date'; validity_days?: number; expires_at?: string; gift_note?: string }>();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const mode = Form.useWatch('mode', form) || 'unlimited';
  async function save(values: { madv: number; quantity: number; mode: string; validity_days?: number; expires_at?: string; gift_note?: string }) {
    setBusy(true); setError('');
    const body: Record<string, unknown> = { makh: treatment.makh, madv: values.madv, quantity: values.quantity, gift_note: values.gift_note?.trim() || '' };
    if (values.mode === 'days') body.validity_days = values.validity_days;
    if (values.mode === 'date') body.expires_at = values.expires_at;
    try { await post(`/api/admin/packages/treatments/${treatment.mathe}/gifts`, body); message.success('Đã tặng dịch vụ vào liệu trình.'); onDone(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Modal open title="Tặng dịch vụ" onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden>
    <p className="muted">{treatment.customer_name} · {treatment.tengoi} (#{treatment.mathe})</p>
    <Form form={form} layout="vertical" onFinish={save} disabled={busy} initialValues={{ quantity: 1, mode: 'unlimited', validity_days: 30 }}>
      <Form.Item label="Dịch vụ tặng" name="madv" rules={[{ required: true, message: 'Chọn dịch vụ' }]}>
        <Select showSearch aria-label="Dịch vụ tặng" optionFilterProp="label" options={services.map(s => ({ value: s.madv, label: s.tendv }))} /></Form.Item>
      <Form.Item label="Số buổi" name="quantity" rules={[{ required: true, message: 'Nhập số buổi' }]}><InputNumber min={1} max={10000} precision={0} style={{ width: '100%' }} /></Form.Item>
      <Form.Item label="Thời hạn" name="mode"><Radio.Group optionType="button" options={[{ value: 'unlimited', label: 'Vô thời hạn' }, { value: 'days', label: 'Số ngày' }, { value: 'date', label: 'Đến ngày' }]} /></Form.Item>
      {mode === 'days' && <Form.Item label="Số ngày" name="validity_days" rules={[{ required: true, message: 'Nhập số ngày' }]}><InputNumber min={1} max={10000} precision={0} style={{ width: '100%' }} /></Form.Item>}
      {mode === 'date' && <Form.Item label="Ngày hết hạn" name="expires_at" rules={[{ required: true, message: 'Chọn ngày' }]}><Input type="date" min={spaToday()} aria-label="Ngày hết hạn" /></Form.Item>}
      <Form.Item label="Ghi chú" name="gift_note" rules={[{ max: 2000 }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item>
      {error && <Alert role="alert" type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
      <Space><Button onClick={onClose} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy}>Xác nhận tặng</Button></Space>
    </Form>
  </Modal>;
}

export function TreatmentDrawer({ mathe, onClose, onChanged }: { mathe: number | null; onClose: () => void; onChanged: () => void }) {
  const [data, setData] = useState<{ treatment: CustomerTreatment; can_gift: boolean; services: { madv: number; tendv: string }[] }>();
  const [error, setError] = useState('');
  const [gifting, setGifting] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true; setData(undefined); setError('');
    if (mathe !== null) api<NonNullable<typeof data>>(`/api/admin/packages/treatments/${mathe}`).then(d => { if (active) setData(d); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [mathe, revision]);
  const t = data?.treatment;
  const names = new Map((t?.items || []).map(i => [i.id, `${i.tendv} · ${i.source_type === 'gift' ? 'Tặng' : 'Trong gói'}`]));
  return <Drawer open={mathe !== null} onClose={onClose} width={720} title={mathe !== null ? `Liệu trình #${mathe}` : ''} destroyOnHidden
    extra={t && data?.can_gift && t.status !== 'cancelled' && <Button type="primary" onClick={() => setGifting(true)}>Tặng dịch vụ</Button>}>
    {error ? <Alert type="error" showIcon message={error} /> : !t ? <Skeleton active /> : <>
      <h2 style={{ marginTop: 0 }}>{t.tengoi}</h2>
      <Descriptions column={{ xs: 1, md: 2 }} size="small" items={[{ key: 'c', label: 'Khách hàng', children: `${t.customer_name}${t.phone ? ` · ${t.phone}` : ''}` },
        { key: 's', label: 'Trạng thái', children: treatmentTag(t.status) }, { key: 'p', label: 'Ngày mua', children: dayText(t.purchased_at) },
        { key: 'a', label: 'Kích hoạt', children: dayText(t.activated_at) }, { key: 'e', label: 'Hạn dùng', children: dayText(t.expires_at) }]} />
      {(['package', 'gift'] as const).map(source => { const items = t.items.filter(i => (i.source_type || 'package') === source); return items.length ? <div key={source} className="section-title">
        <h3>{source === 'gift' ? 'Dịch vụ tặng' : 'Dịch vụ trong gói'}</h3>
        <Table size="small" rowKey="id" pagination={false} dataSource={items} scroll={{ x: 560 }} columns={[
          { title: 'Dịch vụ', render: (_: unknown, i: CustomerTreatment['items'][number]) => <><strong>{i.tendv}</strong><div className="muted">Hạn {dayText(i.effective_expires_at)}{i.usable === false ? ' · không khả dụng' : ''}</div>
            {source === 'gift' && <div className="muted">Tặng bởi {i.gifted_by_name || 'N/A'} · {dayText(i.created_at, '')}{i.gift_note ? ` · ${i.gift_note}` : ''}</div>}</> },
          { title: 'Tổng', dataIndex: 'total_sessions' }, { title: 'Đã dùng', dataIndex: 'consumed' }, { title: 'Đang giữ', dataIndex: 'reserved' },
          { title: 'Còn', dataIndex: 'available_sessions', render: (v: number) => <strong>{v}</strong> }]} /></div> : null; })}
      <h3 className="section-title">Lịch sử sử dụng</h3>
      {!t.history?.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chưa có lịch sử sử dụng" /> : <ul className="history-list">{t.history.map(h => <li key={h.id}>
        <div><strong>{names.get(h.the_item_id) || h.tendv}</strong><div className="muted">Lịch hẹn <a href={`/admin/appointments?q=${h.malh}`}>#{h.malh}</a></div></div>
        <span>{usageLabels[h.state] || h.state} · {dayText(h.consumed_at || h.released_at || h.reserved_at, '')}</span></li>)}</ul>}
    </>}
    {gifting && t && <GiftForm treatment={t} services={data?.services || []} onClose={() => setGifting(false)} onDone={() => { setGifting(false); setRevision(n => n + 1); onChanged(); }} />}
  </Drawer>;
}

function PackageList({ canManage }: { canManage: boolean }) {
  const [query, setQuery] = useQuery();
  const resource = useResource<{ packages: ServicePackage[]; package_revenue: string }>(canManage ? '/api/admin/packages' : '');
  const search = query.get('q') || ''; const sale = (query.get('sale') || '') as SaleState | '';
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const all = resource.data?.packages || [];
  const tokens = fold(search).split(/\s+/).filter(Boolean);
  const rows = all.filter(p => (!sale || saleState(p) === sale) && tokens.every(t => fold(`#${p.magoi} ${p.tengoi} ${p.items.map(i => i.tendv).join(' ')}`).includes(t)));
  const actions = (p: ServicePackage) => <Space wrap size={6}><AppLink href={`/admin/packages/${p.magoi}`} size="small">Xem</AppLink>
    <AppLink href={`/admin/packages/${p.magoi}/edit`} size="small">Sửa</AppLink></Space>;
  const items = (p: ServicePackage) => p.items.map(i => <div key={i.madv}>{i.tendv} <strong>× {i.total_sessions}</strong></div>);
  return <>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Gói đang hoạt động" value={resource.data ? all.filter(p => p.active).length : '…'} /></Card>
      <Card><Statistic title="Đã bán" value={resource.data ? all.reduce((n, p) => n + (p.sold_count || 0), 0) : '…'} /></Card>
      <Card><Statistic title="Liệu trình đang dùng" value={resource.data ? all.reduce((n, p) => n + (p.active_treatments || 0), 0) : '…'} /></Card>
      <Card><Statistic title="Doanh thu bán gói" value={resource.data ? vnd(resource.data.package_revenue) : '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters customers">
        <Select aria-label="Trạng thái bán" value={sale} onChange={v => setQuery({ sale: v || null })} options={[{ value: '', label: 'Tất cả trạng thái' },
          ...Object.entries(saleLabels).map(([value, s]) => ({ value, label: s.label }))]} />
        <Input.Search aria-label="Tìm gói" placeholder="Tên gói, mã # hoặc dịch vụ trong gói" allowClear value={draft}
          onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ q: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null })} />
        <Button disabled={!search && !sale} onClick={() => setQuery({ q: null, sale: null })}>Xóa bộ lọc</Button>
      </div>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Không tìm thấy gói dịch vụ" /> : <>
        <div className="desktop-table section-title"><Table rowKey="magoi" dataSource={rows} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
          { title: 'Gói dịch vụ', render: (_: unknown, p: ServicePackage) => <Space><img className="catalog-thumb" src={p.image_url || fallbackImage} alt="" /><span><strong>{p.tengoi}</strong><div className="muted">#{p.magoi} · đã bán {p.sold_count || 0}</div></span></Space> },
          { title: 'Dịch vụ', render: (_: unknown, p: ServicePackage) => items(p) },
          { title: 'Giá gói', align: 'right' as const, render: (_: unknown, p: ServicePackage) => <><strong>{vnd(p.giagoi)}</strong>{Number(p.savings) > 0 && <div className="muted">tiết kiệm {vnd(p.savings)}</div>}</> },
          { title: 'Hiệu lực', render: (_: unknown, p: ServicePackage) => validityLabel(p.validity_months) },
          { title: 'Trạng thái', render: (_: unknown, p: ServicePackage) => saleTag(p) }, { title: 'Thao tác', render: (_: unknown, p: ServicePackage) => actions(p) }]} /></div>
        <div className="mobile-cards section-title">{rows.map(p => <Card key={p.magoi} className="small-card"><div className="card-head"><Space><img className="catalog-thumb" src={p.image_url || fallbackImage} alt="" /><h2>{p.tengoi}</h2></Space>{saleTag(p)}</div>
          <p><strong>{vnd(p.giagoi)}</strong> · {validityLabel(p.validity_months)}</p><div className="muted">{items(p)}</div><div className="section-title">{actions(p)}</div></Card>)}</div>
      </>)}
    </Card>
  </>;
}

function TreatmentList() {
  const [query, setQuery] = useQuery();
  const search = query.get('tq') || ''; const status = query.get('tstatus') || '';
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const resource = useResource<{ treatments: CustomerTreatment[] }>(`/api/admin/packages/treatments?${new URLSearchParams({ ...(search ? { search } : {}), ...(status ? { status } : {}) })}`);
  const viewing = Number(query.get('mathe')) || null;
  const rows = resource.data?.treatments || [];
  const bar = (t: CustomerTreatment) => { const p = progress(t); return <div className="treatment-progress">{p.used}/{p.total} buổi<Progress percent={p.percent} showInfo={false} size="small" /></div>; };
  return <Card>
    <div className="booking-filters customers">
      <Select aria-label="Trạng thái liệu trình" value={status} onChange={v => setQuery({ tstatus: v || null })}
        options={[{ value: '', label: 'Tất cả trạng thái' }, ...Object.entries(treatmentLabels).map(([value, s]) => ({ value, label: s.label }))]} />
      <Input.Search aria-label="Tìm liệu trình" placeholder="Tên khách, SĐT hoặc mã liệu trình" allowClear value={draft}
        onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ tq: null }, true); }} onSearch={v => setQuery({ tq: v.trim() || null })} />
      <Button disabled={!search && !status} onClick={() => setQuery({ tq: null, tstatus: null })}>Xóa bộ lọc</Button>
    </div>
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Không tìm thấy liệu trình" /> : <>
      <div className="desktop-table section-title"><Table rowKey="mathe" dataSource={rows} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
        { title: 'Mã', dataIndex: 'mathe', render: (v: number) => <strong>#{v}</strong> },
        { title: 'Khách hàng', render: (_: unknown, t: CustomerTreatment) => <>{t.customer_name}<div className="muted">{t.phone || ''}</div></> },
        { title: 'Gói', dataIndex: 'tengoi' }, { title: 'Tiến độ', render: (_: unknown, t: CustomerTreatment) => bar(t), width: 170 },
        { title: 'Hạn dùng', render: (_: unknown, t: CustomerTreatment) => dayText(t.expires_at) },
        { title: 'Trạng thái', dataIndex: 'status', render: treatmentTag },
        { title: 'Thao tác', render: (_: unknown, t: CustomerTreatment) => <Button size="small" onClick={() => setQuery({ mathe: t.mathe })}>Chi tiết</Button> }]} /></div>
      <div className="mobile-cards section-title">{rows.map(t => <Card key={t.mathe} className="small-card"><div className="card-head"><strong>#{t.mathe} · {t.customer_name}</strong>{treatmentTag(t.status)}</div>
        <p>{t.tengoi}</p>{bar(t)}<p className="muted">Hạn {dayText(t.expires_at)}</p><Button size="small" onClick={() => setQuery({ mathe: t.mathe })}>Chi tiết</Button></Card>)}</div>
    </>)}
    <TreatmentDrawer mathe={viewing} onClose={() => setQuery({ mathe: null })} onChanged={resource.reload} />
  </Card>;
}

/**
 * Packages for sale and customers' treatments. Admin/manager manage packages; technicians only
 * see treatments (as the API allows). The legacy #treatments link still opens that tab.
 */
export default function Packages({ me }: { me: Me }) {
  const [query, setQuery] = useQuery();
  const canManage = ['admin', 'manager'].includes(me.user.role);
  const canTreat = canManage || me.user.role === 'staff';
  useEffect(() => { if (window.location.hash === '#treatments') { window.history.replaceState(null, '', window.location.pathname); setQuery({ tab: 'treatments' }, true); } }, []);
  if (!canTreat) return <Result status="403" title="Không có quyền xem gói và liệu trình" subTitle="Bán gói cho khách ở mục Bán gói." extra={<Button href="/admin/package-sales">Bán gói</Button>} />;
  const tab = !canManage || query.get('tab') === 'treatments' ? 'treatments' : 'packages';
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">DANH MỤC</span><h1>{canManage ? 'Gói dịch vụ' : 'Liệu trình khách hàng'}</h1>
        <p>{canManage ? 'Gói đang bán và tiến độ sử dụng liệu trình của khách.' : 'Tiến độ sử dụng, buổi đang giữ và dịch vụ tặng của khách.'}</p></div>
      {canManage && <Space wrap><Button href="/admin/package-sales">Bán gói</Button><AppLink href="/admin/packages/new" type="primary">+ Tạo gói mới</AppLink></Space>}
    </div>
    {canManage ? <Tabs activeKey={tab} onChange={key => setQuery({ tab: key === 'packages' ? null : key }, true)} items={[
      { key: 'packages', label: 'Gói dịch vụ', children: <PackageList canManage /> },
      { key: 'treatments', label: 'Liệu trình khách hàng', children: <TreatmentList /> }]} /> : <TreatmentList />}
  </>;
}
