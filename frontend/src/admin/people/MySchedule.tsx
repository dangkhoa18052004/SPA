import { useState } from 'react';
import { Alert, App, Button, Card, Empty, Modal, Rate, Space, Statistic, Tag } from 'antd';
import { post } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { spaToday } from '../booking/model';
import { addDays, dmy, overnight, registrationState, shiftStarted, weekDays, weekdayLabel, weekLabel, weekStart } from './model';
import type { MyShift, WeekShift } from './model';
import '../booking/booking.css';
import './people.css';

/** Week navigation kept in the URL (?week=YYYY-MM-DD, a Monday) so Back and reload keep the week. */
function useWeek() {
  const [query, setQuery] = useQuery();
  const today = spaToday();
  const monday = weekStart(query.get('week') || today);
  const nav = <Space wrap className="week-nav"><Button onClick={() => setQuery({ week: addDays(monday, -7) })} aria-label="Tuần trước">‹</Button>
    <strong>{weekLabel(monday)}</strong><Button onClick={() => setQuery({ week: addDays(monday, 7) })} aria-label="Tuần sau">›</Button>
    {monday !== weekStart(today) && <Button onClick={() => setQuery({ week: null })}>Tuần này</Button>}</Space>;
  return { monday, days: weekDays(monday), today, nav };
}
const time = (start: string, end: string) => `${start}–${end}${overnight(start, end) ? ' (hôm sau)' : ''}`;

export function MySchedule({ me }: { me: Me }) {
  const { monday, days, today, nav } = useWeek();
  const resource = useResource<{ schedule: MyShift[] }>(`/api/admin/my-schedule-list?start_date=${monday}&end_date=${days[6]}`);
  const reviews = useResource<{ stats: { total_reviews: number; average_rating: number }; reviews: { madg: number; rating: number; comment: string; customer_name: string; created_at: string }[] }>(`/api/reviews/staff/${me.user.id}`);
  const stats = reviews.data?.stats;
  const [colleagues, setColleagues] = useState<MyShift | null>(null);
  const items = resource.data?.schedule || [];
  const approved = items.filter(i => i.trangthai_code === 'approved');
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Lịch làm của tôi</h1><p>Ca đã được phân và ca đang chờ duyệt, theo tuần.</p></div>
      <Space wrap><Button href="/admin/register-shift" type="primary">Đăng ký ca</Button>{me.features.employee_portal && me.features.attendance && <Button href="/employee/attendance">Chấm công</Button>}</Space>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Ca đã phân trong tuần" value={resource.data ? approved.length : '…'} /></Card>
      <Card><Statistic title="Đang chờ duyệt" value={resource.data ? items.length - approved.length : '…'} /></Card>
      <Card><Statistic title="Đánh giá của khách" value={stats?.total_reviews ? stats.average_rating : '—'} suffix={stats?.total_reviews ? <small className="muted">/5 · {stats.total_reviews} lượt</small> : null} /></Card>
    </div>
    <Card className="section-title">{nav}
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && <div className="week-grid section-title">{days.map(day => { const list = items.filter(i => i.ngay === day);
        return <section key={day} className={`week-day${day === today ? ' is-today' : ''}`} aria-label={`${weekdayLabel(day)} ${dmy(day)}`}>
          <h3>{weekdayLabel(day)} <span className="muted">{dmy(day).slice(0, 5)}</span></h3>
          {!list.length ? <p className="muted">Nghỉ</p> : list.map(i => <div key={`${i.ten_ca}-${i.trangthai_code}`} className={`week-shift ${i.trangthai_code}`}>
            <strong>{time(i.giobatdau, i.gioketthuc)}</strong>
            <Tag color={i.trangthai_code === 'approved' ? 'green' : 'gold'}>{i.trangthai_text}</Tag>
            {i.colleagues.length > 0 && <Button type="link" size="small" onClick={() => setColleagues(i)}>{i.colleagues.length} đồng nghiệp</Button>}
          </div>)}
        </section>; })}</div>}
      {!resource.loading && !resource.error && !items.length && <Empty className="section-title" description="Tuần này bạn chưa có ca. Đăng ký ca hoặc liên hệ quản lý." />}
    </Card>
    <Modal open={!!colleagues} title={colleagues ? `Cùng ca ${colleagues.ten_ca} · ${dmy(colleagues.ngay)}` : ''} onCancel={() => setColleagues(null)} footer={null}>
      <ul className="history-list">{colleagues?.colleagues.map((c, n) => <li key={n}><strong>{c.hoten}</strong><span className="muted">{c.chucvu}</span></li>)}</ul>
    </Modal>
    {stats?.total_reviews ? <Card className="section-title" title="Khách nhận xét gần đây"><Space><Rate disabled allowHalf value={stats.average_rating} /><span>{stats.average_rating} từ {stats.total_reviews} đánh giá</span></Space>
      <ul className="history-list section-title">{reviews.data!.reviews.slice(0, 5).map(r => <li key={r.madg}><span><Rate disabled value={r.rating} style={{ fontSize: 13 }} /> <strong>{r.customer_name}</strong>{r.comment ? ` · ${r.comment}` : ''}</span>
        <span className="muted">{dmy(r.created_at)}</span></li>)}</ul></Card> : null}
  </>;
}

