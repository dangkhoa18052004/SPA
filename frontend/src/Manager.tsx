import { useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Form, Input, InputNumber, Modal, Select, Space, Statistic, Switch, Table } from 'antd';
import { api, downloadCsv, post } from './api';
import { dateLabel, time, vnd } from './attendance';
import { Pager, Reason, ResourceState, Status, useResource } from './components';
import type { Adjustment, Branch, Me, Page, PayrollLine, Period, Policy, Session } from './types';

const title = (heading: string, description: string) => <div className="page-heading"><h1>{heading}</h1><p>{description}</p></div>;

export function Dashboard() {
  const r = useResource<{ pending: number; open: number; adjustments: number; draft_payroll: number }>('/api/admin/operations/summary');
  const labels: Record<string, string> = { pending: 'Công chờ duyệt', open: 'Ca chưa chấm ra', adjustments: 'Yêu cầu chỉnh công', draft_payroll: 'Kỳ lương bản nháp' };
  return <>{title('Tổng quan nhân sự', 'Những việc cần xử lý trong các cơ sở bạn quản lý.')}<ResourceState {...r} />
    <div className="kpi-grid">{r.data && Object.entries(labels).map(([key, label]) => <Card key={key}>
      <Statistic title={label} value={r.data![key as keyof typeof r.data]} /></Card>)}</div>
    <div className="list-grid section-title"><Card><h2>Duyệt công</h2><p>Đối chiếu giờ thực tế, xác nhận phút công và tăng ca.</p><Button href="/admin/operations/attendance">Mở bảng công</Button></Card>
      <Card><h2>Chốt kỳ lương</h2><p>Khóa công, tạo bản nháp và chuyển người khác kiểm tra.</p><Button href="/admin/operations/payroll">Mở kỳ công và lương</Button></Card></div>
  </>;
}

