import { useRef, useState } from 'react';
import { Alert, App, Button, Card, Collapse, Descriptions, Drawer, Form, Input, Modal, Select, Space, Statistic, Table } from 'antd';
import { ApiError, post } from './api';
import { logout } from './session';
import { dateLabel, getPosition, nextShift, punchAction, punchBody, time, vnd } from './attendance';
import { inputUtc, localInput, Pager, Reason, ResourceState, Status, useResource } from './components';
import type { Adjustment, Commission, IncomeSummary, LegacySalary, Me, Page, PayrollLine, PunchBody, Session, Shift } from './types';

function Correction({ shifts, onDone }: { shifts: Shift[]; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();
  return <>
    <Button onClick={() => setOpen(true)} disabled={!shifts.length}>Yêu cầu chỉnh công</Button>
    <Drawer title="Đề nghị chỉnh công" open={open} onClose={() => setOpen(false)} width={440}>
      <p>Quên chấm, GPS chưa chính xác hoặc mất mạng: gửi giờ thực tế và lý do để quản lý đối chiếu.</p>
      <Form form={form} layout="vertical" onFinish={async values => {
        setBusy(true);
        try { await post('/api/me/attendance-adjustments', { shift_assignment_id: values.shift,
          proposed_start: inputUtc(values.start), proposed_end: inputUtc(values.end), reason: values.reason });
          message.success('Đã gửi yêu cầu, chờ quản lý xử lý'); setOpen(false); form.resetFields(); onDone();
        } catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
      }}>
        <Form.Item name="shift" label="Ca cần chỉnh" rules={[{ required: true }]}><Select
          options={shifts.map(shift => ({ value: shift.shift_id, label: `${dateLabel(shift.start_at)} · ${time(shift.start_at)}–${time(shift.end_at)} · ${shift.branch_name}` }))}
          onChange={id => { const shift = shifts.find(s => s.shift_id === id)!;
            form.setFieldsValue({ start: localInput(shift.attendance?.actual_start || shift.start_at), end: localInput(shift.attendance?.actual_end || shift.end_at) }); }} /></Form.Item>
        <Form.Item name="start" label="Giờ vào thực tế (giờ Việt Nam)" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
        <Form.Item name="end" label="Giờ ra thực tế (giờ Việt Nam)" rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
        <Reason /><Button type="primary" htmlType="submit" loading={busy}>Gửi quản lý</Button>
      </Form>
    </Drawer>
  </>;
}

function ShiftCard({ shift, reload }: { shift: Shift; reload: () => void }) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [retry, setRetry] = useState(false);
  const pending = useRef<{ action: string; body: PunchBody } | null>(null);
  const action = punchAction(shift);
  const { message } = App.useApp();
  const session = shift.attendance;
  async function punch() {
    if (!action && !pending.current) return;
    setBusy(true); setFeedback('Đang lấy vị trí…');
    try {
      if (!pending.current) {
        const position = await getPosition();
        setFeedback(`Sai số GPS khoảng ${Math.round(position.coords.accuracy)} m. Đang gửi…`);
        pending.current = { action: action!, body: punchBody(shift, position) };
      }
      const result = await post<{ message: string }>(`/api/attendance/${pending.current.action}`, pending.current.body);
      pending.current = null; setRetry(false); setFeedback(result.message); message.success(result.message); reload();
    } catch (error) {
      setFeedback((error as Error).message);
      if (error instanceof ApiError && (error.status === 0 || error.status >= 500 || error.code === 'concurrent_change')) {
        setRetry(true);
      } else { pending.current = null; setRetry(false); }
    } finally { setBusy(false); }
  }
  return <Card className="shift-card">
    <div className="card-head"><span className="eyebrow">{dateLabel(shift.start_at)}</span>{session && <Status value={session.approval_status} />}</div>
    <h2>{time(shift.start_at)} <span className="muted">–</span> {time(shift.end_at)}</h2>
    <p className="branch-name">{shift.branch_name}</p>
    {session && <div className="recorded"><span>Chấm vào <b>{time(session.actual_start)}</b></span><span>Chấm ra <b>{time(session.actual_end)}</b></span></div>}
    {!shift.gps_enabled && <Alert type="info" message="Chấm công GPS đang tạm tắt. Bạn có thể gửi yêu cầu cho quản lý." showIcon />}
    {shift.gps_enabled && !session?.actual_end && <>
      <Button className="punch-button" type="primary" block loading={busy} disabled={!action && !retry} onClick={punch}>
        {retry ? 'Gửi lại yêu cầu chấm công' : action === 'check-out' ? 'Chấm ra · Kết thúc ca' : 'Chấm vào · Bắt đầu ca'}
      </Button>
      {!action && !retry && <p className="muted">Chấm vào từ {time(shift.checkin_opens_at)}; chấm ra đến {time(shift.checkout_closes_at)}.</p>}
    </>}
    {feedback && <p role="status" className="gps-feedback">{feedback}</p>}
    {!session?.actual_end && <PunchRequest shift={shift} reload={reload} />}
    {shift.gps_enabled && <p className="privacy-note">Chỉ lấy vị trí khi bạn nhấn chấm công. Bán kính {shift.radius_m} m; sai số tối đa {shift.max_accuracy_m} m. Tọa độ lưu tối đa {shift.retention_days} ngày để đối chiếu công.</p>}
  </Card>;
}

