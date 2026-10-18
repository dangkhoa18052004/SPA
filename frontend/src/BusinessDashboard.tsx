import { useState } from 'react';
import { Alert, Button, Card, Empty, Input, Select, Space, Statistic, Table, Tag } from 'antd';
import { ResourceState, useResource } from './components';
import type { Me } from './types';
import DashboardDetails from './admin/care/DashboardDetails';

type Appointment = { malh: number; ngaygio: string; khachhang_hoten: string; dichvu_ten: string;
  nhanvien_hoten?: string; trangthai: string; trangthai_vi: string };
type Summary = { revenue: { total: number; service: number; package: number; average_transaction: number };
  appointments: { total: number; completed: number; cancelled: number; cancel_rate: number }; new_customers: number };
type Revenue = { records: { date: string; revenue: number }[] };
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const money = (value: number) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value);
const time = (value: string) => value.slice(11, 16);
const color: Record<string, string> = { pending: 'gold', confirmed: 'blue', in_progress: 'cyan', completed: 'green', cancelled: 'default' };

function Finance() {
  const initial = today();
  const [draft, setDraft] = useState({ from: initial.slice(0, 8) + '01', to: initial });
  const [range, setRange] = useState(draft);
  const invalid = !draft.from || !draft.to || draft.from > draft.to;
  const query = new URLSearchParams(range).toString();
  const summary = useResource<Summary>(`/api/analytics/summary?${query}`);
  const series = useResource<Revenue>(`/api/analytics/revenue-timeseries?${query}&group_by=day`);
  const max = Math.max(1, ...(series.data?.records.map(r => r.revenue) || []));
  return <section aria-label="Thực thu"><div className="section-toolbar"><div><h2>Hiệu quả kinh doanh</h2><span className="muted">Theo ngày nhận thanh toán</span></div>
    <form className="business-range" onSubmit={e => { e.preventDefault(); if (!invalid) setRange({ ...draft }); }}>
      <label>Từ ngày<Input type="date" aria-label="Từ ngày" value={draft.from} max={draft.to} onChange={e => setDraft({ ...draft, from: e.target.value })} /></label>
      <label>Đến ngày<Input type="date" aria-label="Đến ngày" value={draft.to} min={draft.from} onChange={e => setDraft({ ...draft, to: e.target.value })} /></label>
      <Button htmlType="submit" type="primary" disabled={invalid}>Xem báo cáo</Button></form></div>
    {invalid && <Alert type="warning" message="Chọn khoảng ngày hợp lệ." />}
    <ResourceState {...summary} />
    {!summary.loading && !summary.error && summary.data && <>
      <div className="kpi-grid business-kpis" data-testid="business-finance">
        <Card><Statistic title="Tổng thực thu" value={money(summary.data.revenue.total)} /><p className="muted">Dịch vụ {money(summary.data.revenue.service)}<br />Bán gói {money(summary.data.revenue.package)}</p></Card>
        <Card><Statistic title="Lịch hẹn" value={summary.data.appointments.total} /><p className="muted">{summary.data.appointments.completed} lịch hoàn thành</p></Card>
        <Card><Statistic title="Khách mới" value={summary.data.new_customers} /><p className="muted">Trong khoảng ngày đã chọn</p></Card>
        <Card><Statistic title="Tỷ lệ hủy lịch" value={summary.data.appointments.cancel_rate} suffix="%" /><p className="muted">{summary.data.appointments.cancelled} lịch hủy</p></Card>
      </div>
      <Card className="business-revenue"><h2>Thực thu theo ngày</h2><ResourceState {...series} />
        {!series.loading && !series.error && <div className="revenue-bars" aria-label="Biểu đồ thực thu theo ngày">
          {series.data?.records.map(row => <div key={row.date} className="revenue-bar" title={`${row.date}: ${money(row.revenue)}`}>
            <span className="revenue-bar-fill" style={{ height: `${Math.max(row.revenue > 0 ? 3 : 0, row.revenue / max * 100)}%` }} /><small>{row.date.slice(8)}</small></div>)}
        </div>}
        {!series.loading && !series.error && <details><summary>Xem số liệu chi tiết</summary><div className="business-chart-data"><table><thead><tr><th>Ngày</th><th>Thực thu</th></tr></thead><tbody>
          {series.data?.records.map(row => <tr key={row.date}><td>{row.date.split('-').reverse().join('/')}</td><td>{money(row.revenue)}</td></tr>)}
        </tbody></table></div></details>}
      </Card>
    </>}
  </section>;
}