export function ReviewAttendance() {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Session>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const [exceptionForm] = Form.useForm();
  const [missingDates, setMissingDates] = useState<{ from: string; to: string }>();
  const [missing, setMissing] = useState<{ staff_id: number; staff_name: string; shift_id: number; work_date: string }[]>([]);
  const [exception, setException] = useState<typeof missing[number]>();
  const { message } = App.useApp();
  const attendanceParams = new URLSearchParams(window.location.search);
  attendanceParams.set('page', String(page));
  const r = useResource<Page<Session>>(`/api/admin/attendance?${attendanceParams}`);
  function openReview(s: Session) {
    setSelected(s); form.resetFields(); form.setFieldsValue({ decision: 'approve',
      paid_minutes: s.approval_status === 'APPROVED' ? s.paid_minutes : Math.max(0, Math.round((Date.parse(s.planned_end) - Date.parse(s.planned_start)) / 60000) - s.break_minutes),
      break_minutes: s.break_minutes, overtime_minutes: s.overtime_minutes,
      day_kind: s.compensation?.day_kind || 'weekday', night_minutes: s.compensation?.night_minutes || 0,
      night_overtime_minutes: s.compensation?.night_overtime_minutes || 0, daytime_overtime: s.compensation?.daytime_overtime || false });
  }
  async function submit(values: Record<string, unknown>) {
    if (!selected) return;
    setBusy(true);
    try { await post(`/api/admin/attendance/${selected.id}/approve`, { ...values, version: selected.version });
      message.success('Đã ghi quyết định duyệt công'); setSelected(undefined); r.reload();
    } catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
  }
  return <>{title('Bảng công', 'GPS hỗ trợ đối chiếu. Mọi phút công được trả và tăng ca cần xác nhận.')}
    <Card className="small-card"><Form layout="inline" onFinish={async values => {
      try { const result = await api<{ items: typeof missing }>(`/api/admin/attendance/missing?from_date=${values.from}&to_date=${values.to}`);
        setMissingDates(values); setMissing(result.items);
      } catch (error) { message.error((error as Error).message); }
    }}><Form.Item name="from" label="Ca thiếu công từ" rules={[{ required: true }]}><Input type="date" /></Form.Item>
      <Form.Item name="to" label="Đến" rules={[{ required: true }]}><Input type="date" /></Form.Item><Button htmlType="submit">Tìm ca thiếu công</Button></Form>
      {missingDates && <p className="muted">{missing.length} ca chưa có phiên công trong khoảng đã chọn.</p>}
      {missing.map(item => <div className="ledger-row" key={`${item.staff_id}-${item.shift_id}`}><span>{item.staff_name} · {item.work_date} · Ca #{item.shift_id}</span>
        <Button onClick={() => { setException(item); exceptionForm.resetFields(); }}>Xử lý ngoại lệ</Button></div>)}
    </Card>
    <ResourceState {...r} empty={!r.data?.items.length} />
    {!r.loading && !r.error && <><div className="mobile-cards">{r.data?.items.map(s => <Card key={s.id} className="small-card">
      <div className="card-head"><b>{s.staff_name}</b><Status value={s.approval_status} /></div><p>{s.work_date} · {time(s.actual_start)}–{time(s.actual_end)}</p>
      <p>Thực tế {s.worked_minutes} phút · Được duyệt {s.paid_minutes} phút</p>
      <Button className="mobile-review-button" disabled={['OPEN', 'LOCKED'].includes(s.approval_status)} onClick={() => openReview(s)}>Duyệt công</Button>
    </Card>)}</div><Table<Session> className="desktop-table" rowKey="id" pagination={false} dataSource={r.data?.items}
      scroll={{ x: 740 }} columns={[
        { title: 'Nhân viên', dataIndex: 'staff_name' }, { title: 'Ngày ca', dataIndex: 'work_date' },
        { title: 'Vào / ra', render: (_, s) => `${time(s.actual_start)} / ${time(s.actual_end)}` },
        { title: 'Thực tế', render: (_, s) => `${s.worked_minutes} phút` },
        { title: 'Trạng thái', render: (_, s) => <Status value={s.approval_status} /> },
        { title: '', render: (_, s) => <Button disabled={['OPEN', 'LOCKED'].includes(s.approval_status)} onClick={() => openReview(s)}>Duyệt công</Button> }
      ]} /></>}<Pager data={r.data} setPage={setPage} />
    <Drawer title="Đối chiếu và duyệt công" open={!!selected} onClose={() => setSelected(undefined)} width={500}>
      {selected && <><h2>{selected.staff_name}</h2><p>{selected.work_date} · Ca {time(selected.planned_start)}–{time(selected.planned_end)}</p>
        <p>Thực tế {time(selected.actual_start)}–{time(selected.actual_end)} · {selected.worked_minutes} phút</p>
        <Alert type="info" showIcon message={`Vào muộn ${selected.late_minutes} phút; ra sớm ${selected.early_leave_minutes} phút. Không tự động khấu trừ lương.`} />
        <Form className="section-title" form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="decision" label="Quyết định"><Select options={[{ value: 'approve', label: 'Duyệt công' }, { value: 'reject', label: 'Không duyệt công' }]} /></Form.Item>
          <div className="form-grid"><Form.Item name="paid_minutes" label="Phút công thường được trả" rules={[{ required: true }]}><InputNumber min={0} max={1440} precision={0} /></Form.Item>
            <Form.Item name="break_minutes" label="Phút nghỉ không lương"><InputNumber min={0} max={480} precision={0} /></Form.Item>
            <Form.Item name="overtime_minutes" label="Phút tăng ca được duyệt"><InputNumber min={0} max={720} precision={0} /></Form.Item>
            <Form.Item name="night_minutes" label="Phút công thường ban đêm"><InputNumber min={0} max={1440} precision={0} /></Form.Item>
            <Form.Item name="night_overtime_minutes" label="Phút tăng ca ban đêm"><InputNumber min={0} max={720} precision={0} /></Form.Item>
          </div>
          <Form.Item name="day_kind" label="Loại ngày tăng ca"><Select options={[{ value: 'weekday', label: 'Ngày thường · 150%' },
            { value: 'rest_day', label: 'Ngày nghỉ hằng tuần · 200%' }, { value: 'holiday', label: 'Ngày lễ · 300%' }]} /></Form.Item>
          <Form.Item name="daytime_overtime" label="Có tăng ca ban ngày trong cùng ngày (kể cả ca khác)" valuePropName="checked"><Switch /></Form.Item>
          <p className="muted">Ban đêm là 22:00–06:00. Phút ban đêm là phần nằm trong công thường/tăng ca, không cộng thêm vào tổng phút. Kiểm tra ngày nghỉ/lễ theo lịch của nhân viên.</p>
          <Reason /><Button type="primary" htmlType="submit" loading={busy}>Lưu quyết định</Button>
        </Form></>}
    </Drawer>
    <Modal title={`Xử lý ca thiếu công · ${exception?.staff_name || ''}`} open={!!exception} onCancel={() => setException(undefined)} footer={null}>
      <p>Nhập giờ thực tế khi quên chấm/GPS lỗi hoặc xác nhận vắng mặt. Giờ nhập tay sẽ chuyển sang chờ duyệt công.</p>
      <Form form={exceptionForm} layout="vertical" initialValues={{ decision: 'absence' }} onFinish={async values => {
        setBusy(true);
        try { await post('/api/admin/attendance/exceptions', { staff_id: exception!.staff_id, shift_assignment_id: exception!.shift_id,
          ...values, actual_start: values.actual_start ? `${values.actual_start}:00+07:00` : undefined,
          actual_end: values.actual_end ? `${values.actual_end}:00+07:00` : undefined });
          setMissing(items => items.filter(i => !(i.staff_id === exception!.staff_id && i.shift_id === exception!.shift_id)));
          setException(undefined); r.reload(); message.success('Đã ghi ngoại lệ và nhật ký');
        } catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
      }}><Form.Item name="decision" label="Cách xử lý"><Select options={[{ value: 'absence', label: 'Xác nhận vắng mặt · không có công ca này' }, { value: 'manual', label: 'Nhập giờ thực tế · chờ duyệt công' }]} /></Form.Item>
        <Form.Item name="actual_start" label="Giờ vào thực tế (khi nhập tay)"><Input type="datetime-local" /></Form.Item>
        <Form.Item name="actual_end" label="Giờ ra thực tế (khi nhập tay)"><Input type="datetime-local" /></Form.Item>
        <Reason /><Button type="primary" htmlType="submit" loading={busy}>Ghi nhận ngoại lệ</Button></Form>
    </Modal>
  </>;
}

