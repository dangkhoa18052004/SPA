import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, App, Button, Card, Checkbox, Drawer, Empty, Form, Input, Modal, Segmented, Select, Skeleton, Space, Tag } from 'antd';
import { api, ApiError, post } from '../../api';
import { dayLabel, findCreated, fold, packageChoices, quote, revalidate, spaToday, TIME_SLOTS, usagePayload, vnd } from './model';
import type { AdminService, AppointmentRow, Customer, PackageChoice, PackageSelection, Treatment } from './model';

type Staff = { manv: number; hoten: string; chuyenmon: string | null; appointment_count: number };
type Conflict = { ngaygio?: string; ketthuc?: string; dichvu?: string; khachhang?: string };
type Pending = { before: number[]; customer: number; start: string };

export function QuickCustomer({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (makh: number, existed: boolean) => void }) {
  const [form] = Form.useForm<{ hoten: string; sdt: string }>();
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  async function save(values: { hoten: string; sdt: string }) {
    setBusy(true);
    try {
      // The server returns the existing customer for a known phone number instead of a duplicate.
      const result = await post<{ msg: string; makh: number }>('/api/admin/customers/add-quick', { hoten: values.hoten.trim(), sdt: values.sdt.trim() });
      const existed = result.msg.includes('đã tồn tại');
      message[existed ? 'info' : 'success'](existed ? 'Số điện thoại đã có hồ sơ khách — đã chọn khách này.' : result.msg);
      form.resetFields(); onCreated(result.makh, existed);
    } catch (e) { message.error((e as Error).message); } finally { setBusy(false); }
  }
  return <Modal open={open} title="Thêm nhanh khách vãng lai" onCancel={() => { if (!busy) onClose(); }} footer={null} destroyOnHidden>
    <Form form={form} layout="vertical" onFinish={save} disabled={busy}>
      <Form.Item label="Họ tên" name="hoten" rules={[{ required: true, whitespace: true, message: 'Nhập họ tên' }, { max: 100 }]}><Input autoFocus /></Form.Item>
      <Form.Item label="Số điện thoại" name="sdt" rules={[{ required: true, message: 'Nhập số điện thoại' }, { pattern: /^[0-9+ ]{8,15}$/, message: 'Số điện thoại gồm 8–15 chữ số' }]}><Input inputMode="tel" /></Form.Item>
      <p className="muted">Tài khoản đăng nhập của khách là số điện thoại; khách có thể đổi mật khẩu sau.</p>
      <Space><Button onClick={onClose} disabled={busy}>Hủy</Button><Button type="primary" htmlType="submit" loading={busy}>Lưu khách hàng</Button></Space>
    </Form>
  </Modal>;
}