function DailySchedule({ role, employeePortal }: { role: string; employeePortal?: boolean }) {
  const staff = role === 'staff';
  const resource = useResource<{ appointments: Appointment[] }>(`/api/dashboard/appointments/${staff ? 'my-schedule-today' : 'today'}`);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const rows = resource.data?.appointments || [];
  const pending = rows.filter(r => r.trangthai === 'pending').length;
  const progress = rows.filter(r => r.trangthai === 'in_progress').length;
  const visible = rows.filter(r => (!status || r.trangthai === status) && `${r.khachhang_hoten} ${r.dichvu_ten} ${r.nhanvien_hoten || ''}`.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')));
  const href = staff ? employeePortal ? '/employee/appointments' : '/admin/appointments' : '/admin/appointments';
  const badge = (row: Appointment) => <Tag color={color[row.trangthai]}>{row.trangthai_vi}</Tag>;
  return <section><div className="section-toolbar"><h2>{staff ? 'Lịch khách của tôi hôm nay' : 'Lịch hẹn hôm nay'}</h2><Space wrap><Button onClick={resource.reload}>Làm mới</Button><Button href={href}>Xem tất cả lịch hẹn</Button></Space></div>
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && <>
      <div className="appointment-summary"><Card><Statistic title="Tổng lịch hôm nay" value={rows.length} /></Card><Card><Statistic title="Chờ xác nhận" value={pending} /></Card><Card><Statistic title="Đang phục vụ" value={progress} /></Card></div>
      <Card className="business-revenue"><div className="business-filters"><Input aria-label="Tìm lịch hẹn" placeholder="Tìm khách, dịch vụ…" allowClear value={search} onChange={e => setSearch(e.target.value)} />
        <Select aria-label="Trạng thái lịch hẹn" value={status} onChange={setStatus} options={[{ value: '', label: 'Tất cả trạng thái' }, { value: 'pending', label: 'Chờ xác nhận' }, { value: 'confirmed', label: 'Đã xác nhận' }, { value: 'in_progress', label: 'Đang phục vụ' }, { value: 'completed', label: 'Hoàn thành' }, { value: 'cancelled', label: 'Đã hủy' }]} />
        <Button onClick={() => { setSearch(''); setStatus(''); }}>Xóa bộ lọc</Button></div>
        {visible.length ? <><div className="desktop-table"><Table rowKey="malh" dataSource={visible} pagination={{ pageSize: 10, showSizeChanger: false }} columns={[
          { title: 'Giờ', dataIndex: 'ngaygio', render: time, width: 80 }, { title: 'Khách hàng', dataIndex: 'khachhang_hoten' }, { title: 'Dịch vụ', dataIndex: 'dichvu_ten' },
          ...(!staff ? [{ title: 'Nhân viên', dataIndex: 'nhanvien_hoten' }] : []), { title: 'Trạng thái', render: (_: unknown, row: Appointment) => badge(row) },
          { title: 'Thao tác', render: () => <Button href={href}>Mở lịch hẹn</Button> }]} /></div>
          <div className="mobile-cards">{visible.map(row => <article className="business-appointment" key={row.malh}><div className="card-head"><strong>{time(row.ngaygio)} · #{row.malh}</strong>{badge(row)}</div><h3>{row.khachhang_hoten}</h3><p>{row.dichvu_ten}</p>{!staff && <p className="muted">{row.nhanvien_hoten || 'Chưa phân công'}</p>}<Button href={href}>Mở lịch hẹn</Button></article>)}</div>
        </> : <Empty description={rows.length ? 'Không có lịch khớp bộ lọc' : 'Hôm nay chưa có lịch hẹn'} />}
      </Card></>}
  </section>;
}

export default function BusinessDashboard({ me }: { me: Me }) {
  const finance = ['admin', 'manager'].includes(me.user.role);
  const frontDesk = me.user.role === 'letan';
  const internal = finance || frontDesk;
  const employeePortal = me.features.employee_portal;
  return <><div className="page-heading"><span className="eyebrow">{today().split('-').reverse().join('/')}</span><h1>Tổng quan công việc</h1><p>{finance ? 'Lịch phục vụ và kết quả kinh doanh của spa.' : frontDesk ? 'Theo dõi lịch khách để chuẩn bị đón tiếp.' : 'Các lịch khách đã được phân công cho bạn.'}</p></div>
      <Space wrap className="business-shortcuts"><Button type="primary" href={internal ? '/admin/appointments' : employeePortal ? '/employee/appointments' : '/admin/appointments'}>{internal ? 'Quản lý lịch hẹn' : 'Lịch hẹn của tôi'}</Button>
        {employeePortal && <Button href="/employee/attendance">Chấm công hôm nay</Button>}{finance && employeePortal && <Button href="/admin/operations/attendance">Duyệt công</Button>}
        {internal && <Button href="/admin/package-sales">Bán gói tại quầy</Button>}</Space>
      <DailySchedule role={me.user.role} employeePortal={employeePortal} />{finance && (me.features.admin_care ? <DashboardDetails /> : <Finance />)}
      {!me.features.admin_care && <div className="secondary-actions">{finance && <a href="/admin/dashboard?ui=legacy#ai-summary-panel">Phân tích AI và báo cáo chi tiết</a>}<a href="/admin/dashboard?ui=legacy">Mở giao diện tổng quan trước đây</a></div>}
    </>;
}