export function ReviewAdjustments() {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Adjustment>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const r = useResource<Page<Adjustment>>(`/api/admin/attendance-adjustments?page=${page}`);
  return <>{title('Yêu cầu chấm công', 'Duyệt yêu cầu chấm vào, chấm ra hoặc chỉnh giờ khi nhân viên không chấm được.')}
    <ResourceState {...r} empty={!r.data?.items.length} />
    <div className="list-grid">{r.data?.items.map(item => <Card key={item.id}><div className="card-head"><b>{item.staff_name}</b><Status value={item.status} /></div>
      <p>{item.request_kind === 'check-in' ? 'Chấm vào' : item.request_kind === 'check-out' ? 'Chấm ra' : 'Chỉnh công'} · {dateLabel(item.proposed_start)} · {time(item.proposed_start)}{item.proposed_end && `–${time(item.proposed_end)}`}</p><p>{item.reason}</p>
      <Button onClick={() => { setSelected(item); form.resetFields(); }}>Đối chiếu yêu cầu</Button></Card>)}</div><Pager data={r.data} setPage={setPage} />
    <Drawer title="Xử lý yêu cầu chấm công" open={!!selected} onClose={() => setSelected(undefined)} width={440}>
      {selected && <><h2>{selected.staff_name}</h2><p>{selected.reason}</p><Form form={form} layout="vertical" initialValues={{ decision: 'approve' }} onFinish={async values => {
        setBusy(true);
        try { await post(`/api/admin/attendance-adjustments/${selected.id}/decide`, values);
          message.success(values.decision === 'reject' ? 'Đã từ chối yêu cầu' : selected.request_kind === 'check-in' ? 'Đã ghi giờ vào; nhân viên có thể chấm ra' : 'Đã ghi giờ công, chờ duyệt công'); setSelected(undefined); r.reload();
        } catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
      }}><Form.Item name="decision" label="Quyết định"><Select options={[{ value: 'approve', label: 'Chấp nhận giờ đề nghị' }, { value: 'reject', label: 'Từ chối yêu cầu' }]} /></Form.Item>
        <Reason /><Button type="primary" htmlType="submit" loading={busy}>Lưu quyết định</Button></Form></>}
    </Drawer>
  </>;
}