function TreatmentPicker({ treatments, state, error, day, selection, onToggle, onRetry }: { treatments: Treatment[]; state: 'loading' | 'ready' | 'error';
  error: string; day: string; selection: PackageSelection; onToggle: (choice: PackageChoice) => void; onRetry: () => void }) {
  if (state === 'loading') return <Skeleton active paragraph={{ rows: 2 }} />;
  if (state === 'error') return <Alert type="error" showIcon message={error} action={<Button onClick={onRetry}>Thử tải lại</Button>} />;
  const usable = (madv: number, id: number) => packageChoices(treatments, madv, day).find(c => c.item.id === id);
  if (!treatments.some(t => t.items.some(i => usable(i.madv, i.id)))) return <Alert type="info" showIcon message="Khách hiện chưa có gói/liệu trình khả dụng vào ngày đã chọn." />;
  return <div className="booking-treatments">{treatments.map(t => <Card size="small" key={t.mathe} title={`${t.tengoi} · #${t.mathe}`}>
    {t.items.map(i => {
      const choice = usable(i.madv, i.id);
      const reason = i.available_sessions <= 0 ? 'Đã hết lượt' : !choice ? 'Không còn hiệu lực vào ngày đã chọn' : '';
      const expiry = i.effective_expires_at ? dayLabel(i.effective_expires_at) : 'Không giới hạn';
      return <Checkbox key={i.id} className="booking-treatment-item" disabled={!choice} checked={selection.get(i.madv)?.item.id === i.id}
        onChange={() => choice && onToggle(choice)} aria-label={`${i.tendv} · ${i.source_type === 'gift' ? 'Spa tặng' : 'Trong gói'} · ${t.tengoi}`}>
        <strong>{i.tendv}</strong> <Tag color={i.source_type === 'gift' ? 'magenta' : 'green'}>{i.source_type === 'gift' ? 'Spa tặng' : 'Trong gói'}</Tag>
        <small className="muted">Còn {i.available_sessions}/{i.total_sessions ?? '—'} buổi · Đã dùng {i.consumed ?? 0} · Đang giữ {i.reserved ?? 0} · Hạn {expiry}
          {i.valid_from ? ` · Từ ${dayLabel(i.valid_from)}` : ''}{i.gifted_by_name ? ` · Người tặng: ${i.gifted_by_name}` : ''}{reason ? ` · ${reason}` : ''}</small>
        {i.gift_note && <small className="muted">{i.gift_note}</small>}
      </Checkbox>;
    })}
  </Card>)}</div>;
}

/**
 * Creates one appointment for a customer at the desk. Exactly one entitlement per package service;
 * the server re-validates sessions, shift, overlaps and staff. A lost response is reconciled
 * against the day's bookings before another submit is allowed, so the desk never double-books.
 */