function PunchRequest({ shift, reload }: { shift: Shift; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const kind = shift.attendance ? 'check-out' : 'check-in';
  return <><Button className="punch-request section-title" block onClick={() => {
    form.resetFields(); form.setFieldsValue({ at: localInput(new Date().toISOString()) }); setOpen(true);
  }}>Không chấm được? Gửi yêu cầu quản lý</Button>
    <Modal title={kind === 'check-in' ? 'Yêu cầu chấm vào' : 'Yêu cầu chấm ra'} open={open} footer={null} onCancel={() => setOpen(false)}>
      <p>Ca {time(shift.start_at)}–{time(shift.end_at)}. Giờ công chỉ được ghi nhận sau khi quản lý duyệt.</p>
      <Form form={form} layout="vertical" onFinish={async values => {
        setBusy(true);
        try { await post('/api/me/attendance-adjustments', { shift_assignment_id: shift.shift_id,
          request_kind: kind, [kind === 'check-in' ? 'proposed_start' : 'proposed_end']: inputUtc(values.at), reason: values.reason });
          message.success('Đã gửi quản lý duyệt'); setOpen(false); reload();
        } catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
      }}><Form.Item name="at" label={kind === 'check-in' ? 'Giờ vào thực tế' : 'Giờ ra thực tế'} rules={[{ required: true }]}><Input type="datetime-local" /></Form.Item>
        <Reason /><Button type="primary" htmlType="submit" loading={busy}>Gửi yêu cầu</Button>
      </Form>
    </Modal>
  </>;
}

/** The check-in button lives on a shift card; without a shift today, say so and show what to do. */
function NoShiftToday({ shifts }: { shifts?: Shift[] }) {
  const next = shifts ? nextShift(shifts) : null;
  return <Card className="no-shift" data-testid="no-shift-today">
    <h2>Hôm nay bạn chưa có ca làm</h2>
    <p>Nút <b>Chấm vào / Chấm ra</b> chỉ hiện khi bạn có ca trong ngày. Nếu hôm nay bạn đi làm, hãy đăng ký ca hoặc báo quản lý xếp ca, rồi tải lại trang này.</p>
    {next && <p>Ca gần nhất: <b>{dateLabel(next.start_at)}, {time(next.start_at)}–{time(next.end_at)}</b>{next.branch_name ? ` · ${next.branch_name}` : ''}</p>}
    <Space wrap><Button type="primary" href="/admin/register-shift">Đăng ký ca</Button><Button href="/employee/schedule">Xem lịch ca</Button></Space>
  </Card>;
}

export function Today() {
  const resource = useResource<{ items: Shift[] }>('/api/me/shifts/today');
  const schedule = useResource<{ items: Shift[] }>('/api/me/shifts');
  return <>
    <div className="page-heading"><div><h1>Chấm công hôm nay</h1><p>Chọn ca đang mở để chấm vào hoặc chấm ra tại Bin Spa.</p></div></div>
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && !resource.data?.items.length && <NoShiftToday shifts={schedule.data?.items} />}
    {!resource.loading && !resource.error && <div className="shift-grid">{resource.data?.items.map(shift => <ShiftCard key={shift.shift_id} shift={shift} reload={resource.reload} />)}</div>}
    <div className="secondary-actions"><Correction shifts={schedule.data?.items || []} onDone={resource.reload} /><a href="/employee/history">Lịch sử công và yêu cầu đã gửi</a></div>
  </>;
}

