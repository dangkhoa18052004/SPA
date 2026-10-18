import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, App, Button, Card, Checkbox, Descriptions, Empty, Form, Input, InputNumber, Result, Select, Skeleton, Space } from 'antd';
import { api } from '../../api';
import { navigate } from '../../router';
import type { Me } from '../../types';
import { vnd } from '../booking/model';
import { imageError, packageItemsError, packageQuote, validityLabel } from './model';
import type { ServicePackage } from './model';
import { saleTag } from './Packages';
import { AppLink, FilePick } from './ui';
import './catalog.css';

type Values = { tengoi: string; giagoi: number; mota?: string; validity_months?: number | null; unlimited: boolean; post_care_instructions?: string;
  customer_sale_enabled: boolean; staff_sale_enabled: boolean; active: boolean; items: { madv?: number; total_sessions?: number | null }[] };
const fallbackImage = '/static/images/default-package.svg';

/**
 * Create or edit a package. Sold packages keep their purchase snapshot on the server, so editing
 * never changes what customers already bought.
 */
function Editor({ id }: { id: number | null }) {
  const { message, modal } = App.useApp();
  const [form] = Form.useForm<Values>();
  const [services, setServices] = useState<{ madv: number; tendv: string; gia: string }[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState(fallbackImage);
  const dirty = useRef(false);
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [list, detail] = await Promise.all([api<{ services: { madv: number; tendv: string; gia: string }[] }>('/api/admin/packages'),
          id ? api<{ package: ServicePackage }>(`/api/admin/packages/${id}`) : Promise.resolve(null)]);
        if (!active) return;
        setServices(list.services);
        if (detail) {
          const p = detail.package;
          form.setFieldsValue({ tengoi: p.tengoi, giagoi: Number(p.giagoi), mota: p.mota || '', validity_months: p.validity_months ?? 6, unlimited: p.validity_months == null,
            post_care_instructions: p.post_care_instructions || '', customer_sale_enabled: p.customer_sale_enabled, staff_sale_enabled: p.staff_sale_enabled,
            active: p.active, items: p.items.map(i => ({ madv: i.madv, total_sessions: i.total_sessions })) });
          setPreview(p.image_url || fallbackImage);
        }
        setLoaded(true);
      } catch (e) { if (active) setError((e as Error).message); }
    })();
    return () => { active = false; };
  }, [id]);
  useEffect(() => {  // Warn before leaving the page with unsaved changes.
    const guard = (e: BeforeUnloadEvent) => { if (dirty.current) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, []);
  const values = Form.useWatch([], form) as Values | undefined;
  const price = Number(values?.giagoi) || 0;
  const rows = values?.items || [];
  const quote = useMemo(() => packageQuote(rows, services, price), [JSON.stringify(rows), services, price]);
  const unlimited = !!values?.unlimited;

  function leave() {
    const go = () => { dirty.current = false; navigate(id ? `/admin/packages/${id}` : '/admin/packages'); };
    if (!dirty.current) { go(); return; }
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục sửa', onOk: go });
  }
  function pick(selected?: File) {
    if (!selected) return;
    const problem = imageError(selected);
    if (problem) { message.error(problem); return; }
    setFile(selected); setPreview(URL.createObjectURL(selected)); dirty.current = true;
  }
  async function save(v: Values) {
    setSaveError('');
    const items = (v.items || []).map(i => ({ madv: Number(i.madv), total_sessions: Number(i.total_sessions) }));
    const problem = packageItemsError(items);
    if (problem) { setSaveError(problem); return; }
    if (quote.overpriced) {
      const ok = await new Promise<boolean>(resolve => modal.confirm({ title: 'Giá gói cao hơn tổng giá lẻ', content: `Tổng giá lẻ ${vnd(quote.retail)}, giá gói ${vnd(price)}. Vẫn lưu?`,
        okText: 'Vẫn lưu', cancelText: 'Xem lại', onOk: () => resolve(true), onCancel: () => resolve(false) }));
      if (!ok) return;
    }
    const payload = { tengoi: v.tengoi.trim(), giagoi: Number(v.giagoi), mota: v.mota?.trim() || '', validity_months: v.unlimited ? null : Number(v.validity_months),
      active: v.active, customer_sale_enabled: v.customer_sale_enabled, staff_sale_enabled: v.staff_sale_enabled,
      post_care_instructions: v.post_care_instructions?.trim() || '', items };
    const body = new FormData(); body.append('data', JSON.stringify(payload)); if (file) body.append('anhgoi', file);
    setBusy(true);
    try {
      const result = await api<{ package: ServicePackage }>(id ? `/api/admin/packages/${id}` : '/api/admin/packages', { method: id ? 'PUT' : 'POST', body });
      dirty.current = false;
      message.success(id ? 'Đã cập nhật gói dịch vụ.' : 'Đã tạo gói dịch vụ.');
      navigate(`/admin/packages/${result.package.magoi}`);
    } catch (e) { setSaveError((e as Error).message); } finally { setBusy(false); }
  }
  if (error) return <Result status="error" title="Chưa tải được dữ liệu gói" subTitle={error} extra={<AppLink href="/admin/packages">Về danh sách gói</AppLink>} />;
  return <>
    <div className="page-heading"><span className="eyebrow">DANH MỤC · GÓI DỊCH VỤ</span><h1>{id ? `Sửa gói #${id}` : 'Tạo gói dịch vụ'}</h1>
      <p>Thông tin, dịch vụ trong gói, giá, thời hạn và kênh bán.{id ? ' Khách đã mua giữ nguyên quyền lợi lúc mua.' : ''}</p></div>
    {!loaded ? <Skeleton active /> : <Form form={form} layout="vertical" onFinish={save} disabled={busy} onValuesChange={() => { dirty.current = true; }}
      initialValues={{ validity_months: 6, unlimited: false, customer_sale_enabled: true, staff_sale_enabled: true, active: true, items: [{ total_sessions: 1 }] }}>
      {!services.length && <Alert type="warning" showIcon message="Cần có ít nhất một dịch vụ đang hoạt động trước khi tạo gói." style={{ marginBottom: 16 }} />}
      <div className="package-form-layout">
        <div className="package-form-main">
          <Card title="Thông tin gói">
            <Form.Item label="Tên gói" name="tengoi" rules={[{ required: true, whitespace: true, message: 'Nhập tên gói' }, { max: 200 }]}><Input placeholder="Ví dụ: Gói chăm sóc da chuyên sâu" /></Form.Item>
            <Form.Item label="Giá gói (VNĐ)" name="giagoi" rules={[{ required: true, message: 'Nhập giá gói' }, { type: 'number', min: 1, message: 'Giá gói phải lớn hơn 0' }]}>
              <InputNumber<number> min={1} step={10000} precision={0} style={{ width: '100%' }} formatter={v => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.')} parser={v => Number((v || '').replace(/\./g, ''))} /></Form.Item>
            <Form.Item label="Mô tả" name="mota"><Input.TextArea rows={3} placeholder="Quyền lợi và đối tượng phù hợp" /></Form.Item>
            <Form.Item label="Ảnh đại diện" extra="JPG, PNG hoặc WEBP, tối đa 5 MB.">
              <div className="catalog-image-field"><img src={preview} alt="" /><FilePick accept="image/jpeg,image/png,image/webp" label="Ảnh gói" onPick={pick} /></div>
            </Form.Item>
          </Card>
          <Card title="Dịch vụ trong gói" className="section-title">
            <Form.List name="items">{(fields, { add, remove }) => <>
              {fields.map(field => {
                const row = rows[field.name] || {}; const unit = Number(services.find(s => s.madv === row.madv)?.gia || 0);
                return <div key={field.key} className="package-item-row">
                  <Form.Item name={[field.name, 'madv']} rules={[{ required: true, message: 'Chọn dịch vụ' }]} className="grow">
                    <Select showSearch placeholder="Chọn dịch vụ" aria-label={`Dịch vụ dòng ${field.name + 1}`} optionFilterProp="label"
                      options={services.map(s => ({ value: s.madv, label: `${s.tendv} · ${vnd(s.gia)}`, disabled: rows.some((r, n) => n !== field.name && r?.madv === s.madv) }))} /></Form.Item>
                  <Form.Item name={[field.name, 'total_sessions']} rules={[{ required: true, message: 'Số buổi' }]}>
                    <InputNumber min={1} max={10000} precision={0} addonAfter="buổi" aria-label={`Số buổi dòng ${field.name + 1}`} style={{ width: 150 }} /></Form.Item>
                  <span className="package-item-total">{vnd(unit * (Number(row.total_sessions) || 0))}</span>
                  <Button aria-label={`Xóa dòng ${field.name + 1}`} onClick={() => remove(field.name)} disabled={fields.length === 1}>Xóa</Button>
                </div>;
              })}
              <Button onClick={() => add({ total_sessions: 1 })}>+ Thêm dịch vụ</Button>
            </>}</Form.List>
          </Card>
          <Card title="Thời hạn và chăm sóc" className="section-title">
            <Space align="start" wrap>
              <Form.Item label="Hiệu lực (tháng)" name="validity_months" rules={[{ required: !unlimited, message: 'Nhập số tháng' }]}><InputNumber min={1} max={120} precision={0} disabled={unlimited} /></Form.Item>
              <Form.Item label=" " name="unlimited" valuePropName="checked"><Checkbox>Không giới hạn thời gian</Checkbox></Form.Item>
            </Space>
            <Form.Item label="Dặn dò riêng cho gói" name="post_care_instructions" extra="Gửi kèm email dặn dò sau dịch vụ khi khách dùng gói." rules={[{ max: 10000 }]}>
              <Input.TextArea rows={4} maxLength={10000} /></Form.Item>
          </Card>
          <Card title="Kênh bán" className="section-title">
            <Form.Item name="customer_sale_enabled" valuePropName="checked" style={{ marginBottom: 8 }}><Checkbox>Cho phép khách tự mua trên website</Checkbox></Form.Item>
            <Form.Item name="staff_sale_enabled" valuePropName="checked" style={{ marginBottom: 8 }}><Checkbox>Cho phép nhân viên bán tại quầy</Checkbox></Form.Item>
            <Form.Item name="active" valuePropName="checked" extra="Tắt để ngừng bán mới ở cả hai kênh; liệu trình đã mua vẫn dùng được."><Checkbox>Gói đang hoạt động</Checkbox></Form.Item>
          </Card>
        </div>
        <Card title="Tóm tắt giá" className="package-summary">
          <Descriptions column={1} size="small" items={[{ key: 'r', label: 'Tổng giá lẻ', children: vnd(quote.retail) }, { key: 'p', label: 'Giá gói', children: vnd(price) },
            { key: 's', label: 'Khách tiết kiệm', children: <strong data-testid="package-savings">{vnd(quote.savings)}</strong> },
            { key: 'v', label: 'Hiệu lực', children: validityLabel(unlimited ? null : Number(values?.validity_months) || null) }]} />
          {quote.overpriced && <Alert type="warning" showIcon message="Giá gói đang cao hơn tổng giá lẻ." />}
          {saveError && <Alert role="alert" type="error" showIcon message={saveError} className="section-title" />}
          <Space wrap className="section-title"><Button onClick={leave} disabled={busy}>Hủy</Button>
            <Button type="primary" htmlType="submit" loading={busy} data-testid="package-save">{id ? 'Lưu thay đổi' : 'Lưu gói'}</Button></Space>
        </Card>
      </div>
    </Form>}
  </>;
}

function Detail({ id }: { id: number }) {
  const [data, setData] = useState<ServicePackage>();
  const [error, setError] = useState('');
  useEffect(() => { let active = true; api<{ package: ServicePackage }>(`/api/admin/packages/${id}`).then(r => { if (active) setData(r.package); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; }; }, [id]);
  if (error) return <Result status="404" title="Không tìm thấy gói" subTitle={error} extra={<AppLink href="/admin/packages">Về danh sách gói</AppLink>} />;
  if (!data) return <Skeleton active />;
  return <>
    <div className="page-heading section-toolbar"><div><span className="eyebrow">GÓI DỊCH VỤ #{data.magoi}</span><h1>{data.tengoi}</h1><Space wrap>{saleTag(data)}<span className="muted">{validityLabel(data.validity_months)}</span></Space></div>
      <Space wrap><AppLink href="/admin/packages">Danh sách gói</AppLink><AppLink href={`/admin/packages/${data.magoi}/edit`} type="primary">Chỉnh sửa</AppLink></Space></div>
    <div className="package-form-layout">
      <div className="package-form-main">
        <Card><div className="sale-package-head"><img className="catalog-hero small" src={data.image_url || fallbackImage} alt="" /><div><h3>Mô tả</h3><p className="pre-wrap">{data.mota || 'Chưa có mô tả.'}</p></div></div></Card>
        <Card title="Dịch vụ trong gói" className="section-title"><ul className="invoice-lines">{data.items.map(i => <li key={i.madv}><span>{i.tendv} · {i.total_sessions} buổi × {vnd(i.regular_unit_price_snapshot)}</span>
          <span>{vnd(Number(i.regular_unit_price_snapshot) * i.total_sessions)}</span></li>)}</ul></Card>
        {data.post_care_instructions && <Card title="Dặn dò trong liệu trình" className="section-title"><p className="pre-wrap">{data.post_care_instructions}</p></Card>}
      </div>
      <Card title="Tổng quan giá" className="package-summary"><Descriptions column={1} size="small" items={[{ key: 'r', label: 'Giá lẻ', children: vnd(data.regular_total) },
        { key: 'p', label: 'Giá gói', children: <strong>{vnd(data.giagoi)}</strong> }, { key: 's', label: 'Tiết kiệm', children: vnd(Math.max(0, Number(data.savings))) }]} />
        {!data.items.length && <Empty description="Chưa có dịch vụ" />}</Card>
    </div>
  </>;
}

export default function PackagePage({ me, path }: { me: Me; path: string }) {
  if (!['admin', 'manager'].includes(me.user.role)) return <Result status="403" title="Không có quyền quản lý gói dịch vụ" />;
  const match = path.match(/^\/admin\/packages\/(?:new|(\d+)(\/edit)?)$/);
  if (!match) return <Result status="404" title="Không tìm thấy trang" />;
  if (path.endsWith('/new')) return <Editor key="new" id={null} />;
  return match[2] ? <Editor key={`edit-${match[1]}`} id={Number(match[1])} /> : <Detail id={Number(match[1])} />;
}
