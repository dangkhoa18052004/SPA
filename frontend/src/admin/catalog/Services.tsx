import { useEffect, useState } from 'react';
import { Alert, App, Button, Card, Descriptions, Drawer, Empty, Form, Input, InputNumber, Pagination, Result, Select, Space, Statistic, Switch, Table, Tag } from 'antd';
import { api } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { fold, vnd } from '../booking/model';
import { imageError, serviceImage } from './model';
import type { CatalogService, Category } from './model';
import '../booking/booking.css';
import { FilePick } from './ui';
import './catalog.css';

const PAGE = 10;
type FormValues = { tendv: string; gia: number; thoiluong?: number | null; category_id?: number | null; commission_percent?: number | null;
  commission_fixed?: number | null; mota?: string; post_care_instructions?: string; active: boolean };
const statusTag = (s: CatalogService) => <Tag color={s.active ? 'green' : 'default'}>{s.active ? 'Đang hoạt động' : 'Ngừng hoạt động'}</Tag>;

function ServiceForm({ editing, categories, onClose, onSaved }: { editing: CatalogService | 'new' | null; categories: Category[]; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm<FormValues>();
  const { message, modal } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const isNew = editing === 'new';
  const current = editing && editing !== 'new' ? editing : null;
  useEffect(() => { setFile(null); setPreview(current ? (current.anhdichvu ? serviceImage(current) : '') : ''); }, [editing]);
  function close() {
    if (busy) return;
    if (!form.isFieldsTouched() && !file) { onClose(); return; }
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: onClose });
  }
  function pick(selected?: File) {
    if (!selected) return;
    const error = imageError(selected, ['image/jpeg', 'image/png']);
    if (error) { message.error(error); return; }
    setFile(selected); setPreview(URL.createObjectURL(selected));
  }
  async function save(values: FormValues) {
    setBusy(true);
    const body = new FormData();
    body.append('tendv', values.tendv.trim()); body.append('gia', String(values.gia));
    if (values.thoiluong) body.append('thoiluong', String(values.thoiluong));
    body.append('category_id', values.category_id ? String(values.category_id) : '');
    body.append('mota', values.mota?.trim() || ''); body.append('post_care_instructions', values.post_care_instructions?.trim() || '');
    body.append('commission_percent', values.commission_percent == null ? '' : String(values.commission_percent));
    body.append('commission_fixed', values.commission_fixed == null ? '' : String(values.commission_fixed));
    body.append('active', String(values.active));
    if (file) body.append('anhdichvu', file);
    try {
      const result = await api<{ msg: string; madv?: number }>(isNew ? '/api/admin/services' : `/api/admin/services/${current!.madv}`, { method: isNew ? 'POST' : 'PUT', body });
      // New services start active on the server; apply "inactive" right after when chosen.
      if (isNew && !values.active && result.madv) {
        const status = new FormData(); status.append('active', 'false');
        await api(`/api/admin/services/${result.madv}`, { method: 'PUT', body: status });
      }
      message.success(result.msg); onSaved();
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  const initial: Partial<FormValues> = current ? { tendv: current.tendv, gia: Number(current.gia), thoiluong: current.thoiluong, category_id: current.category_id,
    commission_percent: current.commission_percent == null ? null : Number(current.commission_percent),
    commission_fixed: current.commission_fixed == null ? null : Number(current.commission_fixed), mota: current.mota || '',
    post_care_instructions: current.post_care_instructions || '', active: current.active } : { active: true, thoiluong: 60 };
  return <Drawer open={editing !== null} onClose={close} width={600} destroyOnHidden maskClosable={!busy} title={isNew ? 'Thêm dịch vụ' : `Sửa dịch vụ #${current?.madv}`}
    footer={<Space><Button onClick={close} disabled={busy}>Hủy</Button><Button type="primary" loading={busy} onClick={() => form.submit()} data-testid="service-save">Lưu</Button></Space>}>
    <Form form={form} layout="vertical" initialValues={initial} onFinish={save} disabled={busy}>
      <Form.Item label="Hình ảnh" extra="JPG hoặc PNG, tối đa 5 MB.">
        <div className="catalog-image-field">
          <img src={preview || '/static/images/default-service.jpg'} alt="" />
          <FilePick accept="image/jpeg,image/png" label="Ảnh dịch vụ" onPick={pick} />
        </div>
      </Form.Item>
      <Form.Item label="Tên dịch vụ" name="tendv" rules={[{ required: true, whitespace: true, message: 'Nhập tên dịch vụ' }, { max: 200 }]}><Input /></Form.Item>
      <div className="form-grid">
        <Form.Item label="Giá (VNĐ)" name="gia" rules={[{ required: true, message: 'Nhập giá' }]}>
          <InputNumber<number> min={0} step={1000} precision={0} style={{ width: "100%" }} formatter={v => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.')} parser={v => Number((v || '').replace(/\./g, ''))} /></Form.Item>
        <Form.Item label="Thời lượng (phút)" name="thoiluong"><InputNumber min={0} max={1440} precision={0} style={{ width: '100%' }} /></Form.Item>
      </div>
      <Form.Item label="Danh mục" name="category_id" extra="Dùng để đề xuất dịch vụ phù hợp cho từng khách hàng.">
        <Select allowClear aria-label="Danh mục dịch vụ" placeholder="Chưa phân loại" options={categories.map(c => ({ value: c.id, label: c.name }))} /></Form.Item>
      <fieldset className="catalog-fieldset"><legend>Hoa hồng kỹ thuật viên</legend>
        <div className="form-grid">
          <Form.Item label="Theo % giá dịch vụ" name="commission_percent"><InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} /></Form.Item>
          <Form.Item label="Hoặc số tiền cố định / lượt" name="commission_fixed"><InputNumber min={0} step={1000} precision={0} style={{ width: '100%' }} /></Form.Item>
        </div>
        <p className="muted">Số tiền cố định được ưu tiên nếu nhập cả hai; để trống cả hai là không có hoa hồng. Thay đổi chỉ áp dụng cho lịch hoàn thành sau khi lưu.</p>
      </fieldset>
      <Form.Item label="Mô tả" name="mota"><Input.TextArea rows={3} /></Form.Item>
      <Form.Item label="Dặn dò sau dịch vụ" name="post_care_instructions" extra="Dùng cho tin nhắn chăm sóc tự động sau khi khách hoàn thành dịch vụ." rules={[{ max: 10000 }]}>
        <Input.TextArea rows={5} maxLength={10000} /></Form.Item>
      <Form.Item label="Đang mở dịch vụ" name="active" valuePropName="checked"><Switch /></Form.Item>
    </Form>
  </Drawer>;
}

/** Service catalogue: same /api/admin/services as before; only roles the API allows can edit. */
function ServiceList() {
  const [query, setQuery] = useQuery();
  const resource = useResource<CatalogService[]>('/api/admin/services');
  const categoriesResource = useResource<{ categories: Category[] }>('/api/admin/service-categories');
  const categories = categoriesResource.data?.categories || [];
  const status = query.get('status') || '';
  const category = query.get('category') || '';
  const search = query.get('q') || '';
  const page = Math.max(1, Number(query.get('page')) || 1);
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const [editing, setEditing] = useState<CatalogService | 'new' | null>(null);
  const [viewing, setViewing] = useState<CatalogService | null>(null);
  const all = resource.data || [];
  const tokens = fold(search).split(/\s+/).filter(Boolean);
  const rows = all.filter(s => (!status || String(s.active) === status) && (!category || (category === 'none' ? !s.category_id : String(s.category_id) === category))
    && tokens.every(t => fold(`${s.madv} ${s.tendv} ${s.mota || ''}`).includes(t))).sort((a, b) => Number(b.active) - Number(a.active) || a.tendv.localeCompare(b.tendv, 'vi'));
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);
  const categoryName = (id: number | null) => categories.find(c => c.id === id)?.name || 'Chưa phân loại';
  const actions = (s: CatalogService) => <Space wrap size={6}><Button size="small" onClick={() => setViewing(s)}>Xem</Button><Button size="small" onClick={() => setEditing(s)}>Sửa</Button></Space>;
  const active = !!(status || category || search);
  return <>
    <div className="page-heading section-toolbar">
      <div><span className="eyebrow">DANH MỤC</span><h1>Dịch vụ</h1><p>Giá, thời lượng, ảnh, hoa hồng và nội dung chăm sóc sau dịch vụ.</p></div>
      <Button type="primary" onClick={() => setEditing('new')} data-testid="service-new">+ Thêm dịch vụ</Button>
    </div>
    <div className="appointment-summary admin-stats">
      <Card><Statistic title="Tổng dịch vụ" value={resource.data ? all.length : '…'} /></Card>
      <Card><Statistic title="Đang hoạt động" value={resource.data ? all.filter(s => s.active).length : '…'} /></Card>
      <Card><Statistic title="Chưa có dặn dò sau dịch vụ" value={resource.data ? all.filter(s => s.active && !s.post_care_instructions).length : '…'} /></Card>
    </div>
    <Card className="section-title">
      <div className="booking-filters">
        <Select aria-label="Trạng thái dịch vụ" value={status} onChange={v => setQuery({ status: v || null, page: null })}
          options={[{ value: '', label: 'Tất cả trạng thái' }, { value: 'true', label: 'Đang hoạt động' }, { value: 'false', label: 'Ngừng hoạt động' }]} />
        <Select aria-label="Lọc theo danh mục" value={category} onChange={v => setQuery({ category: v || null, page: null })}
          options={[{ value: '', label: 'Tất cả danh mục' }, { value: 'none', label: 'Chưa phân loại' }, ...categories.map(c => ({ value: String(c.id), label: c.name }))]} />
        <Input.Search aria-label="Tìm dịch vụ" placeholder="Tên, mô tả, mã dịch vụ" allowClear value={draft}
          onChange={e => { setDraft(e.target.value); if (!e.target.value) setQuery({ q: null, page: null }, true); }} onSearch={v => setQuery({ q: v.trim() || null, page: null })} />
        <Button disabled={!active} onClick={() => setQuery({ status: null, category: null, q: null, page: null })}>Xóa bộ lọc</Button>
      </div>
      <p className="muted section-title" aria-live="polite">{rows.length} dịch vụ{active ? ' · đang lọc' : ''}</p>
      <ResourceState {...resource} />
      {!resource.loading && !resource.error && (!rows.length ? <Empty description="Không tìm thấy dịch vụ" /> : <>
        <div className="desktop-table"><Table rowKey="madv" dataSource={pageRows} pagination={false} columns={[
          { title: 'Dịch vụ', render: (_: unknown, s: CatalogService) => <Space><img className="catalog-thumb" src={serviceImage(s)} alt="" /><span><strong>{s.tendv}</strong><div className="muted">#{s.madv} · {categoryName(s.category_id)}</div></span></Space> },
          { title: 'Giá', align: 'right' as const, render: (_: unknown, s: CatalogService) => vnd(s.gia) },
          { title: 'Thời lượng', render: (_: unknown, s: CatalogService) => s.thoiluong ? `${s.thoiluong} phút` : '—' },
          { title: 'Hoa hồng', render: (_: unknown, s: CatalogService) => s.commission_fixed ? vnd(s.commission_fixed) : s.commission_percent ? `${Number(s.commission_percent)}%` : '—' },
          { title: 'Trạng thái', render: (_: unknown, s: CatalogService) => statusTag(s) }, { title: 'Thao tác', render: (_: unknown, s: CatalogService) => actions(s) }]} /></div>
        <div className="mobile-cards">{pageRows.map(s => <Card key={s.madv} className="small-card"><div className="card-head"><Space><img className="catalog-thumb" src={serviceImage(s)} alt="" /><h2>{s.tendv}</h2></Space>{statusTag(s)}</div>
          <p>{vnd(s.gia)} · {s.thoiluong ? `${s.thoiluong} phút` : '—'} · {categoryName(s.category_id)}</p>{actions(s)}</Card>)}</div>
        {rows.length > PAGE && <Pagination className="pager" current={page} pageSize={PAGE} total={rows.length} showSizeChanger={false} onChange={n => setQuery({ page: n > 1 ? n : null })} />}
      </>)}
    </Card>
    <Drawer open={!!viewing} onClose={() => setViewing(null)} width={520} title={viewing?.tendv} destroyOnHidden
      extra={viewing && <Button onClick={() => { setEditing(viewing); setViewing(null); }}>Sửa</Button>}>
      {viewing && <><img className="catalog-hero" src={serviceImage(viewing)} alt="" />
        <Descriptions column={1} size="small" items={[{ key: 'id', label: 'Mã', children: `#${viewing.madv}` }, { key: 'price', label: 'Giá', children: vnd(viewing.gia) },
          { key: 'dur', label: 'Thời lượng', children: viewing.thoiluong ? `${viewing.thoiluong} phút` : '—' }, { key: 'cat', label: 'Danh mục', children: categoryName(viewing.category_id) },
          { key: 'status', label: 'Trạng thái', children: statusTag(viewing) }]} />
        <h3 className="section-title">Mô tả</h3><p className="pre-wrap">{viewing.mota || 'Chưa có mô tả.'}</p>
        <h3>Dặn dò sau dịch vụ</h3><p className="pre-wrap">{viewing.post_care_instructions || 'Chưa có hướng dẫn.'}</p></>}
    </Drawer>
    <ServiceForm key={editing === 'new' ? 'new' : editing?.madv ?? 'none'} editing={editing} categories={categories} onClose={() => setEditing(null)}
      onSaved={() => { setEditing(null); resource.reload(); }} />
    {categoriesResource.error && <Alert className="section-title" type="warning" showIcon message={`Chưa tải được danh mục: ${categoriesResource.error}`} />}
  </>;
}

export default function Services({ me }: { me: Me }) {
  if (!['admin', 'manager'].includes(me.user.role)) return <Result status="403" title="Không có quyền quản lý dịch vụ" />;
  return <ServiceList />;
}
