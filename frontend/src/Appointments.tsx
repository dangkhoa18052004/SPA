import { useState } from 'react';
import { Button, Card, Descriptions, Drawer, Form, Input, Select, Space, Statistic, Table, Tag } from 'antd';
import { dateLabel, time } from './attendance';
import { Pager, ResourceState, useResource } from './components';
import type { EmployeeAppointment, Page } from './types';

const statuses = [
  { value: 'pending', label: 'Chờ xác nhận' }, { value: 'confirmed', label: 'Đã xác nhận' },
  { value: 'in_progress', label: 'Đang thực hiện' }, { value: 'completed', label: 'Đã hoàn thành' },
  { value: 'cancelled', label: 'Đã hủy' },
];
const statusColors: Record<string, string> = {
  pending: 'gold', confirmed: 'blue', in_progress: 'cyan', completed: 'green', cancelled: 'default',
};
type Result = Page<EmployeeAppointment> & { summary: { total: number; today: number; upcoming: number }; today: string };

function AppointmentStatus({ item }: { item: EmployeeAppointment }) {
  return <Tag color={statusColors[item.status]}>{item.status_label}</Tag>;
}

export default function Appointments() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<EmployeeAppointment>();
  const [form] = Form.useForm();
  const params = new URLSearchParams({ ...filters, page: String(page) });
  const resource = useResource<Result>(`/api/me/appointments?${params}`);
  function apply(values: Record<string, string>) {
    setFilters(Object.fromEntries(Object.entries(values).filter(([, value]) => !!value)));
    setPage(1);
  }
  const services = (item: EmployeeAppointment) => item.services.map(service => service.name).join(', ') || 'Chưa có dịch vụ';
  return <>
    <div className="page-heading"><h1>Lịch hẹn của tôi</h1><p>Các lịch khách đặt với bạn, gồm lịch sắp tới và lịch sử phục vụ.</p></div>
    {resource.data && <div className="appointment-summary">
      {([['total', 'Toàn bộ'], ['today', 'Hôm nay'], ['upcoming', 'Sắp tới']] as const).map(([key, label]) =>
        <Card key={key}><Statistic title={label} value={resource.data!.summary[key]} /></Card>)}
    </div>}
    <Card className="section-title"><Form form={form} layout="vertical" className="appointment-filters" onFinish={apply}>
      <Form.Item name="from_date" label="Từ ngày"><Input type="date" /></Form.Item>
      <Form.Item name="to_date" label="Đến ngày"><Input type="date" /></Form.Item>
      <Form.Item name="status" label="Trạng thái"><Select allowClear placeholder="Tất cả trạng thái" options={statuses} /></Form.Item>
      <Form.Item name="q" label="Khách hàng"><Input placeholder="Tên hoặc số điện thoại" maxLength={100} allowClear /></Form.Item>
      <Space wrap className="appointment-filter-actions"><Button type="primary" htmlType="submit">Lọc lịch hẹn</Button>
        <Button disabled={!resource.data} onClick={() => { const values = { from_date: resource.data!.today, to_date: resource.data!.today };
          form.resetFields(); form.setFieldsValue(values); apply(values); }}>Hôm nay</Button>
        <Button onClick={() => { form.resetFields(); apply({}); }}>Tất cả lịch hẹn</Button>
        <Button onClick={resource.reload}>Cập nhật</Button>
      </Space>
    </Form></Card>
    <div className="section-toolbar"><h2>{resource.data?.total ?? 0} lịch hẹn</h2><span className="muted">Giờ Việt Nam</span></div>
    <ResourceState {...resource} empty={!resource.data?.items.length} />
    {!resource.loading && !resource.error && <>
      <div className="mobile-cards list-grid">{resource.data?.items.map(item => <Card key={item.id} className="appointment-card">
        <div className="card-head"><b>{dateLabel(item.scheduled_at)} · {time(item.scheduled_at)}</b><AppointmentStatus item={item} /></div>
        <h2>{item.customer_name}</h2><p>{services(item)}</p>
        <p>{time(item.scheduled_at)}–{time(item.ends_at)} · {item.duration_minutes} phút</p>
        <p>{item.customer_phone || 'Chưa có số điện thoại'}</p>
        <Button onClick={() => setSelected(item)}>Xem chi tiết</Button>
      </Card>)}</div>
      <Table<EmployeeAppointment> className="desktop-table" rowKey="id" dataSource={resource.data?.items} pagination={false} scroll={{ x: 780 }} columns={[
        { title: 'Ngày / giờ', render: (_, item) => <><b>{dateLabel(item.scheduled_at)}</b><div>{time(item.scheduled_at)}–{time(item.ends_at)}</div></> },
        { title: 'Khách hàng', render: (_, item) => <><b>{item.customer_name}</b><div>{item.customer_phone || 'Chưa có số điện thoại'}</div></> },
        { title: 'Dịch vụ', render: (_, item) => services(item) },
        { title: 'Trạng thái', render: (_, item) => <AppointmentStatus item={item} /> },
        { title: '', render: (_, item) => <Button onClick={() => setSelected(item)}>Xem chi tiết</Button> },
      ]} />
      <Pager data={resource.data} setPage={setPage} />
    </>}
    <Drawer title="Chi tiết lịch hẹn" width={520} open={!!selected} onClose={() => setSelected(undefined)}>
      {selected && <><h2>{selected.customer_name}</h2><AppointmentStatus item={selected} />
        <Descriptions className="section-title" column={1} bordered items={[
          { key: 'id', label: 'Mã lịch hẹn', children: `#${selected.id}` },
          { key: 'date', label: 'Ngày hẹn', children: dateLabel(selected.scheduled_at) },
          { key: 'time', label: 'Khung giờ', children: `${time(selected.scheduled_at)}–${time(selected.ends_at)}` },
          { key: 'phone', label: 'Số điện thoại', children: selected.customer_phone || 'Chưa có' },
          { key: 'services', label: 'Dịch vụ', children: selected.services.map(service => <div key={service.id}>{service.name} · {service.duration_minutes} phút</div>) },
          { key: 'note', label: 'Ghi chú', children: <span className="appointment-note">{selected.note || 'Không có ghi chú'}</span> },
        ]} />
      </>}
    </Drawer>
  </>;
}