export function BookingDrawer({ open, services, initialCustomer, onClose, onCreated }: { open: boolean; services: AdminService[];
  initialCustomer?: number | null; onClose: () => void; onCreated: (malh: number) => void }) {
  const { message, modal } = App.useApp();
  const today = spaToday();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customersError, setCustomersError] = useState('');
  const [customer, setCustomer] = useState<number | null>(null);
  const [quick, setQuick] = useState(false);
  const [method, setMethod] = useState<'regular' | 'treatment'>('regular');
  const [treatments, setTreatments] = useState<Treatment[]>([]);
  const [treatmentState, setTreatmentState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [treatmentError, setTreatmentError] = useState('');
  const [packages, setPackages] = useState<PackageSelection>(new Map());
  const [regular, setRegular] = useState<number[]>([]);
  const [day, setDay] = useState(today);
  const [time, setTime] = useState<string>();
  const [staff, setStaff] = useState<number | null>(null);
  const [available, setAvailable] = useState<Staff[]>();
  const [staffError, setStaffError] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const submitLock = useRef(false);
  const treatmentVersion = useRef(0);

  function reset() {
    setCustomer(initialCustomer ?? null); setMethod('regular'); setTreatments([]); setPackages(new Map()); setRegular([]); setDay(spaToday());
    setTime(undefined); setStaff(null); setAvailable(undefined); setNote(''); setError(''); setConflicts([]); setPending(null);
  }
  async function loadCustomers(select?: number) {
    try { const list = await api<Customer[]>('/api/admin/customers/list'); setCustomers(list); setCustomersError(''); if (select) setCustomer(select); }
    catch (e) { setCustomersError((e as Error).message); }
  }
  useEffect(() => { if (open) { reset(); void loadCustomers(); } }, [open]);

  async function loadTreatments(id: number) {
    const version = ++treatmentVersion.current;
    setTreatmentState('loading');
    try {
      const data = await api<{ treatments: Treatment[] }>(`/api/admin/appointments/customers/${id}/treatments`);
      if (version !== treatmentVersion.current) return null;
      setTreatments(data.treatments); setTreatmentState('ready'); return data.treatments;
    } catch (e) {
      if (version !== treatmentVersion.current) return null;
      setTreatments([]); setTreatmentState('error'); setTreatmentError((e as Error).message); setPackages(new Map()); return null;
    }
  }
  useEffect(() => {
    treatmentVersion.current++; setPackages(new Map()); setTreatments([]);
    if (customer !== null) void loadTreatments(customer); else setMethod('regular');
  }, [customer]);
  useEffect(() => {  // A new day can invalidate a package pick (expiry / valid-from).
    if (!packages.size) return;
    const { selection, removed } = revalidate(packages, treatments, day);
    if (removed.length) { setPackages(selection); message.warning('Có buổi gói không còn hiệu lực vào ngày đã chọn và đã được bỏ chọn.'); }
  }, [day, treatments]);

  const covered = useMemo(() => new Set(packages.keys()), [packages]);
  const selected = useMemo(() => [...new Set([...packages.keys(), ...regular.filter(id => !covered.has(id))])], [packages, regular, covered]);
  const start = time ? `${day}T${time}` : '';
  const price = quote(services, selected, covered, start || undefined);
  const nowTime = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());

  useEffect(() => {  // Staff free for the whole duration at the chosen start.
    setAvailable(undefined); setStaffError('');
    if (!start || !selected.length) return;
    let active = true;
    api<{ available_staff: Staff[] }>(`/api/admin/staff/available?${new URLSearchParams({ ngaygio: start, madv_list: selected.join(',') })}`)
      .then(r => { if (!active) return; setAvailable(r.available_staff); if (staff !== null && !r.available_staff.some(s => s.manv === staff)) setStaff(null); })
      .catch(e => { if (active) setStaffError((e as Error).message); });
    return () => { active = false; };
  }, [start, selected.join(',')]);

  const dirty = customer !== (initialCustomer ?? null) || selected.length > 0 || !!time || !!note.trim();
  function close() {
    if (busy) return;
    if (pending) { modal.confirm({ title: 'Chưa rõ lịch đã được tạo chưa', content: 'Hãy kiểm tra lịch đã tạo trước khi đóng để tránh đặt trùng.', okText: 'Vẫn đóng', cancelText: 'Ở lại', onOk: onClose }); return; }
    if (!dirty) { onClose(); return; }
    modal.confirm({ title: 'Bỏ lịch hẹn đang nhập?', okText: 'Bỏ', cancelText: 'Tiếp tục nhập', onOk: onClose });
  }
  async function dayBookings(c: number, d: string) {
    return api<AppointmentRow[]>(`/api/admin/appointments?${new URLSearchParams({ start_date: d, end_date: d, makh: String(c) })}`);
  }
  async function reconcile(marker = pending) {
    if (!marker) return;
    setBusy(true);
    try {
      const found = findCreated(marker.before, await dayBookings(marker.customer, marker.start.slice(0, 10)), marker.customer, marker.start);
      if (found) { setPending(null); message.success(`Lịch #${found.malh} đã được tạo trước đó — không cần gửi lại.`); onCreated(found.malh); }
      else { setPending(null); setError('Đã kiểm tra: lịch chưa được tạo. Bạn có thể lưu lại.'); }
    } catch { setError('Vẫn chưa kiểm tra được. Kiểm tra kết nối rồi bấm "Kiểm tra lịch đã tạo" lần nữa.'); }
    finally { setBusy(false); }
  }
  async function submit() {
    if (submitLock.current || pending) return;
    setError(''); setConflicts([]);
    if (customer === null) { setError('Vui lòng chọn khách hàng.'); return; }
    if (!selected.length) { setError('Vui lòng chọn ít nhất một dịch vụ.'); return; }
    if (!time) { setError('Vui lòng chọn giờ hẹn.'); return; }
    if (day === today && time <= nowTime) { setError('Giờ hẹn đã qua. Vui lòng chọn giờ khác.'); return; }
    submitLock.current = true; setBusy(true);
    let marker: Pending | null = null;
    try {
      marker = { before: (await dayBookings(customer, day)).map(r => r.malh), customer, start };
      const result = await post<{ malh: number; msg: string; appointment: { nhanvien: string | null; end_time: string } }>('/api/admin/appointments', {
        makh: customer, madv_list: selected, manv: staff, ngaygio: start, package_usages: usagePayload(packages), ghichu: note.trim() });
      message.success(`${result.msg} · Lịch #${result.malh}${result.appointment?.nhanvien ? ` · ${result.appointment.nhanvien}` : ''}`);
      onCreated(result.malh);
    } catch (e) {
      const err = e as ApiError;
      if (marker && (err.status === 0 || err.status >= 500)) {
        setPending(marker); setError('Chưa nhận được kết quả lưu lịch. Đang kiểm tra để tránh tạo trùng…');
        submitLock.current = false; setBusy(false); await reconcile(marker); return;
      }
      setError(err.message);
      setConflicts((err.data?.conflicts as Conflict[] | undefined) || []);
      if (packages.size && [400, 409].includes(err.status) && customer !== null) {
        const fresh = await loadTreatments(customer);
        if (fresh) { const { selection, removed } = revalidate(packages, fresh, day); setPackages(selection);
          if (removed.length) setError(`${err.message} Liệu trình vừa thay đổi; đã bỏ buổi không còn dùng được.`); }
      }
    } finally { submitLock.current = false; setBusy(false); }
  }

  const customerOptions = customers.map(c => ({ value: c.makh, label: `${c.hoten}${c.sdt ? ` · ${c.sdt}` : ''}`, search: fold(`${c.hoten} ${c.sdt || ''}`),
    disabled: c.trangthai === 'blocked' }));
  return <Drawer open={open} onClose={close} width={640} title="Tạo lịch hẹn" destroyOnHidden maskClosable={!busy}
    footer={<div className="booking-footer">
      <div className="booking-quote" aria-live="polite" data-testid="booking-quote">
        <span>{selected.length} dịch vụ · {price.minutes} phút{price.end ? ` · xong khoảng ${price.end}` : ''}</span>
        <strong>Thu tại spa: {vnd(price.pay)}</strong>{price.list !== price.pay && <small className="muted">Giá gốc {vnd(price.list)} · buổi gói/quà trừ {vnd(price.list - price.pay)}</small>}
      </div>
      <Space wrap><Button onClick={close} disabled={busy}>Hủy</Button>
        {pending ? <Button type="primary" loading={busy} onClick={() => reconcile()}>Kiểm tra lịch đã tạo</Button>
          : <Button type="primary" loading={busy} onClick={submit} data-testid="booking-save">Lưu lịch hẹn</Button>}</Space>
    </div>}>
    <Form layout="vertical" disabled={busy} onFinish={submit} className="booking-form">
      <Form.Item label="Khách hàng" required>
        {customersError ? <Alert type="error" showIcon message={customersError} action={<Button onClick={() => loadCustomers()}>Thử lại</Button>} />
          : <><Select showSearch aria-label="Khách hàng" placeholder="Tìm theo tên hoặc số điện thoại" value={customer ?? undefined}
            onChange={v => setCustomer(v ?? null)} allowClear options={customerOptions} optionFilterProp="label"
            filterOption={(input, option) => fold(input).split(/\s+/).every(t => option?.search.includes(t) ?? false)} notFoundContent="Không tìm thấy khách" style={{ width: '100%' }} />
            <Button type="link" className="booking-quick-add" onClick={() => setQuick(true)}>+ Thêm khách vãng lai</Button></>}
      </Form.Item>
      {customer !== null && <Form.Item label="Phương thức sử dụng dịch vụ">
        <Segmented block value={method} onChange={v => { setMethod(v as typeof method); if (v === 'regular') setPackages(new Map()); }}
          options={[{ value: 'regular', label: 'Dịch vụ thông thường' }, { value: 'treatment', label: 'Dùng gói / liệu trình' }]} />
      </Form.Item>}
      {customer !== null && method === 'treatment' && <Form.Item label="Liệu trình của khách" extra="Mỗi dịch vụ dùng đúng một nguồn. Có thể thêm dịch vụ thanh toán riêng bên dưới.">
        <TreatmentPicker treatments={treatments} state={treatmentState} error={treatmentError} day={day} selection={packages} onRetry={() => loadTreatments(customer)}
          onToggle={choice => setPackages(map => { const next = new Map(map);
            if (next.get(choice.item.madv)?.item.id === choice.item.id) next.delete(choice.item.madv); else next.set(choice.item.madv, choice);
            return next; })} />
      </Form.Item>}
      <Form.Item label={method === 'treatment' ? 'Dịch vụ mua thêm (thanh toán riêng, tùy chọn)' : 'Dịch vụ'} required={method !== 'treatment'}>
        <Select mode="multiple" aria-label="Dịch vụ" placeholder="Tìm dịch vụ" value={regular.filter(id => !covered.has(id))} onChange={setRegular}
          optionFilterProp="label" filterOption={(input, option) => fold(String(option?.label || '')).includes(fold(input))}
          options={services.filter(s => s.active !== false).map(s => ({ value: s.madv, label: `${s.tendv} · ${Number(s.thoiluong) || 60} phút · ${vnd(s.gia)}`, disabled: covered.has(s.madv) }))} />
        {packages.size > 0 && <Space wrap className="section-title">{[...packages.values()].map(p => <Tag key={p.item.madv} color="green" closable
          onClose={e => { e.preventDefault(); setPackages(map => { const next = new Map(map); next.delete(p.item.madv); return next; }); }}>
          {p.item.tendv} · {p.item.source_type === 'gift' ? 'Spa tặng' : 'Trong gói'} · {p.tengoi}</Tag>)}</Space>}
      </Form.Item>
      <div className="form-grid">
        <Form.Item label="Ngày" required><Input type="date" aria-label="Ngày hẹn" min={today} value={day} onChange={e => { setDay(e.target.value || today); setTime(undefined); }} /></Form.Item>
        <Form.Item label="Giờ" required><Select showSearch aria-label="Giờ hẹn" placeholder="Chọn giờ" value={time} onChange={setTime}
          options={TIME_SLOTS.map(t => ({ value: t, label: t, disabled: day === today && t <= nowTime }))} /></Form.Item>
      </div>
      <Form.Item label="Nhân viên" extra={!start || !selected.length ? 'Chọn dịch vụ, ngày và giờ để xem nhân viên rảnh.' : undefined}>
        {staffError ? <Alert type="error" showIcon message={staffError} /> : <Select aria-label="Nhân viên" allowClear placeholder="Tự động sắp xếp" value={staff ?? undefined}
          onChange={v => setStaff(v ?? null)} disabled={!available} loading={!!start && !!selected.length && !available}
          notFoundContent={<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Không có nhân viên rảnh vào giờ này" />}
          options={(available || []).map(s => ({ value: s.manv, label: `${s.hoten} · ${s.chuyenmon || 'Nhân viên'} · ${s.appointment_count} lịch trong ngày` }))} />}
        {available && !available.length && <Alert className="section-title" type="warning" showIcon message="Không có nhân viên rảnh vào giờ này. Chọn giờ khác." />}
      </Form.Item>
      <Form.Item label="Ghi chú"><Input.TextArea rows={3} maxLength={500} showCount value={note} onChange={e => setNote(e.target.value)} placeholder="Yêu cầu của khách (nếu có)" /></Form.Item>
      {error && <Alert role="alert" type={pending ? 'warning' : 'error'} showIcon message={error}
        description={conflicts.length ? <ul>{conflicts.map((c, i) => <li key={i}>{c.ngaygio} – {c.ketthuc}: {c.dichvu} ({c.khachhang})</li>)}</ul> : undefined} />}
    </Form>
    <QuickCustomer open={quick} onClose={() => setQuick(false)} onCreated={makh => { setQuick(false); void loadCustomers(makh); }} />
  </Drawer>;
}
