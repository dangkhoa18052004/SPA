import { useEffect, useState } from 'react';
import { useQuery } from './router';
import { Alert, Button, Card, Descriptions, Drawer, Empty, Form, Input, Result, Select, Space, Statistic, Table, Tag } from 'antd';
import { Pager, ResourceState, useResource } from './components';
import type { EmployeeAppointment, Me, Page } from './types';
import './crm.css';

type Customer = { id: number; name: string; phone: string | null; email: string | null; visits: number; last_visit: string | null; next_visit: string | null; segment: string; segment_label: string };
type Customers = Page<Customer> & { segments: Record<string, number>; segment_labels: Record<string, string> };
type History = Page<EmployeeAppointment> & { customer: Customer; preferences: Record<string, boolean>;
  notifications: { id: number; type: string; status: string; scheduled_at: string; sent_at: string | null; attempts: number }[] };
type Baseline = { impressions: number; clicks: number; ctr: number | null; conversions: number; conversion_rate: number | null;
  covered_services: number; active_services: number; coverage: number | null; latency_samples: number; p95_ms: number | null;
  by_placement: Record<string, { impressions: number; clicks: number }> };
const localDate = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const dateTime = (s: string | null) => s ? new Date(s).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }) : 'Chưa có';
const typeNames: Record<string, string> = { appointment_reminder_24h: 'Nhắc trước 24 giờ', appointment_reminder_2h: 'Nhắc trước 2 giờ', post_care: 'Dặn dò sau dịch vụ', review_request: 'Mời đánh giá', appointment_no_show: 'Hủy lịch không đến', booking_confirmation: 'Xác nhận đặt lịch' };
const statusNames: Record<string, string> = { pending: 'Đang chờ', processing: 'Đang xử lý', sent: 'Đã gửi', failed: 'Gửi thất bại', cancelled: 'Đã dừng' };

