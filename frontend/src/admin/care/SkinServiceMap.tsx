import { useEffect, useRef, useState } from 'react';
import { Alert, App, Button, Card, Empty, List, Result, Select, Space, Tag } from 'antd';
import { api, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import type { Me } from '../../types';
import { utcDate } from './model';
import './care.css';

type Mapping = Record<string, number[]>;
type Service = { madv: number; tendv: string; category_name: string | null };
type Configuration = { schema_ready: boolean; source: 'database' | 'env' | 'empty'; map: Mapping;
  types: Record<string, string>; services: Service[]; approved_at: string | null; approved_by_name: string | null };
type Proposal = { assignments: { type_code: string; items: { service_id: number; reason: string }[] }[]; message: string | null };
type Saved = Pick<Configuration, 'schema_ready' | 'source' | 'map' | 'approved_at' | 'approved_by_name'>;

const canonical = (mapping: Mapping) => JSON.stringify(Object.keys(mapping).sort().map(code => [code, [...mapping[code]].sort((a, b) => a - b)]));
const editable = (data: Configuration): Mapping => Object.fromEntries(Object.keys(data.types).map(code => [code,
  (data.map[code] || []).filter(id => data.services.some(service => service.madv === id))]));
const sourceLabels = { database: 'Danh sách đã duyệt', env: 'Danh sách cấu hình ban đầu', empty: 'Chưa có dịch vụ được chọn' };

export default function SkinServiceMap({ me }: { me: Me }) {
  return ['admin', 'manager'].includes(me.user.role) ? <Editor /> : <Result status="403" title="Bạn không có quyền cấu hình dịch vụ theo loại mụn" extra={<Button href="/admin/dashboard">Về tổng quan</Button>} />;
}

function Editor() {
  const resource = useResource<Configuration>('/api/admin/skin-service-map');
  const [saved, setSaved] = useState<Configuration>();
  const [selection, setSelection] = useState<Mapping>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [proposed, setProposed] = useState(false);
  const [busy, setBusy] = useState<'proposal' | 'save' | null>(null);
  const [error, setError] = useState('');
  const inFlight = useRef(false), mounted = useRef(true);
  const { modal, message } = App.useApp();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (resource.data) { setSaved(resource.data); setSelection(editable(resource.data)); setReasons({}); setProposed(false); }
  }, [resource.data]);
  const dirty = !!saved && canonical(selection) !== canonical(editable(saved));
  const unavailable = !!busy || !saved?.schema_ready || resource.loading || !!resource.error;

  async function propose() {
    if (inFlight.current || !saved) return;
    const base = saved;
    inFlight.current = true; setBusy('proposal'); setError('');
    try {
      const result = await api<Proposal>('/api/admin/skin-service-map/proposal', { method: 'POST', body: '{}' }, false, 30000);
      if (!mounted.current) return;
      const next: Mapping = Object.fromEntries(Object.keys(base.types).map(code => [code, []]));
      const descriptions: Record<string, string> = {};
      for (const group of result.assignments) {
        if (!(group.type_code in next)) continue;
        for (const item of group.items) {
          if (!base.services.some(service => service.madv === item.service_id)) continue;
          if (!next[group.type_code].includes(item.service_id)) next[group.type_code].push(item.service_id);
          descriptions[`${group.type_code}:${item.service_id}`] = item.reason;
        }
      }
      setSelection(next); setReasons(descriptions); setProposed(true);
      if (result.message) message.info(result.message);
    } catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { inFlight.current = false; if (mounted.current) setBusy(null); }
  }

  function requestProposal() {
    if (dirty || proposed) modal.confirm({ title: 'Thay các lựa chọn chưa lưu bằng đề xuất mới?', content: 'Danh sách đã duyệt chưa thay đổi. Bạn có thể chỉnh lại đề xuất trước khi lưu.',
      okText: 'Lấy đề xuất mới', cancelText: 'Giữ lựa chọn', onOk: propose });
    else void propose();
  }

  function confirmSave() {
    if (!saved || inFlight.current) return;
    const base = saved;
    const mapping = Object.fromEntries(Object.keys(base.types).map(code => [code, [...(selection[code] || [])]]));
    const empty = !Object.values(mapping).some(ids => ids.length);
    modal.confirm({ title: 'Lưu và duyệt dịch vụ gợi ý?', okText: 'Lưu và duyệt', cancelText: 'Kiểm tra lại', autoFocusButton: 'cancel',
      content: <><ul>{Object.entries(base.types).map(([code, name]) => <li key={code}>{name}: {mapping[code].length} dịch vụ</li>)}</ul>
        {empty && <p>Danh sách trống sẽ dùng lại danh sách cấu hình ban đầu, nếu có. Khách chưa có dịch vụ phù hợp sẽ được hướng dẫn tư vấn trực tiếp.</p>}</>,
      onOk: async () => {
        if (inFlight.current) return;
        inFlight.current = true; setBusy('save'); setError('');
        try {
          const result = await put<Saved>('/api/admin/skin-service-map', { map: mapping });
          if (!mounted.current) return;
          const updated = { ...base, ...result };
          setSaved(updated); setSelection(editable(updated)); setReasons({}); setProposed(false);
          message.success(empty ? 'Đã duyệt danh sách trống.' : 'Đã lưu và duyệt dịch vụ gợi ý.');
        } catch (e) { if (mounted.current) setError((e as Error).message); }
        finally { inFlight.current = false; if (mounted.current) setBusy(null); }
      } });
  }

  function discard() {
    modal.confirm({ title: 'Bỏ các thay đổi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục chỉnh', onOk: () => {
      if (saved) setSelection(editable(saved)); setReasons({}); setProposed(false); setError('');
    } });
  }

  return <>
    <div className="page-heading"><h1>Dịch vụ theo loại mụn</h1><p>Chọn dịch vụ được phép gợi ý sau khi soi da. Khách chỉ thấy danh sách bạn đã lưu và duyệt.</p></div>
    <ResourceState {...resource} />
    {saved && !resource.error && !resource.loading && <>
      <Card className="care-section">
        <Space wrap><Tag color={saved.source === 'database' ? 'green' : 'default'}>{sourceLabels[saved.source]}</Tag>
          {saved.approved_at && <span>Duyệt lúc {utcDate(saved.approved_at)} · Người duyệt: {saved.approved_by_name || 'Không còn thông tin'}</span>}</Space>
        <p>Chọn tối đa 10 dịch vụ cho mỗi loại mụn. Gemini chỉ đưa đề xuất để bạn xem và chỉnh sửa trước khi duyệt.</p>
        {!saved.schema_ready && <Alert type="warning" showIcon message="Cấu hình gợi ý dịch vụ chưa được cập nhật trên hệ thống này. Cần cập nhật dữ liệu trước khi lưu và duyệt." />}
        {(proposed || dirty) && <Alert className="care-section" showIcon type="warning" message={proposed ? 'Đây là bản nháp đề xuất, chưa được lưu và duyệt.' : 'Bạn có thay đổi chưa lưu và duyệt.'} />}
        {error && <Alert className="care-section" type="error" showIcon message={error} description="Các lựa chọn vẫn được giữ. Hệ thống không tự gửi lại yêu cầu." />}
        <Space wrap className="care-section">
          <Button onClick={requestProposal} loading={busy === 'proposal'} disabled={unavailable}>Nhờ Gemini đề xuất</Button>
          <Button type="primary" onClick={confirmSave} loading={busy === 'save'} disabled={unavailable}>Lưu và duyệt</Button>
          <Button onClick={discard} disabled={unavailable || (!dirty && !proposed)}>Hủy thay đổi</Button>
        </Space>
      </Card>
      {!saved.services.length && <Empty className="care-section" description="Chưa có dịch vụ đang hoạt động để chọn." />}
      <div className="skin-map-cards care-section">{Object.entries(saved.types).map(([code, name]) => {
        const selected = selection[code] || [], approved = saved.map[code] || [];
        const removed = approved.filter(id => !selected.includes(id));
        return <Card key={code} title={<h2>{name}</h2>} extra={<Tag>{selected.length}/10</Tag>} data-testid={`skin-map-${code}`}>
          <Select mode="multiple" showSearch optionFilterProp="label" maxCount={10} style={{ width: '100%' }}
            aria-label={`Dịch vụ cho ${name}`} placeholder="Tìm và chọn dịch vụ" value={selected} disabled={unavailable}
            options={saved.services.map(service => ({ value: service.madv, label: service.tendv }))}
            onChange={ids => setSelection(previous => ({ ...previous, [code]: ids }))} />
          {selected.length ? <List dataSource={selected} renderItem={id => {
            const service = saved.services.find(row => row.madv === id);
            return <List.Item><div><strong>{service?.tendv}</strong>{!approved.includes(id) && <Tag color="blue">Thêm mới</Tag>}
              {service?.category_name && <p>{service.category_name}</p>}{reasons[`${code}:${id}`] && <p className="care-text">{reasons[`${code}:${id}`]}</p>}</div></List.Item>;
          }} /> : <p className="care-text">Chưa chọn dịch vụ cho nhóm này.</p>}
          {!!removed.length && <div className="care-section"><p>Sẽ bỏ khi lưu:</p>{removed.map(id => <Tag key={id} color="orange">{saved.services.find(service => service.madv === id)?.tendv || `Dịch vụ #${id} không còn hoạt động`}</Tag>)}</div>}
        </Card>;
      })}</div>
    </>}
  </>;
}