export function RegisterShift({ me }: { me: Me }) {
  const { message } = App.useApp();
  const { monday, days, today, nav } = useWeek();
  const shifts = useResource<Record<string, Omit<WeekShift, 'ngay'>[]>>(`/api/admin/all-schedules?start_date=${monday}&end_date=${days[6]}`);
  const mine = useResource<{ schedule: MyShift[] }>(`/api/admin/my-schedule-list?start_date=${monday}&end_date=${days[6]}`);
  const [busy, setBusy] = useState<number | null>(null);
  const list: WeekShift[] = Object.entries(shifts.data || {}).flatMap(([ngay, rows]) => rows.map(r => ({ ...r, ngay })))
    .sort((a, b) => a.ngay.localeCompare(b.ngay) || a.start_time.localeCompare(b.start_time));
  async function register(s: WeekShift) {
    setBusy(s.maca);
    try { const r = await post<{ msg: string }>('/api/admin/shifts/register', { maca: s.maca }); message.success(`${r.msg} Quản lý sẽ duyệt.`); mine.reload(); shifts.reload(); }
    catch (e) { message.error((e as Error).message); } finally { setBusy(null); }
  }
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">NHÂN SỰ</span><h1>Đăng ký ca</h1><p>Chọn ca muốn làm; quản lý duyệt thì ca xuất hiện trong lịch và chấm công được.</p></div>
      <Button href="/admin/my-schedule">Lịch làm của tôi</Button>
    </div>
    <Card>{nav}
      <ResourceState {...shifts} />
      {mine.error && <Alert className="section-title" type="warning" showIcon message={`Chưa tải được ca bạn đã đăng ký: ${mine.error}`} />}
      {!shifts.loading && !shifts.error && (!list.length ? <Empty className="section-title" description="Tuần này chưa có ca nào. Chọn tuần khác hoặc liên hệ quản lý." /> :
        <div className="week-grid section-title">{days.map(day => { const rows = list.filter(s => s.ngay === day);
          return <section key={day} className={`week-day${day === today ? ' is-today' : ''}`} aria-label={`${weekdayLabel(day)} ${dmy(day)}`}>
            <h3>{weekdayLabel(day)} <span className="muted">{dmy(day).slice(0, 5)}</span></h3>
            {!rows.length ? <p className="muted">Không có ca</p> : rows.map(s => { const state = registrationState(s.maca, mine.data?.schedule || [], s.assigned_staff, me.user.id);
              const past = shiftStarted(s.ngay, s.start_time);
              return <div key={s.maca} className={`week-shift ${state === 'assigned' ? 'approved' : state}`} data-shift={s.maca}>
                <strong>{time(s.start_time, s.end_time)}</strong><span className="muted">{s.assigned_staff.length} người</span>
                {state === 'assigned' ? <Tag color="green">Đã được phân</Tag> : state === 'pending' ? <Tag color="gold">Chờ duyệt</Tag>
                  : past ? <Tag>Đã qua</Tag> : <Button size="small" type="primary" loading={busy === s.maca} onClick={() => register(s)}>Đăng ký</Button>}
              </div>; })}
          </section>; })}</div>)}
    </Card>
  </>;
}