export function Schedule() {
  const resource = useResource<{ items: Shift[] }>('/api/me/shifts');
  return <><div className="page-heading"><h1>Lịch ca</h1><p>Xem các ca trong tuần trước và 30 ngày tới.</p></div>
    <ResourceState {...resource} empty={!resource.data?.items.length} />
    {!resource.loading && !resource.error && <div className="list-grid">{resource.data?.items.map(shift => <Card key={shift.shift_id}>
      <div className="card-head"><b>{dateLabel(shift.start_at)}</b>{shift.attendance && <Status value={shift.attendance.approval_status} />}</div>
      <h2>{time(shift.start_at)}–{time(shift.end_at)}</h2><p>{shift.branch_name}</p>
    </Card>)}</div>}
    <Correction shifts={resource.data?.items || []} onDone={resource.reload} />
  </>;
}

export function History() {
  const [page, setPage] = useState(1);
  const resource = useResource<Page<Session>>(`/api/me/attendance?page=${page}`);
  const adjustments = useResource<Page<Adjustment>>('/api/me/attendance-adjustments?per_page=100');
  const events = useResource<Page<{ id: number; event_type: string; server_at: string; verdict: string; reason: string }>>('/api/me/attendance-events?per_page=20');
  const schedule = useResource<{ items: Shift[] }>('/api/me/shifts');
  return <><div className="page-heading"><h1>Lịch sử công</h1><p>Công được trả theo số phút quản lý xác nhận.</p></div>
    <ResourceState {...resource} empty={!resource.data?.items.length} />
    {!resource.loading && !resource.error && <div className="list-grid">{resource.data?.items.map(session => <Card key={session.id}>
      <div className="card-head"><b>{dateLabel(session.planned_start)}</b><Status value={session.approval_status} /></div>
      <p>{time(session.actual_start)}–{time(session.actual_end)} · Thực tế {session.worked_minutes} phút</p>
      <p>Được duyệt: {session.paid_minutes} phút · Tăng ca: {session.overtime_minutes} phút</p>
      {(session.late_minutes > 0 || session.early_leave_minutes > 0) && <p className="muted">Vào muộn {session.late_minutes} phút · Ra sớm {session.early_leave_minutes} phút. Quản lý sẽ đối chiếu.</p>}
    </Card>)}</div>}<Pager data={resource.data} setPage={setPage} />
    <Correction shifts={schedule.data?.items || []} onDone={() => { resource.reload(); adjustments.reload(); }} />
    <h2 className="section-title">Yêu cầu đã gửi</h2><ResourceState {...adjustments} empty={!adjustments.data?.items.length} />
    {adjustments.data?.items.map(item => <Card key={item.id} className="small-card"><div className="card-head"><b>{dateLabel(item.proposed_start)}</b><Status value={item.status} /></div>
      <p>{item.request_kind === 'check-in' ? 'Yêu cầu chấm vào' : item.request_kind === 'check-out' ? 'Yêu cầu chấm ra' : 'Chỉnh công'} · {time(item.proposed_start)}{item.proposed_end && `–${time(item.proposed_end)}`} · {item.reason}</p>{item.decision_reason && <p>Quản lý: {item.decision_reason}</p>}</Card>)}
    <h2 className="section-title">20 lần chấm công gần nhất</h2><ResourceState {...events} empty={!events.data?.items.length} />
    {events.data?.items.map(event => <div className="ledger-row" key={event.id}><div><b>{dateLabel(event.server_at)} · {time(event.server_at)}</b>
      <p>{event.event_type === 'check-in' ? 'Chấm vào' : 'Chấm ra'} · {event.reason}</p></div><span>{event.verdict === 'accepted' ? 'Đã ghi' : 'Chưa ghi công'}</span></div>)}
  </>;
}

