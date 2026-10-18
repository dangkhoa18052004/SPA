import { useState } from 'react';
import { Alert, App, Button, Card, Empty, Input, Result, Select, Space, Statistic, Table, Tag } from 'antd';
import { ResourceState, useResource } from './components';
import type { Me } from './types';
import './reports.css';

type Person = { staff_id: number; name: string; sessions: number; worked_minutes: number; approved_minutes: number; overtime_minutes: number; late_minutes: number };
type Report = { from_date: string; to_date: string; business_scope: string; business: null | {
  revenue: { total: string; service: string; package: string }; earned_commission: string;
  appointments: { total: number; counts: Record<string, number>; no_show_recorded: number; cancelled_without_outcome: number };
  customers: { completed: number; returning: number; returning_rate: number | null; cohort: number; retained: number; retention_rate: number | null; cohort_from: string; cohort_to: string };
  revenue_series: { date: string; revenue: number; service_revenue: number; package_revenue: number }[] };
  workforce: { session_states: Record<string, number>; people: Person[]; approved_minutes: number; overtime_minutes: number; locked_payroll: string; locked_commission: string; locked_periods: number; excluded_partial_periods: number } };
type Runtime = { http: { scope: string; requests: number; client_errors: number; server_errors: number; sample_limit: number;
  routes: { route: string; method: string; requests: number; client_errors: number; server_errors: number; p95_ms: number }[] };
  worker: { state: string; last_seen_at: string | null }; jobs: { states: Record<string, number>; overdue_pending: number; stuck_processing: number };
  webhooks: Record<string, number>; gps: { verdict: string; reason: string; count: number }[] };
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const money = (v: number | string) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(v));
const hours = (v: number) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(v / 60) + ' giờ';
const percent = (v: number | null) => v === null ? 'Chưa có dữ liệu' : v.toLocaleString('vi-VN') + '%';
const date = (v: string) => v.split('-').reverse().join('/');
const gpsReason: Record<string, string> = { ok: 'Hợp lệ', outside_geofence: 'Ngoài bán kính', inaccurate_location: 'Sai số GPS lớn', stale_location: 'Vị trí đã cũ', outside_window: 'Ngoài thời gian chấm công', policy_disabled: 'GPS chưa bật', not_checked_in: 'Chưa chấm vào', already_checked_in: 'Đã chấm vào', already_checked_out: 'Đã chấm ra', open_session: 'Chưa kết thúc ca trước' };

function RuntimePanel({ query }: { query: string }) {
  const resource = useResource<Runtime>(`/api/admin/runtime/status?${query}`);
  const data = resource.data;
  const states: Record<string, string> = { ok: 'Đang hoạt động', degraded: 'Có lỗi trong lần xử lý gần nhất', stale: 'Mất tín hiệu trên 2 phút', unknown: 'Chưa nhận tín hiệu' };
  return <section data-testid="runtime-panel"><div className="section-toolbar"><h2>Giám sát vận hành</h2><Button onClick={resource.reload}>Làm mới giám sát</Button></div><ResourceState {...resource} />
    {!resource.loading && !resource.error && data && <>
      <Alert type="info" showIcon message="Số liệu HTTP là tối đa 5.000 yêu cầu trong 30 phút của tiến trình web đang trả lời. Khởi động lại sẽ đặt lại; nhiều tiến trình có mẫu riêng. Log JSON dùng mã yêu cầu để đối chiếu." />
      <div className="kpi-grid report-kpis"><Card><Statistic title="Yêu cầu HTTP trong mẫu" value={data.http.requests} /></Card><Card><Statistic title="Lỗi phía khách (4xx)" value={data.http.client_errors} /></Card><Card><Statistic title="Lỗi máy chủ (5xx)" value={data.http.server_errors} /></Card><Card><Statistic title="Thông báo chờ quá 5 phút" value={data.jobs.overdue_pending} /></Card></div>
      <Card className="report-section"><h2>Tiến trình gửi thông báo</h2><Tag color={data.worker.state === 'ok' ? 'green' : 'gold'}>{states[data.worker.state] || data.worker.state}</Tag><p className="muted">{data.worker.last_seen_at ? `Tín hiệu gần nhất: ${new Date(data.worker.last_seen_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}` : 'Khởi động lại worker sau khi bật giám sát để bắt đầu nhận tín hiệu.'}</p>
        <p>{data.jobs.states.failed || 0} thông báo gửi thất bại · {data.jobs.stuck_processing} tác vụ xử lý quá 10 phút.</p><p className="muted">Báo cáo chỉ đọc trạng thái; không gửi lại thư hoặc gọi ngân hàng.</p></Card>
      <Card className="report-section"><h2>API chậm và lỗi</h2><div className="report-table"><Table rowKey={r => r.method + r.route} size="small" dataSource={data.http.routes} pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: 650 }} columns={[
        { title: 'API', dataIndex: 'route', render: (v: string, r) => <span>{r.method} {v}</span> }, { title: 'Lượt', dataIndex: 'requests' }, { title: '4xx', dataIndex: 'client_errors' }, { title: '5xx', dataIndex: 'server_errors' }, { title: 'p95 (ms)', dataIndex: 'p95_ms' }]} /></div></Card>
      <div className="report-two"><Card><h2>Webhook thanh toán</h2><p className="muted">Trong khoảng ngày đã chọn, theo giờ ghi nhận UTC quy đổi sang Việt Nam.</p>{Object.keys(data.webhooks).length ? Object.entries(data.webhooks).map(([key, value]) => <p key={key}><Tag>{key}</Tag> {value}</p>) : <Empty description="Chưa có webhook trong khoảng ngày" />}</Card>
        <Card><h2>Kết quả kiểm tra GPS</h2><p className="muted">Các cơ sở được cấp quyền; không hiển thị tọa độ.</p>{data.gps.length ? data.gps.map(r => <p key={r.verdict + r.reason}><Tag color={r.verdict === 'accepted' ? 'green' : 'gold'}>{gpsReason[r.reason] || 'Lý do khác'}</Tag> {r.count} lượt</p>) : <Empty description="Chưa có sự kiện GPS trong khoảng ngày" />}</Card></div>
    </>}
  </section>;
}

