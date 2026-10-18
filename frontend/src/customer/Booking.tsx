import { useEffect, useRef, useState } from 'react';
import { Button, Card, Input, cn, selectClass } from './ui';
import { customerApi, customerPost, CustomerApiError } from './api';
import { availableBookingSlots, choices, initialSelection, isFutureBookingTime, localDate, money, subtotal } from './booking-model';
import type { Booking, Service, Slots, Staff, Treatment, Usage } from './booking-model';

type Catalogue = { services: Service[]; treatments: Treatment[]; vietqr: boolean };
type Pending = { before: number[]; start: string; services: number[]; customer: string };
type OwnBooking = Booking & { services: { madv: number }[] };
const pendingKey = 'binspa.pending-booking';
const servicesPerPage = 6;
const servicePlaceholder = '/static/images/default-service.jpg';
const readPending = (): Pending | null => { try { return JSON.parse(sessionStorage.getItem(pendingKey) || 'null'); } catch { return null; } };
const customerKey = () => {
  try { return JSON.parse(atob(window.CustomerAuth.getAccessToken()!.split('.')[1])).sub as string; } catch { return ''; }
};
function Notice({ children, retry }: { children: React.ReactNode; retry?: () => void }) {
  return <div role="alert" className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"><p>{children}</p>{retry && <Button variant="outline" className="mt-3" onClick={retry}>Thử lại</Button>}</div>;
}
function useCustomerResource<T>(path: string, body?: unknown) {
  const bodyKey = JSON.stringify(body);
  const [state, setState] = useState<{ data?: T; loading: boolean; error: string }>({ loading: true, error: '' });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setState({ loading: true, error: '' });
    (bodyKey ? customerPost<T>(path, JSON.parse(bodyKey)) : customerApi<T>(path)).then(data => { if (active) setState({ data, loading: false, error: '' }); })
      .catch(e => { if (active) setState({ loading: false, error: e.message }); });
    return () => { active = false; };
  }, [path, bodyKey, revision]);
  return { ...state, reload: () => setRevision(n => n + 1) };
}