export function Payroll({ me }: { me: Me }) {
  const [openCreate, setOpenCreate] = useState(false);
  const [selected, setSelected] = useState<Period & { lines: PayrollLine[]; warnings: { commission_id: number }[] }>();
  const [adjusting, setAdjusting] = useState<PayrollLine>();
  const [decision, setDecision] = useState<{ kind: string; period: Period }>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const [decisionForm] = Form.useForm();
  const [adjustForm] = Form.useForm();
  const { message } = App.useApp();
  const [periodPage, setPeriodPage] = useState(1);
  const [payrollPage, setPayrollPage] = useState(1);
  const periods = useResource<Page<Period>>(`/api/admin/attendance-periods?page=${periodPage}`);
  const payrolls = useResource<Page<Period>>(`/api/admin/payroll-periods?page=${payrollPage}`);
  async function execute(fn: () => Promise<void>) {
    setBusy(true); try { await fn(); periods.reload(); payrolls.reload(); }
    catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
  }
  async function view(periodId: number) { setSelected(await api(`/api/admin/payroll-periods/${periodId}`)); }
  return <>{title('Kỳ công và bảng lương', 'Khóa công → Tạo bản nháp → Người khác duyệt → Chốt phiếu lương.')}
    {!me.features.payroll && <Alert type="info" message="Bảng lương GPS chưa được kích hoạt. Bạn vẫn có thể tạo kỳ và duyệt công; cần quản trị viên thiết lập ngày chuyển trước khi tạo/chốt lương." showIcon />}
    <div className="section-toolbar"><h2>Kỳ công</h2><Button type="primary" onClick={() => { form.resetFields();
      const branches = me.branches.filter(b => me.managed_branch_ids.includes(b.id));
      if (branches.length === 1) form.setFieldsValue({ branch_id: branches[0].id }); setOpenCreate(true); }}>Tạo kỳ công</Button></div>
    <ResourceState {...periods} empty={!periods.data?.items.length} />
    <div className="list-grid">{periods.data?.items.map(period => <Card key={period.id}><div className="card-head"><b>{period.from_date} → {period.to_date}</b><Status value={period.status} /></div>
      <p>{me.branches.find(b => b.id === period.branch_id)?.name || `Cơ sở ${period.branch_id}`}</p>
      {period.readiness && period.status !== 'LOCKED' && <><p>Đã duyệt: {period.readiness.approved} · Chờ duyệt: {period.readiness.submitted} · Chưa chấm ra: {period.readiness.open}</p>
        {!!period.readiness.missing && <p>Còn {period.readiness.missing} ca thiếu công cần xử lý.</p>}
        {!!period.readiness.pending_requests && <p>Còn {period.readiness.pending_requests} yêu cầu chấm công chờ quyết định.</p>}
        {!period.readiness.ended && <p>Chỉ khóa được từ ngày sau ngày kết thúc kỳ.</p>}
        {period.readiness.requires_other_manager && <p>Kỳ có công của bạn, cần quản lý khác khóa.</p>}</>}
      <Space wrap>
        {period.status !== 'LOCKED' && <><Button href={`/admin/operations/attendance?from_date=${period.from_date}&to_date=${period.to_date}`}>Duyệt công trong kỳ</Button>
          {!!period.readiness?.pending_requests && <Button href="/admin/operations/adjustments">Xử lý yêu cầu</Button>}
          <Button disabled={period.readiness && !period.readiness.can_lock} loading={busy} onClick={() => { setDecision({ kind: 'attendance-lock', period }); decisionForm.resetFields(); }}>Khóa công</Button></>}
        {period.status === 'LOCKED' && <Button disabled={!me.features.payroll} loading={busy} onClick={() => execute(async () => {
          await post('/api/admin/payroll-periods', { attendance_period_id: period.id }); message.success('Đã tạo bản nháp lương');
        })}>Tạo bảng lương</Button>}
      </Space></Card>)}</div><Pager data={periods.data} setPage={setPeriodPage} />
    <h2 className="section-title">Bảng lương</h2><ResourceState {...payrolls} empty={!payrolls.data?.items.length} />
    <div className="list-grid">{payrolls.data?.items.map(period => <Card key={period.id}><div className="card-head"><b>{period.from_date} → {period.to_date}</b><Status value={period.status} /></div>
      <Space wrap><Button onClick={() => execute(() => view(period.id))}>Xem chi tiết</Button>
        {period.status !== 'LOCKED' && <Button loading={busy} disabled={!me.features.payroll} onClick={() => {
          setDecision({ kind: period.status === 'DRAFT' ? 'approve' : 'lock', period }); decisionForm.resetFields();
        }}>{period.status === 'DRAFT' ? 'Duyệt lương' : 'Chốt phiếu lương'}</Button>}
        <Button onClick={() => execute(() => downloadCsv(period.id))}>Xuất CSV</Button></Space></Card>)}</div><Pager data={payrolls.data} setPage={setPayrollPage} />
    <Modal title="Tạo kỳ công" forceRender open={openCreate} footer={null} onCancel={() => setOpenCreate(false)}>
      <Form form={form} layout="vertical" onFinish={values => execute(async () => {
        await post('/api/admin/attendance-periods', values); setOpenCreate(false); message.success('Đã tạo kỳ công');
      })}><Form.Item name="branch_id" label="Cơ sở" rules={[{ required: true }]}><Select options={me.branches.filter(b => me.managed_branch_ids.includes(b.id)).map(b => ({ value: b.id, label: b.name }))} /></Form.Item>
        <Form.Item name="from_date" label="Từ ngày" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Form.Item name="to_date" label="Đến hết ngày" rules={[{ required: true }]}><Input type="date" /></Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>Tạo kỳ công</Button></Form>
    </Modal>
    <Modal title={decision?.kind === 'attendance-lock' ? 'Khóa kỳ công' : decision?.kind === 'approve' ? 'Duyệt bảng lương' : 'Chốt phiếu lương'}
      open={!!decision} footer={null} onCancel={() => setDecision(undefined)}>
      <p>Sau khi khóa, dữ liệu đã chốt được giữ nguyên. Điều chỉnh thu nhập về sau cần ghi sang kỳ tiếp theo.</p>
      <Form form={decisionForm} layout="vertical" onFinish={values => execute(async () => {
        const d = decision!;
        const path = d.kind === 'attendance-lock' ? `/api/admin/attendance-periods/${d.period.id}/lock` : `/api/admin/payroll-periods/${d.period.id}/${d.kind}`;
        await post(path, { ...values, version: d.period.version }); setDecision(undefined); message.success('Đã lưu trạng thái kỳ');
      })}><Reason /><Button type="primary" htmlType="submit" loading={busy}>Xác nhận</Button></Form>
    </Modal>
    <Drawer title="Chi tiết bảng lương" width={900} open={!!selected} onClose={() => setSelected(undefined)}>
      {selected && <><p>{selected.from_date} → {selected.to_date} · <Status value={selected.status} /></p>
        <Alert type="info" message="Các khoản dưới đây là tổng trước thuế/bảo hiểm. Giờ công, mức giờ và hoa hồng đã được lưu tại thời điểm tạo bản nháp." />
        {!!selected.warnings?.length && <Alert className="section-title" type="warning" message={`${selected.warnings.length} nguồn hoa hồng đã thay đổi sau khi tạo bản nháp.`}
          action={<Button loading={busy} onClick={() => execute(async () => {
            await post(`/api/admin/payroll-periods/${selected.id}/reconcile`, { version: selected.version, reason: 'Đối soát trạng thái hoa hồng nguồn trước khi duyệt' });
            await view(selected.id); message.success('Đã ghi điều chỉnh hoa hồng và nhật ký');
          })}>Đối soát lại</Button>} />}
        <div className="mobile-cards">{selected.lines.map(line => <Card key={line.id} className="small-card"><h3>{line.source_snapshot.staff_name}</h3>
          <Descriptions column={1} items={(['base', 'overtime', 'commission', 'allowance', 'deduction', 'net'] as const).map((key, i) => ({ key,
            label: ['Lương công', 'Tăng ca', 'Hoa hồng', 'Phụ cấp', 'Khấu trừ', 'Tổng'][i], children: vnd(line[key]) }))} />
          <Button disabled={selected.status !== 'DRAFT'} onClick={() => { setAdjusting(line); adjustForm.resetFields(); }}>Điều chỉnh</Button></Card>)}</div>
        <Table<PayrollLine> className="section-title desktop-table" rowKey="id" dataSource={selected.lines} pagination={false} scroll={{ x: 740 }} columns={[
          { title: 'Nhân viên', render: (_, l) => l.source_snapshot.staff_name },
          ...(['base', 'overtime', 'commission', 'allowance', 'deduction', 'net'] as const).map((key, i) => ({ title: ['Lương công', 'Tăng ca', 'Hoa hồng', 'Phụ cấp', 'Khấu trừ', 'Tổng'][i], render: (_: unknown, l: PayrollLine) => vnd(l[key]) })),
          { title: '', render: (_, line) => <Button disabled={selected.status !== 'DRAFT'} onClick={() => { setAdjusting(line); adjustForm.resetFields(); }}>Điều chỉnh</Button> }
        ]} />
        <h3>Đối soát công và hoa hồng</h3>{selected.lines.map(line => <Card key={line.id} className="small-card"><b>{line.source_snapshot.staff_name}</b>
          <p>{line.source_snapshot.attendance.map(s => `${s.work_date}: ${s.paid_minutes} phút + ${s.overtime_minutes} phút tăng ca`).join('; ') || 'Không có giờ công kỳ này'}</p>
          <p>{line.source_snapshot.commissions.map(c => `${c.service_name}: ${vnd(c.amount)}`).join('; ') || 'Không có hoa hồng mới'}</p>
          {line.source_snapshot.commission_deltas.map((c, i) => <p key={i}>Điều chỉnh hoa hồng #{c.commission_id}: {vnd(c.amount)}</p>)}</Card>)}</>}
    </Drawer>
    <Modal title={`Điều chỉnh ${adjusting?.staff_name || ''}`} open={!!adjusting} footer={null} onCancel={() => setAdjusting(undefined)}>
      <Form form={adjustForm} layout="vertical" initialValues={{ allowance_delta: 0, deduction_delta: 0 }} onFinish={values => execute(async () => {
        await post(`/api/admin/payroll-lines/${adjusting!.id}/adjust`, { ...values, version: selected!.version });
        await view(selected!.id); setAdjusting(undefined); message.success('Đã ghi nhật ký điều chỉnh');
      })}><Form.Item name="allowance_delta" label="Phụ cấp / thưởng thêm (VNĐ)"><InputNumber precision={0} min={-1000000000} max={1000000000} /></Form.Item>
        <Form.Item name="deduction_delta" label="Khấu trừ thêm (VNĐ)"><InputNumber precision={0} min={-1000000000} max={1000000000} /></Form.Item>
        <p className="muted">Số âm dùng để hoàn lại điều chỉnh cũ. Chỉ ghi khoản khấu trừ có căn cứ được duyệt.</p>
        <Reason /><Button type="primary" htmlType="submit" loading={busy}>Ghi điều chỉnh</Button></Form>
    </Modal>
  </>;
}

const initialPolicy: Policy = { latitude: 10.78686228650495, longitude: 106.5794979291708, radius_m: 500, max_accuracy_m: 150,
  max_age_seconds: 30, checkin_early_minutes: 30, checkout_late_minutes: 120,
  unpaid_break_minutes: 0, retention_days: 90, enabled: false, payroll_model: 'hourly-approved-v1' };

export function Branches({ me }: { me: Me }) {
  const r = useResource<{ items: Branch[] }>('/api/admin/branches');
  const [editing, setEditing] = useState<Branch | 'new'>();
  const [assigning, setAssigning] = useState<Branch>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const [memberForm] = Form.useForm();
  const [shiftForm] = Form.useForm();
  const { message } = App.useApp();
  async function perform(fn: () => Promise<void>) {
    setBusy(true); try { await fn(); r.reload(); message.success('Đã lưu cấu hình'); }
    catch (error) { message.error((error as Error).message); } finally { setBusy(false); }
  }
  function edit(branch: Branch | 'new') {
    setEditing(branch); form.resetFields();
    form.setFieldsValue(branch === 'new' ? { name: 'Bin Spa', address: '', ...initialPolicy } : { ...branch, ...branch.policy });
  }
  if (me.features.simple_attendance) return <>{title('Địa điểm chấm công', 'Tất cả ca dùng cùng địa điểm. Không cần phân cơ sở, gắn định vị hoặc gán nhân viên trước khi chấm.')}
    <ResourceState {...r} empty={!r.data?.items.length} />
    {r.data?.items.map(branch => <Card key={branch.id}><h2>{branch.name}</h2><TagStatus enabled={!!branch.policy?.enabled} />
      <p>Tọa độ: {branch.policy?.latitude}, {branch.policy?.longitude}</p>
      <p>Bán kính {branch.policy?.radius_m} m · Sai số GPS tối đa {branch.policy?.max_accuracy_m} m</p>
      <p>Nhân viên chọn ca đang mở và chấm vào/ra. Nếu không chấm được, gửi yêu cầu để quản lý duyệt.</p>
      <Space wrap><Button href="/admin/shifts">Quản lý ca làm</Button><Button href="/admin/operations/adjustments">Yêu cầu chấm công</Button></Space>
    </Card>)}</>;
  return <>{title('Cơ sở và chính sách GPS', 'Cấu hình theo địa điểm thực tế; mỗi lần đổi chính sách đều giữ lịch sử.')}
    {me.user.role === 'admin' && <Button type="primary" onClick={() => edit('new')}>Thêm cơ sở</Button>}
    <ResourceState {...r} empty={!r.data?.items.length} />
    <div className="list-grid section-title">{r.data?.items.map(branch => <Card key={branch.id}><div className="card-head"><h2>{branch.name}</h2><TagStatus enabled={!!branch.policy?.enabled} /></div>
      <p>{branch.address || 'Chưa nhập địa chỉ'}</p><p>Bán kính {branch.policy?.radius_m || '—'} m · Sai số tối đa {branch.policy?.max_accuracy_m || '—'} m</p>
      <p>Chính sách phiên bản {branch.policy?.version || '—'}</p>
      <p>Nhân viên: {branch.members?.map(m => `${m.name}${m.can_manage ? ' (quản lý)' : ''}`).join(', ') || 'Chưa phân công'}</p>
      {me.user.role === 'admin' && <Space wrap><Button onClick={() => edit(branch)}>Chính sách GPS</Button><Button onClick={() => { setAssigning(branch); memberForm.resetFields(); shiftForm.resetFields(); }}>Phân cơ sở / gắn ca</Button></Space>}
    </Card>)}</div>
    <Drawer title={editing === 'new' ? 'Thêm cơ sở' : 'Chính sách GPS'} open={!!editing} onClose={() => setEditing(undefined)} width={500}>
      <Form form={form} layout="vertical" onFinish={values => perform(async () => {
        const { name, address, reason, ...settings } = values;
        const payload = { ...settings, payroll_model: 'hourly-approved-v1' };
        if (editing === 'new') await post('/api/admin/branches', { name, address, reason, policy: payload });
        else await post(`/api/admin/branches/${(editing as Branch).id}/policy`, { settings: payload, reason });
        setEditing(undefined);
      })}>
        {editing === 'new' && <><Form.Item name="name" label="Tên cơ sở" rules={[{ required: true, min: 3, max: 100 }]}><Input /></Form.Item><Form.Item name="address" label="Địa chỉ"><Input maxLength={255} /></Form.Item></>}
        <div className="form-grid">{[
          ['latitude', 'Vĩ độ', -90, 90], ['longitude', 'Kinh độ', -180, 180], ['radius_m', 'Bán kính (m)', 1, 2000],
          ['max_accuracy_m', 'Sai số GPS tối đa (m)', 1, 1000], ['max_age_seconds', 'Độ cũ GPS tối đa (giây)', 1, 120],
          ['checkin_early_minutes', 'Mở chấm vào trước ca (phút)', 0, 180], ['checkout_late_minutes', 'Chấm ra sau ca tối đa (phút)', 0, 720],
          ['unpaid_break_minutes', 'Nghỉ không lương (phút)', 0, 480], ['retention_days', 'Giữ tọa độ (ngày)', 1, 365]
        ].map(([key, label, min, max]) => <Form.Item key={key} name={String(key)} label={String(label)} rules={[{ required: true }]}>
          <InputNumber min={Number(min)} max={Number(max)} precision={['latitude', 'longitude'].includes(String(key)) ? 6 : 0} /></Form.Item>)}</div>
        <Alert type="info" message="Thử GPS tại cửa hàng trước khi bật. Bán kính và sai số là hai điều kiện độc lập." />
        <Form.Item className="section-title" name="enabled" label="Bật chính sách GPS cho cơ sở" valuePropName="checked"><Switch /></Form.Item><Reason />
        <Button type="primary" htmlType="submit" loading={busy}>Lưu phiên bản chính sách</Button>
      </Form>
    </Drawer>
    <Drawer title={`Phân cơ sở · ${assigning?.name || ''}`} open={!!assigning} onClose={() => setAssigning(undefined)} width={480}>
      <p>Lấy mã nhân viên và mã ca tại trang quản lý hiện tại. Nhân viên phải được cấp cơ sở trước khi gắn ca.</p>
      <Form form={memberForm} layout="vertical" initialValues={{ can_manage: false }} onFinish={values => perform(async () => {
        await api(`/api/admin/branches/${assigning!.id}/members/${values.staff_id}`, { method: 'PUT', body: JSON.stringify(values) });
      })}><Form.Item name="staff_id" label="Mã nhân viên" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>
        <Form.Item name="can_manage" label="Cho quản lý duyệt công tại cơ sở" valuePropName="checked"><Switch /></Form.Item><Reason />
        <Button htmlType="submit" loading={busy}>Cấp cơ sở cho nhân viên</Button></Form>
      <h2 className="section-title">Gắn ca vào cơ sở</h2><Form form={shiftForm} layout="vertical" onFinish={values => perform(async () => {
        await api(`/api/admin/shifts/${values.shift_id}/branch`, { method: 'PUT', body: JSON.stringify({ branch_id: assigning!.id, reason: values.reason }) });
      })}><Form.Item name="shift_id" label="Mã ca làm" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item><Reason />
        <Button htmlType="submit" loading={busy}>Gắn ca</Button></Form>
      <Space className="section-title" wrap><Button href="/admin/staff">Danh sách nhân viên</Button><Button href="/admin/shifts">Danh sách ca</Button></Space>
    </Drawer>
  </>;
}

function TagStatus({ enabled }: { enabled: boolean }) { return <span className={enabled ? 'enabled-label' : 'muted'}>{enabled ? 'GPS đã bật' : 'GPS chưa bật'}</span>; }

export function Audit() {
  const [page, setPage] = useState(1);
  const r = useResource<Page<{ id: number; actor_id: number; action: string; entity_type: string; entity_id: number; reason: string; created_at: string; before: unknown; after: unknown }>>(`/api/admin/operations/audit?page=${page}`);
  const [selected, setSelected] = useState<NonNullable<typeof r.data>['items'][number]>();
  return <>{title('Nhật ký thay đổi', 'Ai thực hiện, thời điểm, lý do và dữ liệu trước/sau.')}
    <ResourceState {...r} empty={!r.data?.items.length} />
    <div className="mobile-cards">{r.data?.items.map(item => <Card key={item.id} className="small-card"><b>{item.action}</b><p>{dateLabel(item.created_at)} · {time(item.created_at)} · Người thực hiện #{item.actor_id}</p>
      <p>{item.reason}</p><Button onClick={() => setSelected(item)}>Xem thay đổi</Button></Card>)}</div>
    <Table className="desktop-table" rowKey="id" dataSource={r.data?.items} pagination={false} scroll={{ x: 640 }} columns={[
      { title: 'Thời điểm', render: (_, item) => `${dateLabel(item.created_at)} ${time(item.created_at)}` },
      { title: 'Người thực hiện', dataIndex: 'actor_id' }, { title: 'Thao tác', dataIndex: 'action' }, { title: 'Lý do', dataIndex: 'reason' },
      { title: '', render: (_, item) => <Button onClick={() => setSelected(item)}>Xem thay đổi</Button> }
    ]} /><Pager data={r.data} setPage={setPage} />
    <Drawer title="Chi tiết nhật ký" width={620} open={!!selected} onClose={() => setSelected(undefined)}>
      <Descriptions column={1} items={[{ key: 'actor', label: 'Người thực hiện', children: selected?.actor_id },
        { key: 'reason', label: 'Lý do', children: selected?.reason }]} /><h3>Trước thay đổi</h3><pre>{JSON.stringify(selected?.before, null, 2)}</pre>
      <h3>Sau thay đổi</h3><pre>{JSON.stringify(selected?.after, null, 2)}</pre>
    </Drawer>
  </>;
}