function ReportPanel({ query }: { query: string }) {
  const resource = useResource<Report>(`/api/admin/bi/report?${query}`);
  const { message } = App.useApp();
  const [exporting, setExporting] = useState(false);
  async function download() {
    setExporting(true);
    try {
      const response = await fetch(`/api/admin/bi/export.csv?${query}`, { headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` }, credentials: 'same-origin' });
      if (!response.ok) { const error = await response.json(); throw new Error(error.message || error.msg || 'Không thể xuất báo cáo.'); }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = `binspa-bi-${resource.data?.from_date}-${resource.data?.to_date}.csv`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { message.error((e as Error).message); } finally { setExporting(false); }
  }
  const data = resource.data, business = data?.business;
  return <section data-testid="bi-report"><div className="section-toolbar"><h2>Kết quả trong kỳ</h2><Space wrap><Button onClick={resource.reload}>Làm mới báo cáo</Button><Button data-testid="bi-export" onClick={download} loading={exporting} disabled={resource.loading || !!resource.error}>Xuất CSV</Button></Space></div><ResourceState {...resource} />
    {!resource.loading && !resource.error && data && <>
      <Alert type={business ? 'info' : 'warning'} showIcon message={data.business_scope === 'single_site' ? 'Số liệu kinh doanh của spa tại địa điểm cố định; công và lương theo cơ sở đã chọn.' : business ? 'Lịch hẹn và thực thu là số liệu toàn spa. Công và lương chỉ gồm các cơ sở được cấp quyền.' : 'Lịch hẹn và thu tiền cũ chưa có thông tin cơ sở đáng tin cậy. Báo cáo này chỉ hiển thị công/lương thuộc cơ sở được cấp quyền.'} />
      {business && <>
        <div className="kpi-grid report-kpis"><Card><Statistic title="Tổng thực thu" value={money(business.revenue.total)} /><p className="muted">Dịch vụ {money(business.revenue.service)}<br />Bán gói {money(business.revenue.package)}</p></Card><Card><Statistic title="Lịch hẹn trong kỳ" value={business.appointments.total} /><p className="muted">{business.appointments.counts.completed || 0} hoàn thành · {business.appointments.counts.cancelled || 0} đã hủy</p></Card><Card><Statistic title="Khách quay lại" value={percent(business.customers.returning_rate)} /><p className="muted">{business.customers.returning}/{business.customers.completed} khách hoàn thành dịch vụ đã từng đến trước kỳ.</p></Card><Card><Statistic title="Không đến đã ghi nhận" value={business.appointments.no_show_recorded} /><p className="muted">Từ khi bật BI. {business.appointments.cancelled_without_outcome} lịch hủy chưa có phân loại không đến.</p></Card></div>
        <div className="report-two"><Card><h2>Khách kỳ trước quay lại</h2><Statistic value={percent(business.customers.retention_rate)} /><p>{business.customers.retained}/{business.customers.cohort} khách của kỳ {date(business.customers.cohort_from)}–{date(business.customers.cohort_to)} đã hoàn thành thêm dịch vụ trong kỳ đang xem.</p><p className="muted">Hai kỳ liền nhau có cùng số ngày. Không tính lịch chưa hoàn thành.</p></Card><Card><h2>Hoa hồng phát sinh</h2><Statistic value={money(business.earned_commission)} /><p className="muted">Hoa hồng còn hiệu lực, theo ngày ghi nhận. Khoản này có thể chưa vào bảng lương; không cộng thêm vào tổng lương đã khóa.</p></Card></div>
        <Card className="report-section"><h2>Thực thu từng ngày</h2><p className="muted">Theo ngày nhận thanh toán; dùng buổi liệu trình không thu lại lần hai.</p><div className="report-table"><Table rowKey="date" size="small" dataSource={business.revenue_series} pagination={{ pageSize: 7, showSizeChanger: false }} scroll={{ x: 540 }} columns={[
          { title: 'Ngày', dataIndex: 'date', render: date }, { title: 'Dịch vụ', dataIndex: 'service_revenue', render: money }, { title: 'Bán gói', dataIndex: 'package_revenue', render: money }, { title: 'Tổng', dataIndex: 'revenue', render: money }]} /></div></Card>
      </>}
      <h2 className="report-section">Công và lương theo cơ sở</h2><div className="kpi-grid report-kpis"><Card><Statistic title="Giờ công được duyệt" value={hours(data.workforce.approved_minutes)} /></Card><Card><Statistic title="Tăng ca được duyệt" value={hours(data.workforce.overtime_minutes)} /></Card><Card><Statistic title="Lương các kỳ đã khóa" value={money(data.workforce.locked_payroll)} /></Card><Card><Statistic title="Hoa hồng trong lương đã khóa" value={money(data.workforce.locked_commission)} /></Card></div>
      <Alert type="info" showIcon message={`Chỉ tính ${data.workforce.locked_periods} kỳ lương đã khóa nằm trọn khoảng ngày. ${data.workforce.excluded_partial_periods} kỳ chỉ nằm một phần trong khoảng ngày nên chưa được cộng.`} />
      <Card className="report-section"><h2>Giờ công nhân viên</h2><p className="muted">Theo ngày bắt đầu ca tại Việt Nam. Giờ được duyệt và tăng ca hiển thị riêng; đi muộn không tự động trừ tiền.</p>
        <div className="desktop-table"><Table rowKey="staff_id" dataSource={data.workforce.people} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
          { title: 'Nhân viên', dataIndex: 'name' }, { title: 'Phiên công', dataIndex: 'sessions' }, { title: 'Được duyệt', dataIndex: 'approved_minutes', render: hours }, { title: 'Tăng ca', dataIndex: 'overtime_minutes', render: hours }, { title: 'Đi muộn (phút)', dataIndex: 'late_minutes' }]} /></div>
        <div className="mobile-cards">{data.workforce.people.length ? data.workforce.people.map(p => <article className="report-person" key={p.staff_id}><strong>{p.name}</strong><p>{p.sessions} phiên công · {hours(p.approved_minutes)} được duyệt</p><p className="muted">Tăng ca {hours(p.overtime_minutes)} · Đi muộn {p.late_minutes} phút</p></article>) : <Empty description="Chưa có dữ liệu công trong khoảng ngày" />}</div>
      </Card>
    </>}
  </section>;
}

export default function Reports({ me }: { me: Me }) {
  const initial = today();
  const [draft, setDraft] = useState({ from: initial.slice(0, 8) + '01', to: initial, branch_id: '' });
  const [range, setRange] = useState(draft);
  const [tab, setTab] = useState('reports');
  const invalid = !draft.from || !draft.to || draft.to < draft.from || Date.parse(draft.to) - Date.parse(draft.from) > 365 * 86400000;
  const query = new URLSearchParams(Object.fromEntries(Object.entries(range).filter(([, v]) => v))).toString();
  if (!['admin', 'manager'].includes(me.user.role) || !me.features.bi) return <><Result status="403" title="Bạn không có quyền xem báo cáo này" /></>;
  return <><div className="page-heading"><span className="eyebrow">BÁO CÁO BIN SPA</span><h1>Kinh doanh và vận hành</h1><p>Thực thu, khách quay lại và công lương với nguồn số liệu rõ ràng.</p></div>
    <Card className="report-filters"><form onSubmit={e => { e.preventDefault(); if (!invalid) setRange({ ...draft }); }}><label>Từ ngày<Input type="date" aria-label="Báo cáo từ ngày" value={draft.from} max={draft.to} onChange={e => setDraft({ ...draft, from: e.target.value })} /></label><label>Đến ngày<Input type="date" aria-label="Báo cáo đến ngày" value={draft.to} min={draft.from} onChange={e => setDraft({ ...draft, to: e.target.value })} /></label>
      <label>Cơ sở công/lương<Select aria-label="Cơ sở báo cáo" value={draft.branch_id} onChange={branch_id => setDraft({ ...draft, branch_id })} options={[{ value: '', label: 'Tất cả cơ sở được cấp' }, ...me.branches.filter(b => me.managed_branch_ids.includes(b.id)).map(b => ({ value: String(b.id), label: b.name }))]} /></label><Button htmlType="submit" type="primary" disabled={invalid}>Xem báo cáo</Button></form>{invalid && <p role="alert">Chọn khoảng ngày hợp lệ, tối đa 366 ngày.</p>}</Card>
    {me.user.role === 'admin' && me.features.observability && <Space className="report-tabs" wrap><Button type={tab === 'reports' ? 'primary' : 'default'} onClick={() => setTab('reports')}>Báo cáo kinh doanh</Button><Button type={tab === 'runtime' ? 'primary' : 'default'} onClick={() => setTab('runtime')}>Giám sát hệ thống</Button></Space>}
    {tab === 'runtime' ? <RuntimePanel query={query} /> : <ReportPanel query={query} />}
  </>;
}