function CustomerHistory({ id }: { id: number }) {
  const [page, setPage] = useState(1);
  const resource = useResource<History>(`/api/admin/crm/customers/${id}?page=${page}&per_page=10`);
  const data = resource.data;
  return <><ResourceState {...resource} />{!resource.loading && !resource.error && data && <>
    <h2>{data.customer.name}</h2><Descriptions size="small" column={1} items={[{ key: 'phone', label: 'Điện thoại', children: data.customer.phone || 'Chưa có' }, { key: 'email', label: 'Email', children: data.customer.email || 'Chưa có' }]} />
    <h3 className="section-title">Khách đã đăng ký nhận</h3><Space wrap>{(['reminders', 'post_care', 'review_requests'] as const).map((key, i) => <Tag key={key} color={data.preferences[key] ? 'green' : 'default'}>{['Nhắc lịch', 'Dặn dò', 'Mời đánh giá'][i]}: {data.preferences[key] ? 'Có' : 'Chưa đăng ký'}</Tag>)}</Space><p className="muted">Khách tự thay đổi tại Hồ sơ → Thông báo & quyền riêng tư.</p>
    <h3 className="section-title">Lịch sử dịch vụ</h3>{data.items.length ? data.items.map(a => <Card size="small" className="small-card" key={a.id}><div className="card-head"><strong>#{a.id} · {dateTime(a.scheduled_at)}</strong><Tag>{a.status_label}</Tag></div><p>{a.services.map(s => s.name).join(', ') || 'Chưa có dịch vụ'}</p>{a.note && <p className="appointment-note">{a.note}</p>}</Card>) : <Empty description="Chưa có lịch sử dịch vụ" />}
    <Pager data={data} setPage={setPage} />
    <h3 className="section-title">20 thông báo gần nhất</h3>{data.notifications.length ? data.notifications.map(j => <div className="ledger-row" key={j.id}><div><strong>{typeNames[j.type] || j.type}</strong><p>{dateTime(j.sent_at || j.scheduled_at)}</p></div><Tag color={j.status === 'sent' ? 'green' : j.status === 'failed' ? 'red' : 'default'}>{statusNames[j.status] || j.status}</Tag></div>) : <Empty description="Chưa có thông báo" />}
  </>}</>;
}

function RecommendationBaseline() {
  const initial = localDate();
  const [draft, setDraft] = useState({ from: initial.slice(0, 8) + '01', to: initial });
  const [range, setRange] = useState(draft);
  const resource = useResource<Baseline>(`/api/admin/recommendations/baseline?${new URLSearchParams(range)}`);
  const data = resource.data;
  const percent = (value: number | null) => value === null ? 'Chưa có dữ liệu' : `${value} %`;
  return <section className="section-title" aria-label="Hiệu quả đề xuất"><div className="section-toolbar"><div><h2>Hiệu quả đề xuất</h2><p className="muted">Thẻ thực sự đã hiển thị cho khách đăng nhập, tối đa 6 thẻ/vị trí.</p></div><form className="business-range" onSubmit={e => { e.preventDefault(); setRange({ ...draft }); }}>
    <label>Từ ngày<Input aria-label="Báo cáo từ ngày" type="date" required value={draft.from} max={draft.to} onChange={e => setDraft({ ...draft, from: e.target.value })} /></label><label>Đến ngày<Input aria-label="Báo cáo đến ngày" type="date" required min={draft.from} value={draft.to} onChange={e => setDraft({ ...draft, to: e.target.value })} /></label><Button htmlType="submit">Xem báo cáo</Button></form></div>
    <ResourceState {...resource} />{!resource.loading && !resource.error && data && <>
      <div className="kpi-grid business-kpis" data-testid="recommendation-baseline"><Card><Statistic title="Lượt hiển thị" value={data.impressions} /><p>{data.clicks} lượt nhấp</p></Card><Card><Statistic title="Tỷ lệ nhấp (CTR@6)" value={percent(data.ctr)} /></Card><Card><Statistic title="Đặt/mua sau nhấp" value={percent(data.conversion_rate)} /><p>{data.conversions} lượt nhấp có đặt/mua trong 7 ngày</p></Card><Card><Statistic title="Dịch vụ được hiển thị" value={percent(data.coverage)} /><p>{data.covered_services}/{data.active_services} dịch vụ hoạt động</p></Card></div>
      <Card className="business-revenue"><div className="crm-placement-grid">{Object.entries(data.by_placement).map(([key, row]) => <div key={key}><h3>{({ home: 'Trang chủ', catalog: 'Danh sách dịch vụ', related: 'Dịch vụ liên quan', booking: 'Đặt lịch' } as Record<string, string>)[key]}</h3><p>{row.impressions} hiển thị · {row.clicks} nhấp</p></div>)}</div><p className="muted">Thời gian phản hồi p95: {data.p95_ms === null ? 'chưa có dữ liệu' : `${data.p95_ms} ms`} ({data.latency_samples} mẫu gần nhất, tối đa 5.000).</p></Card>
      <Alert className="small-card" type="info" showIcon message="Số liệu bắt đầu từ khi bật đo lường" description="Không tính ngược lượt hiển thị cũ. Đặt/mua sau nhấp là số liệu đối chiếu trong 7 ngày, có thể cập nhật khi khách đặt sau đó; không dùng để khẳng định đề xuất gây ra giao dịch." />
    </>}
  </section>;
}

export default function CRM({ me }: { me: Me }) {
  const [query, setQuery] = useQuery();
  const segment = query.get('segment') || '';
  const search = query.get('q') || '';
  const page = Math.max(1, Number(query.get('page')) || 1);
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const [selected, setSelected] = useState<number | null>(null);
  const allowed = ['admin', 'manager', 'letan'].includes(me.user.role) && me.features.crm;
  return !allowed ? <Result status="403" title="Bạn không có quyền xem chăm sóc khách hàng" extra={<Button href="/admin/profile">Trang cá nhân</Button>} /> : <><div className="page-heading"><span className="eyebrow">KHÁCH HÀNG</span><h1>Chăm sóc khách hàng</h1><p>Lọc nhóm khách, xem lịch sử dịch vụ và lựa chọn nhận thông báo.</p></div><CustomerList segment={segment} setFilters={() => setQuery({ segment: null, q: null, page: null })} setSegment={v => setQuery({ segment: v, page: null })} draft={draft} setDraft={setDraft} search={search} setSearch={v => setQuery({ q: v, page: null })} page={page} setPage={n => setQuery({ page: n > 1 ? n : null })} setSelected={setSelected} />
    {me.features.recommendation_metrics && ['admin', 'manager'].includes(me.user.role) && <RecommendationBaseline />}
    <Drawer title="Lịch sử khách hàng" open={selected !== null} onClose={() => setSelected(null)} width={600} destroyOnClose>{selected !== null && <CustomerHistory key={selected} id={selected} />}</Drawer>
  </>;
}

function CustomerList({ segment, setSegment, setFilters, draft, setDraft, search, setSearch, page, setPage, setSelected }: {
  segment: string; setSegment: (v: string) => void; setFilters: () => void; draft: string; setDraft: (v: string) => void; search: string; setSearch: (v: string) => void; page: number; setPage: (v: number) => void; setSelected: (v: number) => void }) {
  const resource = useResource<Customers>(`/api/admin/crm/customers?${new URLSearchParams({ segment, q: search, page: String(page), per_page: '20' })}`);
  const data = resource.data;
  const detail = (row: Customer) => <Button data-customer-id={row.id} onClick={() => setSelected(row.id)}>Xem lịch sử</Button>;
  return <><Form className="crm-filters" layout="vertical" onFinish={() => setSearch(draft.trim())}><Form.Item label="Tìm khách"><Input aria-label="Tìm khách hàng" placeholder="Tên, số điện thoại, email…" allowClear value={draft} onChange={e => setDraft(e.target.value)} maxLength={100} /></Form.Item><Form.Item label="Nhóm khách"><Select aria-label="Nhóm khách" value={segment} onChange={setSegment} options={[{ value: '', label: 'Tất cả khách đang hoạt động' }, ...Object.entries(data?.segment_labels || {}).map(([value, label]) => ({ value, label }))]} /></Form.Item><Form.Item label=" "><Space><Button htmlType="submit" type="primary">Tìm kiếm</Button><Button onClick={() => { setDraft(''); setFilters(); }}>Xóa bộ lọc</Button></Space></Form.Item></Form>
    <ResourceState {...resource} />{!resource.loading && !resource.error && data && <><Space wrap className="crm-segments">{Object.entries(data.segment_labels).map(([key, label]) => <Button key={key} type={key === segment ? 'primary' : 'default'} onClick={() => setSegment(key)}>{label}: {data.segments[key]}</Button>)}</Space><p className="muted">Phân nhóm theo lần phục vụ hoàn thành gần nhất. Khách đã có lịch sắp tới được hiển thị để tránh nhắc lại.</p>
      {!data.items.length ? <Empty description="Không có khách phù hợp" /> : <><div className="desktop-table"><Table rowKey="id" dataSource={data.items} pagination={false} columns={[{ title: 'Khách hàng', render: (_: unknown, r: Customer) => <><b>{r.name}</b><div className="muted">{r.phone || r.email || 'Chưa có liên hệ'}</div></> }, { title: 'Nhóm', dataIndex: 'segment_label' }, { title: 'Lần phục vụ gần nhất', dataIndex: 'last_visit', render: dateTime }, { title: 'Lịch sắp tới', dataIndex: 'next_visit', render: dateTime }, { title: 'Thao tác', render: (_: unknown, r: Customer) => detail(r) }]} /></div><div className="mobile-cards">{data.items.map(r => <Card key={r.id} className="small-card"><div className="card-head"><h2>{r.name}</h2><Tag>{r.segment_label}</Tag></div><p>{r.phone || r.email || 'Chưa có liên hệ'}</p><p className="muted">Đã phục vụ {r.visits} lần · Gần nhất: {dateTime(r.last_visit)}</p>{r.next_visit && <p>Lịch sắp tới: {dateTime(r.next_visit)}</p>}{detail(r)}</Card>)}</div></>}
      <Pager data={data} setPage={setPage} />
    </>}</>;
}