function TimeSelection({ selected, date, setDate, time, setTime, staff, setStaff, disabled }: {
  selected: number[]; date: string; setDate: (v: string) => void; time: string; setTime: (v: string) => void; staff: number | null; setStaff: (v: number | null) => void; disabled: boolean }) {
  const resource = useCustomerResource<Slots>(`/api/appointments/available-slots?${new URLSearchParams({ date, madv_list: selected.join(','), suggest: '1' })}`);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = window.setInterval(update, 30_000);
    window.addEventListener('focus', update);
    document.addEventListener('visibilitychange', update);
    return () => { window.clearInterval(timer); window.removeEventListener('focus', update); document.removeEventListener('visibilitychange', update); };
  }, []);
  const slots = availableBookingSlots(resource.data?.slots || [], date, now);
  const suggestions = resource.data?.suggestions?.filter(s => isFutureBookingTime(s.date, s.time, now)) || [];
  useEffect(() => {
    if (time && resource.data && !resource.loading && !resource.error && !slots.some(s => s.time === time)) setTime('');
  }, [time, resource.data, resource.loading, resource.error, date, now, setTime]);
  return <><h2 className="mb-2 text-xl font-semibold">Chọn ngày và giờ</h2><p className="mb-6 text-sm text-muted-foreground">Khung giờ trống được cập nhật theo tổng thời lượng dịch vụ.</p>
    <label className="mb-5 block font-medium">Ngày hẹn<Input disabled={disabled} data-testid="booking-date" className="mt-2 max-w-sm" type="date" min={localDate()} value={date} required onChange={e => { if (e.target.value) setDate(e.target.value); }} /></label>
    {resource.loading ? <p role="status">Đang tìm giờ trống…</p> : resource.error ? <Notice retry={resource.reload}>{resource.error}</Notice> : <>
      <div className="mb-5 grid grid-cols-3 gap-2 sm:grid-cols-5" role="group" aria-label="Giờ hẹn">
        {slots.map(slot => <Button key={slot.time} data-slot={slot.time} variant={time === slot.time ? 'default' : 'outline'} aria-pressed={time === slot.time} disabled={disabled} onClick={() => setTime(slot.time)}>{slot.time}</Button>)}
      </div>
      {!slots.length && <Notice>Ngày này không còn giờ trống phù hợp. Vui lòng chọn ngày khác.</Notice>}
      {!!suggestions.length && <div className="mb-6"><h3 className="mb-2 font-medium">Thời gian khác còn trống</h3><div className="flex flex-wrap gap-2">{suggestions.map(s => <Button disabled={disabled} variant="outline" key={`${s.date}-${s.time}`} onClick={() => setDate(s.date)}>{s.date.split('-').reverse().join('/')} · {s.time}</Button>)}</div></div>}
    </>}
    {time && !resource.loading && !resource.error && slots.some(s => s.time === time) && <StaffSelection disabled={disabled} selected={selected} start={`${date}T${time}`} staff={staff} setStaff={setStaff} />}
  </>;
}
function StaffSelection({ selected, start, staff, setStaff, disabled }: { selected: number[]; start: string; staff: number | null; setStaff: (v: number | null) => void; disabled: boolean }) {
  const resource = useCustomerResource<{ staff: Staff[] }>('/api/appointments/available-staff', { madv_list: selected, ngaygio: start });
  return <section className="mt-7 border-t border-border pt-6"><h2 className="mb-3 text-lg font-semibold">Nhân viên phục vụ</h2>
    <label className="mb-4 flex min-h-11 items-center gap-3"><input disabled={disabled} type="radio" name="staff" checked={staff === null} onChange={() => setStaff(null)} />Để spa sắp xếp nhân viên phù hợp</label>
    {resource.loading ? <p role="status">Đang kiểm tra nhân viên…</p> : resource.error ? <Notice retry={resource.reload}>{resource.error}</Notice> : <div className="grid gap-3 sm:grid-cols-2">
      {resource.data?.staff.map(s => <label className={cn('flex items-center gap-3 rounded-xl border p-4', !s.available && 'opacity-60', s.manv === staff ? 'border-primary bg-secondary' : 'border-border')} key={s.manv}>
        <input type="radio" name="staff" disabled={disabled || !s.available} checked={s.manv === staff} onChange={() => setStaff(s.manv)} /><span><strong className="block">{s.hoten}</strong><small>{s.available ? s.chucvu : s.message}</small></span></label>)}
    </div>}
  </section>;
}