export function Income() {
  const [page, setPage] = useState(1);
  const [commissionPage, setCommissionPage] = useState(1);
  const resource = useResource<Page<PayrollLine>>(`/api/me/payslips?page=${page}`);
  const commissions = useResource<Page<Commission>>(`/api/me/commissions?page=${commissionPage}`);
  const summary = useResource<IncomeSummary>('/api/me/income-summary');
  const legacy = useResource<{ salaries: LegacySalary[]; cutover_date: string | null; gps_payroll_enabled: boolean }>('/api/profile/my-salary');
  const [selected, setSelected] = useState<PayrollLine>();
  return <><div className="page-heading"><h1>Thu nhập</h1><p>Giờ thực tế, công chờ duyệt và công được trả được hiển thị riêng.</p></div>
    <ResourceState {...summary} />
    {summary.data && <><p>{dateLabel(summary.data.from_date + 'T00:00:00+07:00')} → {dateLabel(summary.data.to_date + 'T00:00:00+07:00')}</p>
      <div className="kpi-grid"><Card><Statistic title="Giờ thực tế đã chấm ra" value={summary.data.worked_minutes / 60} precision={2} suffix="giờ" /></Card>
        <Card><Statistic title="Giờ đang chờ duyệt" value={summary.data.pending_minutes / 60} precision={2} suffix="giờ" /></Card>
        <Card><Statistic title="Giờ công được trả đã duyệt" value={summary.data.approved_minutes / 60} precision={2} suffix="giờ" /></Card>
        <Card><Statistic title="Lương công tạm tính chờ duyệt" value={vnd(summary.data.pending_estimate)} /></Card></div>
      <p>Lương công đã duyệt: <b>{vnd(summary.data.approved_earnings)}</b> · Tăng ca đã duyệt: {(summary.data.approved_overtime_minutes / 60).toFixed(2)} giờ.</p>
      {!!summary.data.pending_sessions && <Alert type="info" showIcon className="section-title" message={`${summary.data.pending_sessions} phiên đã chấm ra đang chờ quản lý duyệt. Lương tạm tính dựa trên giờ thực tế và đơn giá đã lưu, chưa gồm hoa hồng/phụ cấp/khấu trừ và chưa phải phiếu lương chốt.`} />}
      {!!summary.data.open_sessions && <Alert type="warning" className="section-title" message={`${summary.data.open_sessions} ca chưa chấm ra nên chưa có đủ giờ thực tế.`} />}
    </>}
    <h2 className="section-title">Phiếu lương đã chốt</h2><ResourceState {...resource} />
    {!resource.loading && !resource.error && !resource.data?.items.length && <Alert type="info" message="Phiếu lương sẽ hiển thị sau khi quản lý duyệt công, khóa kỳ công, tạo bảng lương và chốt phiếu." />}
    <div className="list-grid">{resource.data?.items.map(line => <Card key={line.id}>
      <div className="card-head"><b>{line.from_date} → {line.to_date}</b><Status value={line.status} /></div>
      <h2>{vnd(line.net)}</h2><p className="muted">Trước thuế và bảo hiểm</p><Button onClick={() => setSelected(line)}>Xem phiếu lương</Button>
    </Card>)}</div><Pager data={resource.data} setPage={setPage} />
    <h2 className="section-title">Hoa hồng dịch vụ</h2><ResourceState {...commissions} empty={!commissions.data?.items.length} />
    {commissions.data?.items.map(item => <div className="ledger-row" key={item.id}><div><b>{item.service_name}</b><p>{dateLabel(item.earned_at + '+07:00')} · {item.source_label} · {item.status === 'active' ? 'Đủ điều kiện' : 'Đã hủy hiệu lực'}</p></div><strong>{vnd(item.amount)}</strong></div>)}
    <Pager data={commissions.data} setPage={setCommissionPage} />
    <Collapse className="section-title" items={[{ key: 'legacy', label: 'Lịch sử lương trước khi chuyển sang GPS', children: <>
      {legacy.data?.gps_payroll_enabled && legacy.data.cutover_date && <p>Từ {dateLabel(legacy.data.cutover_date + 'T00:00:00+07:00')}, lương hiện tại dùng công GPS đã duyệt. Các tháng dưới đây là lịch sử hệ thống cũ và không cộng vào lương GPS.</p>}
      <ResourceState {...legacy} empty={!legacy.data?.salaries.length} />
      <div className="mobile-cards">{legacy.data?.salaries.map(salary => <Card key={salary.maluong} className="small-card">
        <h3>{salary.thang}/{salary.nam}</h3><Descriptions column={1} items={
          (['luongcoban', 'hoahong', 'thuong', 'khautru', 'tongluong'] as const).map((key, i) => ({ key,
            label: ['Lương ca cũ', 'Hoa hồng', 'Thưởng', 'Khấu trừ', 'Tổng lịch sử'][i], children: vnd(salary[key]) }))} />
      </Card>)}</div>
      <Table<LegacySalary> className="desktop-table" rowKey="maluong" dataSource={legacy.data?.salaries} pagination={false} scroll={{ x: 700 }} columns={[
        { title: 'Tháng / năm', render: (_, row) => `${row.thang}/${row.nam}` },
        ...(['luongcoban', 'hoahong', 'thuong', 'khautru', 'tongluong'] as const).map((key, i) => ({ title: ['Lương ca cũ', 'Hoa hồng', 'Thưởng', 'Khấu trừ', 'Tổng lịch sử'][i],
          render: (_: unknown, row: LegacySalary) => vnd(row[key]) })),
      ]} />
    </> }]} />
    <Drawer title="Phiếu lương" open={!!selected} onClose={() => setSelected(undefined)} width={520}>
      {selected && <div className="payslip"><h2>{selected.source_snapshot.staff_name}</h2><p>{selected.from_date} → {selected.to_date}</p>
        <Descriptions column={1} bordered items={[
          { key: 'minutes', label: 'Giờ công', children: `${(selected.paid_minutes / 60).toFixed(2)} giờ` },
          ...(['base', 'overtime', 'commission', 'allowance', 'deduction', 'net'] as const).map((key, index) => ({ key,
            label: ['Lương công', 'Tăng ca', 'Hoa hồng', 'Phụ cấp', 'Khấu trừ', 'Tổng trước thuế/bảo hiểm'][index], children: vnd(selected[key]) }))
        ]} />
        <Collapse className="section-title" items={[{ key: 'sources', label: 'Chi tiết công và hoa hồng được chốt', children: <>
          {selected.source_snapshot.attendance.map(s => <p key={s.id}>{s.work_date}: {s.paid_minutes} phút công, {s.overtime_minutes} phút tăng ca</p>)}
          {selected.source_snapshot.commissions.map(c => <p key={c.id}>{c.service_name}: {vnd(c.amount)}</p>)}
          {selected.source_snapshot.commission_deltas.map((c, i) => <p key={i}>Điều chỉnh hoa hồng #{c.commission_id}: {vnd(c.amount)}</p>)}
        </> }]} />
        <Button className="no-print" onClick={() => window.print()}>In / lưu PDF</Button>
      </div>}
    </Drawer>
  </>;
}

export function Account({ me }: { me: Me }) {
  return <><div className="page-heading"><h1>Tài khoản</h1></div><Card><h2>{me.user.name}</h2>
    <p>Cơ sở: {me.branches.map(b => b.name).join(', ') || 'Chưa được phân cơ sở'}</p>
    <p>GPS chỉ được lấy khi nhấn chấm vào/ra. Khi từ chối quyền vị trí, bật lại trong cài đặt trình duyệt hoặc gửi yêu cầu chỉnh công cho quản lý.</p>
    <Space wrap><Button href="/admin/profile">Hồ sơ và mật khẩu</Button>{me.features.staff_security && <Button href="/admin/security">Bảo mật tài khoản</Button>}<Button onClick={() => { void logout(); }}>Đăng xuất</Button></Space></Card></>;
}
