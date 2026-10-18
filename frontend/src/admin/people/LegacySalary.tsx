import { useState } from 'react';
import { Alert, App, Button, Card, Drawer, Empty, Input, Result, Segmented, Space, Table } from 'antd';
import { downloadFile } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { vnd } from '../booking/model';
import '../booking/booking.css';

type MonthRow = { maluong: number; manv: number; hoten: string; thang: number; nam: number; luongcoban: string; hoahong: string; thuong: string; khautru: string; tongluong: string };
type DayRow = { id_chitiet: number; manv: number; hoten: string; ngay_lam: string; chucvu: string; sogio_lam: string; dongia_gio: string; luong_ca: string;
  hoahong_ngay: string; thuong_ca: string; khautru_ca: string };
type Commissions = { hoten: string; thang: number; nam: number; total: string; entries: { id: number; service_name: string; amount: string; earned_at: string; source_label: string }[] };

/**
 * Read-only history of the old monthly payroll. While GPS payroll is on, the server refuses any
 * write to these records, so there is only ever one place that calculates pay for a period.
 */
function History({ me }: { me: Me }) {
  const { message } = App.useApp();
  const [query, setQuery] = useQuery();
  const mode = query.get('by') === 'day' ? 'day' : 'month';
  const month = query.get('month') || '2026-09';
  const day = query.get('day') || '';
  const params = mode === 'day' ? (day ? `filter_type=day&day=${day}` : '') : `filter_type=month&month_year=${month}`;
  const resource = useResource<(MonthRow | DayRow)[]>(params ? `/api/admin/salaries?${params}` : '');
  const [detail, setDetail] = useState<number | null>(null);
  const commissions = useResource<Commissions>(detail ? `/api/admin/salaries/${detail}/commissions` : '');
  const [busy, setBusy] = useState(false);
  const rows = resource.data || [];
  const total = rows.reduce((sum, r) => sum + Number('tongluong' in r ? r.tongluong : Number(r.luong_ca) + Number(r.hoahong_ngay) + Number(r.thuong_ca) - Number(r.khautru_ca)), 0);
  async function exportPdf() {
    setBusy(true);
    try { await downloadFile(`/api/admin/salaries/export-pdf?${params}`, mode === 'day' ? `luong-ngay-${day}.pdf` : `luong-thang-${month}.pdf`); }
    catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">CÔNG VÀ LƯƠNG</span><h1>Lịch sử lương cũ</h1><p>Bảng lương tính theo ca trước khi dùng bảng lương chấm công GPS. Chỉ xem, không sửa.</p></div>
      {me.features.payroll && me.features.employee_portal && <Button type="primary" href="/admin/operations/payroll">Kỳ công và lương hiện tại</Button>}
    </div>
    {me.features.payroll && <Alert type="info" showIcon style={{ marginBottom: 16 }} message="Bảng lương GPS đang là luồng tính lương chính. Mọi điều chỉnh làm ở Kỳ công và lương; dữ liệu ở đây giữ nguyên để đối chiếu." />}
    <Card>
      <Space wrap align="end">
        <Segmented value={mode} onChange={v => setQuery({ by: v === 'day' ? 'day' : null })} options={[{ value: 'month', label: 'Theo tháng' }, { value: 'day', label: 'Theo ngày' }]} />
        {mode === 'month' ? <label>Tháng<Input type="month" aria-label="Tháng" value={month} onChange={e => setQuery({ month: e.target.value || null })} /></label>
          : <label>Ngày<Input type="date" aria-label="Ngày" value={day} onChange={e => setQuery({ day: e.target.value || null })} /></label>}
        <Button onClick={exportPdf} loading={busy} disabled={!params || !rows.length}>Xuất PDF</Button>
      </Space>
      {!params ? <Empty className="section-title" description="Chọn ngày để xem lương theo ca." /> : <>
        <ResourceState {...resource} />
        {!resource.loading && !resource.error && (!rows.length ? <Empty className="section-title" description="Không có dữ liệu lương cũ trong khoảng này" /> : <>
          <p className="section-title"><strong>Tổng: {vnd(total)}</strong> · {rows.length} dòng</p>
          {mode === 'month' ? <Table rowKey="maluong" dataSource={rows as MonthRow[]} pagination={false} scroll={{ x: 760 }} columns={[
            { title: 'Nhân viên', dataIndex: 'hoten' }, { title: 'Lương ca', align: 'right' as const, render: (_: unknown, r: MonthRow) => vnd(r.luongcoban) },
            { title: 'Hoa hồng', align: 'right' as const, render: (_: unknown, r: MonthRow) => <Button type="link" size="small" onClick={() => setDetail(r.maluong)}>{vnd(r.hoahong)}</Button> },
            { title: 'Thưởng', align: 'right' as const, render: (_: unknown, r: MonthRow) => vnd(r.thuong) }, { title: 'Khấu trừ', align: 'right' as const, render: (_: unknown, r: MonthRow) => vnd(r.khautru) },
            { title: 'Tổng', align: 'right' as const, render: (_: unknown, r: MonthRow) => <strong>{vnd(r.tongluong)}</strong> }]} />
            : <Table rowKey="id_chitiet" dataSource={rows as DayRow[]} pagination={false} scroll={{ x: 820 }} columns={[
              { title: 'Nhân viên', render: (_: unknown, r: DayRow) => <>{r.hoten}<div className="muted">{r.chucvu}</div></> },
              { title: 'Giờ × đơn giá', render: (_: unknown, r: DayRow) => `${Number(r.sogio_lam)} × ${vnd(r.dongia_gio)}` },
              { title: 'Lương ca', align: 'right' as const, render: (_: unknown, r: DayRow) => vnd(r.luong_ca) }, { title: 'Hoa hồng', align: 'right' as const, render: (_: unknown, r: DayRow) => vnd(r.hoahong_ngay) },
              { title: 'Thưởng', align: 'right' as const, render: (_: unknown, r: DayRow) => vnd(r.thuong_ca) }, { title: 'Khấu trừ', align: 'right' as const, render: (_: unknown, r: DayRow) => vnd(r.khautru_ca) }]} />}
        </>)}
      </>}
    </Card>
    <Drawer open={detail !== null} onClose={() => setDetail(null)} width={520} destroyOnHidden title={commissions.data ? `Hoa hồng ${commissions.data.hoten} · ${commissions.data.thang}/${commissions.data.nam}` : 'Hoa hồng'}>
      <ResourceState {...commissions} />
      {commissions.data && (!commissions.data.entries.length ? <Empty description="Không có hoa hồng" /> : <>
        <p><strong>Tổng {vnd(commissions.data.total)}</strong></p>
        <ul className="history-list">{commissions.data.entries.map(e => <li key={e.id}><span>{e.service_name}<div className="muted">{e.source_label} · {new Date(e.earned_at).toLocaleDateString('vi-VN')}</div></span><strong>{vnd(e.amount)}</strong></li>)}</ul></>)}
    </Drawer>
  </>;
}

export default function LegacySalary({ me }: { me: Me }) {
  if (me.user.role !== 'admin' && !(me.user.role === 'manager' && !me.features.payroll)) {
    return <Result status="403" title="Không có quyền xem lịch sử lương cũ" extra={me.features.payroll ? <Button href="/admin/operations/payroll">Kỳ công và lương</Button> : undefined} />;
  }
  return <History me={me} />;
}