export default function BookingPage() {
  const [catalogue, setCatalogue] = useState<Catalogue>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [usages, setUsages] = useState<Usage[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [servicePage, setServicePage] = useState(1);
  const [date, setDate] = useState(localDate());
  const [time, setTime] = useState('');
  const [staff, setStaff] = useState<number | null>(null);
  const [staffName, setStaffName] = useState('Spa sắp xếp');
  const [payment, setPayment] = useState('at_spa');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const submitLock = useRef(false);
  const [result, setResult] = useState<Booking>();
  const [pending, setPending] = useState<Pending | null>(readPending);
  const [notice, setNotice] = useState('');
  const heading = useRef<HTMLDivElement>(null);
  const serviceList = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  useEffect(() => { heading.current?.focus(); }, [step]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    (async () => {
      const token = await window.CustomerAuth.restoreAccessToken();
      if (!active) return;
      if (!token) { setGuest(true); setLoading(false); return; }
      const [services, treatments, options] = await Promise.all([
        customerApi<{ services: Service[] }>('/api/services'), customerApi<{ treatments: Treatment[] }>('/api/packages/my-treatments'),
        customerApi<{ vietqr_available: boolean }>('/api/packages/payment-options')]);
      if (!active) return;
      setCatalogue({ services: services.services, treatments: treatments.treatments, vietqr: options.vietqr_available });
      if (!initialized.current) {
        const initial = initialSelection(location.search, services.services, treatments.treatments, date);
        setSelected(initial.selected); setUsages(initial.usages);
        if (initial.invalidEntitlement) setNotice('Thông tin trong liên kết chưa dùng được. Hãy kiểm tra gói và chọn dịch vụ, hình thức sử dụng bên dưới.');
        const existing = readPending();
        if (existing && existing.customer !== customerKey()) { sessionStorage.removeItem(pendingKey); setPending(null); }
        initialized.current = true;
      }
    })().catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  const picked = catalogue?.services.filter(s => selected.includes(s.madv)) || [];
  const amount = subtotal(picked, usages);
  const duration = picked.reduce((sum, s) => sum + (s.thoiluong || 60), 0);
  const invalidUsages = catalogue ? usages.some(u => !choices(catalogue.treatments, u.madv, date).some(c => c.item.id === u.the_item_id)) : false;
  function changeDate(v: string) { setDate(v); setTime(''); setStaff(null); setStaffName('Spa sắp xếp'); }
  function changeServicePage(page: number) {
    setServicePage(page);
    window.requestAnimationFrame(() => {
      serviceList.current?.focus({ preventScroll: true });
      serviceList.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }
  function toggleService(id: number) {
    if (!selected.includes(id)) void window.CustomerRecommendations?.track('select_service', { madv: id });
    setSelected(prev => prev.includes(id) ? prev.filter(v => v !== id) : [...prev, id]);
    setUsages(prev => prev.filter(u => u.madv !== id)); setTime(''); setStaff(null);
  }
  async function continueToReview() {
    if (!time || !picked.length || invalidUsages) return;
    setBusy(true); setError('');
    try {
      const slots = await customerApi<Slots>(`/api/appointments/available-slots?${new URLSearchParams({ date, madv_list: selected.join(',') })}`);
      if (!availableBookingSlots(slots.slots, date).some(s => s.time === time)) { setTime(''); throw new Error('Giờ vừa chọn không còn trống. Vui lòng chọn giờ khác.'); }
      const people = await customerPost<{ staff: Staff[] }>('/api/appointments/available-staff', { ngaygio: `${date}T${time}`, madv_list: selected });
      const person = people.staff.find(s => s.manv === staff && s.available);
      if (staff !== null && !person) { setStaff(null); throw new Error('Nhân viên này vừa có lịch khác. Vui lòng chọn lại nhân viên.'); }
      setStaffName(person?.hoten || 'Spa sắp xếp'); setStep(3);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function reconcile() {
    if (!pending) return;
    setBusy(true); setError('');
    try {
      const own = await customerApi<{ appointments: OwnBooking[] }>('/api/appointments/my-appointments');
      const found = own.appointments.find(a => !pending.before.includes(a.malh) && a.ngaygio.slice(0, 16) === pending.start
        && a.services.map(s => s.madv).sort().join(',') === [...pending.services].sort().join(','));
      if (found) { setResult({ ...found, invoice_id: (found as OwnBooking & { invoice?: { mahd: number } }).invoice?.mahd || null }); sessionStorage.removeItem(pendingKey); setPending(null); }
      else setError('Chưa tìm thấy lịch mới. Hãy kiểm tra mục Lịch hẹn của tôi hoặc liên hệ spa trước khi đặt lại.');
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function submit() {
    if (submitLock.current || pending || !picked.length || !time || invalidUsages) return;
    submitLock.current = true; setBusy(true); setError('');
    let sent = false;
    try {
      // Snapshot before POST allows safe reconciliation if the response is lost.
      const own = await customerApi<{ appointments: OwnBooking[] }>('/api/appointments/my-appointments');
      const marker: Pending = { before: own.appointments.map(a => a.malh), start: `${date}T${time}`, services: selected, customer: customerKey() };
      sessionStorage.setItem(pendingKey, JSON.stringify(marker));
      sent = true;
      const response = await customerPost<{ appointment: Booking }>('/api/appointments/create', { madv_list: selected, package_usages: usages, ngaygio: marker.start,
        manv: staff, ghichu: note.trim(), payment_option: amount > 0 ? payment : 'at_spa' });
      sessionStorage.removeItem(pendingKey); setPending(null); setResult(response.appointment);
      if (response.appointment.invoice_id) {
        try { await window.LoyaltyPayment.openCustomerInvoice(response.appointment.invoice_id); }
        catch { setNotice('Chưa mở được thanh toán. Bạn có thể tiếp tục ở Hóa đơn của tôi.'); }
      }
    } catch (e) {
      const uncertain = sent && (!(e instanceof CustomerApiError) || e.status === 0 || e.status >= 500);
      if (uncertain) { setPending(readPending()); setError('Chưa nhận được kết quả đặt lịch. Kiểm tra lịch đã đặt trước khi gửi lại để tránh đặt trùng.'); }
      else { sessionStorage.removeItem(pendingKey); setError((e as Error).message); if (sent) { setStep(2); setTime(''); } }
    } finally { setBusy(false); submitLock.current = false; }
  }
  if (loading) return <Card><p role="status" className="animate-pulse">Đang tải dịch vụ và liệu trình…</p></Card>;
  if (guest) return <Card className="mx-auto max-w-xl text-center"><h2 className="mb-3 text-xl font-semibold">Đăng nhập để đặt lịch</h2><p className="mb-6 text-muted-foreground">Xem liệu trình hiện có và lưu lịch hẹn vào tài khoản của bạn.</p><Button asChild><a href={`/auth/login?redirect=${encodeURIComponent(location.pathname + location.search)}`}>Đăng nhập / Đăng ký</a></Button></Card>;
  if (!catalogue) return <Notice retry={() => setRevision(n => n + 1)}>{error || 'Chưa tải được danh sách dịch vụ.'}</Notice>;
  if (result) return <Card className="mx-auto max-w-2xl" data-testid="booking-success"><p className="mb-2 text-sm font-semibold text-primary">ĐÃ ĐẶT LỊCH</p><h2 className="mb-5 text-2xl font-semibold">Hẹn gặp bạn tại Bin Spa</h2>
    <p className="mb-3">Lịch hẹn #{result.malh} · {result.ngaygio.slice(0, 10).split('-').reverse().join('/')} lúc {result.ngaygio.slice(11, 16)}</p><p className="mb-6 text-muted-foreground">Nhân viên: {result.nhanvien || 'Spa sắp xếp'}. Vui lòng đến trước 10 phút. Bạn có thể theo dõi xác nhận của spa ở lịch hẹn của mình.</p>
    {notice && <Notice>{notice}</Notice>}<div className="flex flex-wrap gap-3"><Button asChild><a href="/profile#appointments">Xem lịch hẹn của tôi</a></Button>{result.invoice_id && <Button variant="outline" onClick={() => window.LoyaltyPayment.openCustomerInvoice(result.invoice_id!).catch(e => setNotice(e.message))}>Tiếp tục thanh toán</Button>}</div></Card>;
  if (pending) return <Card className="mx-auto max-w-xl"><h2 className="mb-4 text-xl font-semibold">Kiểm tra kết quả đặt lịch</h2><Notice>{error || 'Lần đặt lịch trước chưa nhận được phản hồi. Kiểm tra lịch để tránh đặt trùng.'}</Notice><div className="flex flex-wrap gap-3"><Button disabled={busy} onClick={reconcile}>{busy ? 'Đang kiểm tra…' : 'Kiểm tra lịch đã đặt'}</Button><Button asChild variant="outline"><a href="/profile#appointments">Lịch hẹn của tôi</a></Button></div></Card>;
  const filtered = catalogue.services.filter(s => (!category || s.category_name === category) && s.tendv.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')));
  const pageCount = Math.max(1, Math.ceil(filtered.length / servicesPerPage));
  const currentPage = Math.min(servicePage, pageCount);
  const pageStart = (currentPage - 1) * servicesPerPage;
  const visibleServices = filtered.slice(pageStart, pageStart + servicesPerPage);
  const context = catalogue.treatments.find(t => t.mathe === Number(new URLSearchParams(location.search).get('treatment')));
  return <div className="booking-grid"><section className="min-w-0"><div ref={heading} tabIndex={-1} className="mb-6 flex gap-2 outline-none" aria-label={`Bước ${step} trên 3`}>
    {['Dịch vụ', 'Thời gian', 'Xác nhận'].map((label, i) => <button key={label} disabled={i + 1 > step || busy} onClick={() => { setError(''); setStep(i + 1); }} aria-current={step === i + 1 ? 'step' : undefined} className={cn('flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl px-2 text-sm font-medium', step === i + 1 ? 'bg-primary text-white' : 'bg-secondary text-muted-foreground')}><span className="hidden sm:inline">{i + 1}.</span>{label}</button>)}
  </div>
  {notice && <Notice>{notice}</Notice>}{error && <Notice>{error}</Notice>}
  {invalidUsages && <Notice>Ngày hẹn nằm ngoài hạn dùng lượt gói đã chọn. Quay lại Dịch vụ để chọn lại lượt hoặc thanh toán bình thường.</Notice>}
  <Card>
    {step === 1 && <><h2 className="mb-2 text-xl font-semibold">Bạn muốn chăm sóc gì?</h2><p className="mb-5 text-sm text-muted-foreground">Có thể chọn nhiều dịch vụ và sử dụng buổi liệu trình hoặc quà tặng.</p>
      {context && <section className="mb-5 rounded-xl bg-secondary p-4"><h3 className="mb-3 font-medium">Liệu trình đang chọn: {context.tengoi}</h3><div className="flex flex-wrap gap-2">{catalogue.services.flatMap(s => choices([context], s.madv, date)).map(c => <Button key={c.item.id} variant="outline" onClick={() => {
        setSelected(prev => prev.includes(c.item.madv) ? prev : [...prev, c.item.madv]);
        setUsages(prev => [...prev.filter(u => u.madv !== c.item.madv), { mathe: c.treatment.mathe, the_item_id: c.item.id, madv: c.item.madv, quantity: 1 }]);
        setTime(''); setStaff(null);
      }}>{c.item.source_type === 'gift' ? 'Quà tặng' : 'Dùng 1 buổi'} · {c.item.tendv}</Button>)}</div></section>}
      <div className="mb-5 grid gap-3 sm:grid-cols-2"><Input aria-label="Tìm dịch vụ" placeholder="Tìm dịch vụ…" value={search} onChange={e => { setSearch(e.target.value); setServicePage(1); }} /><select aria-label="Nhóm dịch vụ" className={selectClass} value={category} onChange={e => { setCategory(e.target.value); setServicePage(1); }}><option value="">Tất cả nhóm dịch vụ</option>{[...new Set(catalogue.services.map(s => s.category_name).filter(Boolean))].map(c => <option key={c!}>{c}</option>)}</select></div>
      <div className="grid scroll-mt-5 gap-4 outline-none sm:grid-cols-2" id="booking-service-list" ref={serviceList} tabIndex={-1} role="group" aria-label="Danh sách dịch vụ">{visibleServices.map(s => <article key={s.madv} className={cn('booking-service-card overflow-hidden rounded-xl border', selected.includes(s.madv) ? 'border-primary bg-secondary/50' : 'border-border')}>
        <button type="button" data-service-id={s.madv} className="block w-full text-left" aria-pressed={selected.includes(s.madv)} onClick={() => toggleService(s.madv)}>
          <img className="booking-service-image" src={s.anhdichvu ? (s.anhdichvu.startsWith('data:image/') ? s.anhdichvu : `data:image/jpeg;base64,${s.anhdichvu}`) : servicePlaceholder} alt="" loading="lazy" onError={e => { if (!e.currentTarget.src.endsWith(servicePlaceholder)) e.currentTarget.src = servicePlaceholder; }} />
          <span className="block p-4 pb-0"><span className="mb-2 flex items-start justify-between gap-3"><strong>{s.tendv}</strong><span aria-hidden="true" className="booking-service-check">{selected.includes(s.madv) ? '✓' : '+'}</span></span><span className="block text-sm text-muted-foreground">{s.thoiluong || 60} phút</span><span className="mt-2 block font-semibold text-primary">{money(s.gia)}</span><span className="mt-3 block text-sm font-medium text-primary">{selected.includes(s.madv) ? 'Đã chọn · Bấm để bỏ chọn' : 'Chọn dịch vụ'}</span></span>
        </button>
        <a className="mx-4 mb-2 inline-flex min-h-11 items-center text-sm text-primary underline" href={`/services/${s.madv}`} target="_blank" rel="noopener">Chi tiết dịch vụ</a>
      </article>)}</div>{!filtered.length && <p className="py-8 text-center text-muted-foreground">Chưa có dịch vụ phù hợp.</p>}
      {!!filtered.length && <div className="mt-5 border-t border-border pt-4"><p className="mb-3 text-sm text-muted-foreground" role="status">Hiển thị {pageStart + 1}–{Math.min(pageStart + servicesPerPage, filtered.length)} / {filtered.length} dịch vụ</p>
        {pageCount > 1 && <nav className="flex flex-wrap items-center justify-between gap-2" aria-label="Phân trang dịch vụ"><Button variant="outline" aria-controls="booking-service-list" aria-label="Trang dịch vụ trước" disabled={currentPage === 1} onClick={() => changeServicePage(currentPage - 1)}>← Trước</Button><span className="text-sm" aria-live="polite">Trang {currentPage} / {pageCount}</span><Button variant="outline" aria-controls="booking-service-list" aria-label="Trang dịch vụ sau" disabled={currentPage === pageCount} onClick={() => changeServicePage(currentPage + 1)}>Sau →</Button></nav>}
      </div>}
      {!!picked.length && <section className="mt-6 border-t border-border pt-5"><h3 className="mb-3 font-semibold">Dịch vụ đã chọn & lượt liệu trình</h3>{picked.map(s => {
        const available = choices(catalogue.treatments, s.madv, date);
        const usage = usages.find(u => u.madv === s.madv);
        return <label key={s.madv} className="mb-4 block text-sm font-medium">{s.tendv}<select data-treatment-service={s.madv} className={cn(selectClass, 'mt-2')} value={usage?.the_item_id || ''} onChange={e => {
          const choice = available.find(c => c.item.id === Number(e.target.value));
          setUsages(prev => [...prev.filter(u => u.madv !== s.madv), ...(choice ? [{ mathe: choice.treatment.mathe, the_item_id: choice.item.id, madv: s.madv, quantity: 1 as const }] : [])]);
        }}><option value="">Thanh toán bình thường · {money(s.gia)}</option>{usage && !available.some(c => c.item.id === usage.the_item_id) && <option value={usage.the_item_id} disabled>Lượt đã chọn không dùng được vào ngày hẹn</option>}
          {available.map(c => <option key={c.item.id} value={c.item.id}>{c.item.source_type === 'gift' ? 'Quà tặng' : 'Dùng 1 buổi'} · {c.treatment.tengoi} · còn {c.item.available_sessions} buổi</option>)}</select></label>;
      })}</section>}
    </>}
    {step === 2 && <TimeSelection disabled={busy} selected={selected} date={date} setDate={changeDate} time={time} setTime={v => { setTime(v); setStaff(null); }} staff={staff} setStaff={setStaff} />}
    {step === 3 && <><h2 className="mb-5 text-xl font-semibold">Kiểm tra trước khi đặt</h2><div data-testid="booking-recap" className="mb-6 rounded-xl bg-secondary p-5"><strong className="block">{date.split('-').reverse().join('/')} · {time}</strong><p className="mt-2">{staffName} · {duration} phút</p><ul className="my-4 space-y-3">{picked.map(s => <li key={s.madv} className="flex justify-between gap-3"><span>{s.tendv}<small className="block text-muted-foreground">{usages.some(u => u.madv === s.madv) ? 'Dùng 1 buổi gói / quà tặng' : 'Thanh toán dịch vụ'}</small></span><b className="whitespace-nowrap">{money(usages.some(u => u.madv === s.madv) ? 0 : s.gia)}</b></li>)}</ul><div className="flex justify-between border-t border-border pt-3 font-semibold"><span>Còn phải trả</span><span>{money(amount)}</span></div></div>
      <label className="mb-6 block font-medium">Ghi chú cho spa<textarea disabled={busy} className={cn(selectClass, 'mt-2 min-h-24')} value={note} maxLength={2000} placeholder="Ví dụ: cần tư vấn trước khi làm dịch vụ…" onChange={e => setNote(e.target.value)} /></label>
      {amount > 0 ? <fieldset disabled={busy}><legend className="mb-3 font-semibold">Thanh toán</legend><label className="mb-3 flex min-h-11 items-center gap-3 rounded-xl border border-border p-4"><input type="radio" name="payment" value="at_spa" checked={payment === 'at_spa'} onChange={e => setPayment(e.target.value)} /><span>Thanh toán tại spa<small className="block text-muted-foreground">Thanh toán sau khi sử dụng dịch vụ.</small></span></label>
        <label className={cn('flex min-h-11 items-center gap-3 rounded-xl border border-border p-4', !catalogue.vietqr && 'opacity-60')}><input data-testid="booking-prepay" type="radio" name="payment" value="prepay" checked={payment === 'prepay'} disabled={!catalogue.vietqr} onChange={e => setPayment(e.target.value)} /><span>Thanh toán ngay bằng VietQR<small className="block text-muted-foreground">{catalogue.vietqr ? 'Áp dụng điểm / voucher và quét mã sau khi đặt lịch.' : 'VietQR tạm thời chưa khả dụng.'}</small></span></label></fieldset> : <p className="text-sm text-primary">Toàn bộ dịch vụ dùng lượt gói / quà tặng. Không cần thanh toán thêm.</p>}
      <p className="mt-6 text-sm text-muted-foreground">Spa sẽ xác nhận lịch hẹn. Vui lòng đến trước 10 phút để chuẩn bị.</p>
    </>}
    <div className="booking-actions mt-7 flex flex-wrap justify-between gap-3 border-t border-border pt-5">
      {step > 1 ? <Button variant="outline" disabled={busy} onClick={() => { setError(''); setStep(step - 1); }}>Quay lại</Button> : <span />}
      {step === 1 && <Button data-testid="booking-next" disabled={!picked.length || invalidUsages || busy} onClick={() => { setError(''); setStep(2); }}>Chọn thời gian</Button>}
      {step === 2 && <Button data-testid="booking-next" disabled={!time || invalidUsages || busy} onClick={continueToReview}>{busy ? 'Đang kiểm tra…' : 'Kiểm tra lịch hẹn'}</Button>}
      {step === 3 && <Button data-testid="booking-submit" disabled={busy || invalidUsages} onClick={submit}>{busy ? 'Đang đặt lịch…' : 'Xác nhận đặt lịch'}</Button>}
    </div>
  </Card></section>
  <aside className="booking-summary"><Card><h2 className="mb-5 text-lg font-semibold">Lịch hẹn của bạn</h2>{picked.length ? <ul className="space-y-4">{picked.map(s => <li className="flex items-start justify-between gap-3" key={s.madv}><div><span className="font-medium">{s.tendv}</span><small className="mt-1 block text-muted-foreground">{usages.some(u => u.madv === s.madv) ? 'Dùng 1 buổi liệu trình / quà tặng' : `${s.thoiluong || 60} phút`}</small></div><button aria-label={`Bỏ ${s.tendv}`} disabled={busy} className="min-h-11 min-w-11 text-muted-foreground" onClick={() => { toggleService(s.madv); setStep(1); }}>×</button></li>)}</ul> : <p className="text-sm text-muted-foreground">Chưa chọn dịch vụ.</p>}
    <div className="mt-6 border-t border-border pt-5 text-sm"><p>{date.split('-').reverse().join('/')} {time && `· ${time}`}</p><p className="mt-2 text-muted-foreground">Tổng thời lượng: {duration} phút</p></div><div className="mt-5 flex justify-between gap-2 border-t border-border pt-5"><span>Tạm tính</span><strong data-testid="booking-total" className="text-lg text-primary">{money(amount)}</strong></div><p className="mt-3 text-xs text-muted-foreground">Điểm thưởng và voucher được áp dụng ở bước thanh toán VietQR, hoặc khi thanh toán tại spa.</p>
  </Card><a className="mt-4 inline-flex min-h-11 items-center text-sm text-primary underline" href="/profile#treatments">Xem liệu trình của tôi</a></aside></div>;
}
