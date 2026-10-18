import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Collapse, Empty, Input, Progress, Select, Space, Statistic, Table } from 'antd';
import { api } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import { spaToday, statusLabel, vnd } from '../booking/model';
import { options } from './model';
import './care.css';

type Summary = { revenue: { total: number; service: number; package: number; transactions: number; average_transaction: number };
  appointments: { total: number; completed: number; cancelled: number; cancel_rate: number }; new_customers: number };
type Series = { records: { date: string; revenue: number; service_revenue?: number; package_revenue?: number }[] };
type AiSummary = { facts: string[]; summary: string; suggestions: string[]; removed_unverified: number; from_date: string; to_date: string };
function AiPanel({ from, to }: { from: string; to: string }) {
  const state = useResource<{ configured: boolean }>('/api/ai/status'); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [result, setResult] = useState<AiSummary>();
  const active = useRef(true); const inFlight = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  async function generate() {
    if (inFlight.current) return; inFlight.current = true; setBusy(true); setError(''); setResult(undefined);
    try { const value = await api<AiSummary>('/api/ai/business-summary', { method: 'POST', body: JSON.stringify({ from, to }) }, false, 30000); if (active.current) setResult(value); }
    catch (e) { if (active.current) setError((e as Error).message); } finally { inFlight.current = false; if (active.current) setBusy(false); }
  }
  return <Card className="care-section" id="ai-summary-panel" title="Tóm tắt kinh doanh bằng AI"><p>AI nhận số liệu tổng hợp của khoảng ngày đang xem. Các con số do hệ thống tính; nhận xét và gợi ý cần được kiểm tra trước khi áp dụng.</p><ResourceState {...state} />
    {state.data?.configured === false && <Alert type="info" message="AI chưa được cấu hình. Bạn vẫn xem được toàn bộ số liệu và báo cáo." />}
    <Button className="care-section" type="primary" disabled={state.loading || !!state.error || !state.data?.configured} loading={busy} onClick={() => { void generate(); }}>Tạo tóm tắt cho khoảng đang xem</Button>
    {error && <Alert className="care-section" showIcon type="error" message={error} description="Bạn có thể bấm tạo lại khi cần. Hệ thống không tự gửi lại yêu cầu AI." />}
    {result && <div className="care-section" data-testid="business-ai-result"><h3>Số liệu đã đối chiếu</h3><ul className="care-summary-facts">{result.facts.map((fact, i) => <li key={i}>{fact}</li>)}</ul><h3>Nhận xét của AI</h3><p className="care-text">{result.summary || 'AI chưa có nhận xét phù hợp với dữ liệu.'}</p><h3>Gợi ý để cân nhắc</h3><ul className="care-summary-facts">{result.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>{!!result.removed_unverified && <Alert type="info" message="Một số nội dung có số liệu chưa xác minh đã được lược bỏ." />}</div>}
  </Card>;
}
function FinanceData({ from, to, group }: { from: string; to: string; group: string }) {
  const query = new URLSearchParams({ from, to }).toString();
  const summary = useResource<Summary>(`/api/analytics/summary?${query}`);
  const series = useResource<Series>(`/api/analytics/revenue-timeseries?${query}&group_by=${group}`);
  const top = useResource<{ top_services: { madv: number; tendv: string; booking_count: number }[] }>(`/api/analytics/top-services?${query}&limit=10`);
  const statuses = useResource<{ counts: Record<string, number>; percentages: Record<string, number>; total_appointments: number }>(`/api/analytics/appointment-stats?${query}`);
  const kpi = useResource<{ general: { total_customers: number; active_staff: number }; today: { working_staff: number }; date: string }>('/api/analytics/kpi-cards');
  const max = Math.max(1, ...(top.data?.top_services.map(r => r.booking_count) || []));
  return <><ResourceState {...summary} />{!summary.loading && !summary.error && summary.data && <div className="kpi-grid business-kpis" data-testid="business-finance">
    <Card><Statistic title="Tổng thực thu" value={vnd(summary.data.revenue.total)} /><p>Dịch vụ {vnd(summary.data.revenue.service)}<br />Bán gói {vnd(summary.data.revenue.package)}</p></Card>
    <Card><Statistic title="Lịch hẹn" value={summary.data.appointments.total} /><p>{summary.data.appointments.completed} lịch hoàn thành</p></Card>
    <Card><Statistic title="Khách mới" value={summary.data.new_customers} /></Card><Card><Statistic title="Tỷ lệ hủy" value={summary.data.appointments.cancel_rate} suffix="%" /></Card>
    <Card><Statistic title="Thực thu trung bình / giao dịch" value={vnd(summary.data.revenue.average_transaction)} /><p>{summary.data.revenue.transactions} giao dịch đã thu tiền</p></Card>
  </div>}
    <Card className="care-section" title={group === 'month' ? 'Thực thu theo tháng' : 'Thực thu theo ngày'}><ResourceState {...series} />{!series.loading && !series.error && <>
      <div className="revenue-bars" role="img" aria-label="Biểu đồ tổng thực thu; bảng số liệu đầy đủ ở bên dưới">{series.data?.records.map(row => <div key={row.date} className="revenue-bar" title={`${row.date}: ${vnd(row.revenue)}`}><span className="revenue-bar-fill" style={{ height: `${Math.max(row.revenue ? 3 : 0, row.revenue / Math.max(1, ...series.data!.records.map(r => r.revenue)) * 100)}%` }} /><small>{group === 'month' ? row.date.slice(5) : row.date.slice(8)}</small></div>)}</div>
      <Collapse items={[{ key: 'figures', label: 'Xem số liệu thực thu chi tiết', children: <Table rowKey="date" dataSource={series.data?.records} pagination={{ pageSize: 10, showSizeChanger: false }} scroll={{ x: 560 }} columns={[{ title: group === 'month' ? 'Tháng' : 'Ngày', dataIndex: 'date' }, { title: 'Dịch vụ', dataIndex: 'service_revenue', render: vnd }, { title: 'Bán gói', dataIndex: 'package_revenue', render: vnd }, { title: 'Tổng thực thu', dataIndex: 'revenue', render: vnd }]} /> }]} />
    </>}</Card>
    <div className="list-grid care-section"><Card title="Dịch vụ được đặt nhiều"><p>Gồm lịch đã xác nhận, đang làm hoặc hoàn thành. Số lượt này không phải thực thu.</p><ResourceState {...top} />{!top.loading && !top.error && (top.data?.top_services.length ? top.data.top_services.map(row => <div className="care-chart-row" key={row.madv}><span>{row.tendv}</span><Progress percent={row.booking_count / max * 100} showInfo={false} /><b>{row.booking_count} lượt</b></div>) : <Empty description="Chưa có lượt đặt trong khoảng ngày này" />)}</Card>
      <Card title="Trạng thái lịch hẹn"><ResourceState {...statuses} />{!statuses.loading && !statuses.error && (statuses.data?.total_appointments ? Object.entries(statuses.data.counts).map(([key, count]) => <div className="care-chart-row" key={key}><span>{statusLabel[key] || key}</span><Progress percent={statuses.data!.percentages[key]} showInfo={false} /><b>{count} lịch</b></div>) : <Empty description="Chưa có lịch trong khoảng ngày này" />)}</Card></div>
    <Collapse className="care-section" items={[{ key: 'current', label: 'Quy mô spa và nhân sự hôm nay', children: <><ResourceState {...kpi} />{!kpi.loading && !kpi.error && kpi.data && <><p>Số liệu hiện tại; nhân viên có ca theo lịch phân công ngày {kpi.data.date}. Đây là lịch dự kiến, không xác nhận đã chấm vào.</p><div className="kpi-grid"><Card><Statistic title="Tổng khách đã tạo hồ sơ" value={kpi.data.general.total_customers} /></Card><Card><Statistic title="Nhân viên đang hoạt động" value={kpi.data.general.active_staff} /></Card><Card><Statistic title="Nhân viên có ca theo lịch hôm nay" value={kpi.data.today.working_staff} /></Card></div></>}</> }]} />
    <AiPanel key={query} from={from} to={to} />
  </>;
}
export default function DashboardDetails() {
  const [q, query] = useQuery(); const today = spaToday(); const from = q.get('from') || today.slice(0, 8) + '01'; const to = q.get('to') || today;
  const [draft, setDraft] = useState({ from, to }); const group = q.get('group') === 'month' ? 'month' : 'day';
  useEffect(() => setDraft({ from, to }), [from, to]);
  const valid = (a: string, b: string) => /^\d{4}-\d{2}-\d{2}$/.test(a) && /^\d{4}-\d{2}-\d{2}$/.test(b) && Number.isFinite(Date.parse(a)) && Number.isFinite(Date.parse(b)) && a <= b && Date.parse(b) - Date.parse(a) <= 365 * 86400000;
  return <section aria-label="Thực thu"><div className="section-toolbar"><div><h2>Hiệu quả kinh doanh</h2><p>Theo ngày nhận tiền; buổi liệu trình không tính thu thêm lần nữa.</p></div></div>
    <Space wrap className="care-section"><Button onClick={() => query({ from: today, to: today })}>Hôm nay</Button><Button onClick={() => query({ from: today.slice(0, 8) + '01', to: today })}>Tháng này đến hôm nay</Button><Button onClick={() => query({ from: new Date(Date.parse(today + 'T00:00:00Z') - 29 * 86400000).toISOString().slice(0, 10), to: today })}>30 ngày gần nhất</Button></Space>
    <form className="business-range care-section" onSubmit={e => { e.preventDefault(); if (valid(draft.from, draft.to)) query(draft); }}><label>Từ ngày<Input aria-label="Từ ngày" type="date" value={draft.from} onChange={e => setDraft({ ...draft, from: e.target.value })} /></label><label>Đến ngày<Input aria-label="Đến ngày" type="date" value={draft.to} onChange={e => setDraft({ ...draft, to: e.target.value })} /></label><Button type="primary" htmlType="submit" disabled={!valid(draft.from, draft.to)}>Xem báo cáo</Button><Select aria-label="Nhóm biểu đồ thực thu" value={group} options={options({ day: 'Theo ngày', month: 'Theo tháng' })} onChange={group => query({ group })} /></form>
    {!valid(draft.from, draft.to) && <Alert type="warning" message="Chọn ngày bắt đầu không sau ngày kết thúc, tối đa 366 ngày." />}
    {valid(from, to) ? <FinanceData key={`${from}:${to}:${group}`} from={from} to={to} group={group} /> : <Alert type="error" message="Khoảng ngày trong liên kết không hợp lệ. Chọn lại ngày rồi bấm Xem báo cáo." />}
  </section>;
}
