import { useEffect, useMemo, useState } from 'react';
import { Alert, App, Button, Empty, Input, Modal, Select, Skeleton, Space, Tag } from 'antd';
import { api, ApiError, put } from '../../api';
import { dateTime, fold, packageChoices, quote, vnd } from './model';
import type { AdminService, AppointmentDetail, Treatment } from './model';

const image = (s: AdminService) => s.image_url || (s.anhdichvu ? `data:image/jpeg;base64,${s.anhdichvu}` : '/static/images/default-service.jpg');

/**
 * Keeps the time and staff; the server re-checks shift and overlaps with the new duration.
 * Package/gift sessions already reserved stay as they are; newly added services may use one.
 */
export function ChangeServices({ malh, canUseTreatments, services, onClose, onSaved }: { malh: number | null; canUseTreatments: boolean;
  services: AdminService[]; onClose: () => void; onSaved: () => void }) {
  const { message } = App.useApp();
  const [detail, setDetail] = useState<AppointmentDetail>();
  const [treatments, setTreatments] = useState<Treatment[]>([]);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<number[]>([]);
  const [packages, setPackages] = useState<Map<number, string>>(new Map());
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState('');
  useEffect(() => {
    let active = true;
    setDetail(undefined); setError(''); setSaveError(''); setSearch(''); setPackages(new Map()); setTreatments([]);
    if (malh === null) return;
    (async () => {
      try {
        const data = (await api<{ appointment: AppointmentDetail }>(`/api/admin/appointments/${malh}`)).appointment;
        if (!active) return;
        setDetail(data); setSelected(data.services.map(s => s.madv));
        if (canUseTreatments && data.khachhang) {
          const t = await api<{ treatments: Treatment[] }>(`/api/admin/appointments/customers/${data.khachhang.makh}/treatments`).catch(() => ({ treatments: [] }));
          if (active) setTreatments(t.treatments);
        }
      } catch (e) { if (active) setError((e as Error).message); }
    })();
    return () => { active = false; };
  }, [malh, canUseTreatments]);

  const current = useMemo(() => new Map((detail?.services || []).map(s => [s.madv, s])), [detail]);
  const catalogue = useMemo(() => services.filter(s => s.active !== false || current.has(s.madv)), [services, current]);
  const day = detail?.ngaygio.slice(0, 10) || '';
  const coveredBefore = new Set([...current.values()].filter(s => s.coverage).map(s => s.madv));
  const coveredAfter = new Set([...selected.filter(id => coveredBefore.has(id)), ...[...packages.keys()].filter(id => selected.includes(id))]);
  const start = detail?.ngaygio.slice(0, 16);
  const before = quote(catalogue, [...current.keys()], coveredBefore, start);
  const after = quote(catalogue, selected, coveredAfter, start);
  const changed = selected.length !== current.size || selected.some(id => !current.has(id)) || packages.size > 0;
  const tokens = fold(search).split(/\s+/).filter(Boolean);
  const visible = catalogue.filter(s => tokens.every(t => fold(`${s.tendv} ${s.mota || ''}`).includes(t)))
    .sort((a, b) => Number(selected.includes(b.madv)) - Number(selected.includes(a.madv)) || a.tendv.localeCompare(b.tendv, 'vi'));

  function toggle(id: number) {
    setSaveError('');
    setSelected(list => list.includes(id) ? list.filter(x => x !== id) : [...list, id]);
    setPackages(map => { if (!map.has(id)) return map; const next = new Map(map); next.delete(id); return next; });
  }
  async function save() {
    if (!malh || busy || !selected.length) return;
    setBusy(true); setSaveError('');
    const usages = [...packages].filter(([id]) => selected.includes(id)).map(([madv, value]) => {
      const [mathe, item] = value.split(':').map(Number);
      return { mathe, the_item_id: item, madv, quantity: 1 };
    });
    try {
      const result = await put<{ msg: string; end_time: string }>(`/api/admin/appointments/${malh}/services`, { madv_list: selected, package_usages: usages });
      message.success(`${result.msg}. Dự kiến kết thúc ${result.end_time}.`);
      onSaved(); onClose();
    } catch (e) {
      const err = e as ApiError;
      const conflicts = (err.data?.conflicts as { ngaygio?: string; ketthuc?: string; dichvu?: string }[] | undefined) || [];
      setSaveError(err.message + (conflicts.length ? ` Trùng: ${conflicts.map(c => `${c.ngaygio || ''}–${c.ketthuc || ''} ${c.dichvu || ''}`).join('; ')}` : ''));
    } finally { setBusy(false); }
  }

  return <Modal open={malh !== null} onCancel={() => { if (!busy) onClose(); }} width={760} destroyOnHidden maskClosable={!busy}
    title={malh !== null ? `Đổi dịch vụ – lịch #${malh}` : ''}
    footer={detail && <div className="cs-footer-react">
      <div className="cs-compare-react" aria-live="polite">
        <span>Trước <strong>{vnd(before.pay)}</strong><small>{before.minutes} phút{before.end ? ` · xong ${before.end}` : ''}</small></span>
        <span aria-hidden>→</span>
        <span>Sau <strong>{vnd(after.pay)}</strong><small>{after.minutes} phút{after.end ? ` · xong ${after.end}` : ''}</small></span>
        <span>Chênh lệch <strong>{after.pay - before.pay > 0 ? '+' : after.pay - before.pay < 0 ? '−' : ''}{vnd(Math.abs(after.pay - before.pay))}</strong>
          <small>{after.list !== after.pay ? `Giá gốc ${vnd(after.list)}, buổi gói trừ ${vnd(after.list - after.pay)}` : 'Số tiền thanh toán tại spa'}</small></span>
      </div>
      {saveError && <Alert type="error" showIcon message={saveError} style={{ textAlign: 'left', marginBottom: 12 }} />}
      {!selected.length && <Alert type="warning" showIcon message="Cần giữ ít nhất một dịch vụ." style={{ textAlign: 'left', marginBottom: 12 }} />}
      <Space><Button onClick={onClose} disabled={busy}>Quay lại</Button><Button type="primary" onClick={save} loading={busy} disabled={!selected.length || !changed}>Lưu thay đổi</Button></Space>
    </div>}>
    {error ? <Alert type="error" showIcon message={error} /> : !detail ? <Skeleton active /> : <>
      <p className="muted">{detail.khachhang?.hoten || 'Khách'} · {dateTime(detail.ngaygio)} · Nhân viên {detail.nhanvien?.hoten || 'chưa gán'}</p>
      <Space wrap className="cs-chips" aria-label="Dịch vụ đã chọn">{selected.map(id => {
        const s = catalogue.find(x => x.madv === id);
        return <Tag key={id} closable onClose={e => { e.preventDefault(); toggle(id); }} color={current.has(id) ? undefined : 'green'}>
          {s?.tendv || `#${id}`}{coveredAfter.has(id) ? ' · gói' : ''}</Tag>;
      })}</Space>
      <Input.Search className="section-title" allowClear placeholder="Tìm dịch vụ: tên, mô tả… (vd: da mun, massage)" aria-label="Tìm dịch vụ"
        value={search} onChange={e => setSearch(e.target.value)} />
      <p className="muted">{tokens.length ? `${visible.length} kết quả` : `${catalogue.length} dịch vụ`}</p>
      {!visible.length ? <Empty description={`Không tìm thấy dịch vụ phù hợp với “${search}”.`} /> : <div className="cs-grid-react" role="list">
        {visible.map(s => {
          const on = selected.includes(s.madv); const mine = current.get(s.madv);
          const options = mine ? [] : packageChoices(treatments, s.madv, day);
          return <div key={s.madv} role="listitem" className={`cs-card-react${on ? ' is-on' : ''}`}>
            <button type="button" data-toggle={s.madv} aria-pressed={on} onClick={() => toggle(s.madv)}>
              <img src={image(s)} alt="" loading="lazy" onError={e => { e.currentTarget.onerror = null; e.currentTarget.src = '/static/images/default-service.jpg'; }} />
              <span><strong>{s.tendv}</strong><small>{Number(s.thoiluong) || 60} phút · {vnd(s.gia)}</small>
                {mine && <Tag>{mine.coverage ? `${mine.coverage.source_type === 'gift' ? 'Quà tặng' : 'Buổi gói'}: ${mine.coverage.tengoi}` : 'Đang đặt'}</Tag>}
                {!mine && options.length > 0 && <Tag color="green">Có buổi gói</Tag>}</span>
              <span className="cs-check" aria-hidden>{on ? '✓' : '+'}</span>
            </button>
            {on && options.length > 0 && <Select size="small" aria-label={`Nguồn thanh toán cho ${s.tendv}`} value={packages.get(s.madv) || ''}
              onChange={v => setPackages(map => { const next = new Map(map); if (v) next.set(s.madv, v); else next.delete(s.madv); return next; })}
              options={[{ value: '', label: 'Thanh toán bình thường' }, ...options.map(o => ({ value: `${o.mathe}:${o.item.id}`,
                label: `${o.item.source_type === 'gift' ? 'Quà tặng' : 'Buổi gói'}: ${o.tengoi} — còn ${o.item.available_sessions}` }))]} />}
          </div>;
        })}
      </div>}
    </>}
  </Modal>;
}
