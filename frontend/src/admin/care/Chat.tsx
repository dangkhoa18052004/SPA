import { useEffect, useRef, useState } from 'react';
import { Alert, App, Badge, Button, Card, Collapse, Empty, Input, Pagination, Result, Select, Space } from 'antd';
import { ApiError, api, post, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { fold, vnd } from '../booking/model';
import { reconcileMessage, richMessage, utcDate } from './model';
import type { ChatMessage, Conversation } from './model';
import './care.css';

type Saved = { text: string; pending?: { text: string; baseline: number[] } };
function read(key: string): Saved { try { const v = JSON.parse(sessionStorage.getItem(key) || '{}'); return v && typeof v.text === 'string' ? v : { text: '' }; } catch { return { text: '' }; } }
function write(key: string, value: Saved) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* A storage limit must not interrupt sending. */ } }
function MessageContent({ text }: { text: string }) {
  const rich = richMessage(text);
  return <>{rich.image && <img src={rich.image} alt={'name' in rich ? rich.name : 'Ảnh trong tin nhắn'} loading="lazy" onError={e => { e.currentTarget.style.display = 'none'; }} />}{'name' in rich && <p><b>{rich.name}</b><br />{vnd(rich.price!)} · {rich.duration} phút</p>}<span>{rich.text}</span></>;
}
function Thread({ conversation, me, close, refresh }: { conversation: Conversation; me: Me; close: () => void; refresh: () => void }) {
  const id = conversation.maht; const key = `binspa-chat-draft:${me.user.id}:${id}`;
  const [saved, setSaved] = useState<Saved>(() => read(key)); const [messages, setMessages] = useState<ChatMessage[]>([]); const [error, setError] = useState('');
  const [loading, setLoading] = useState(true); const [sending, setSending] = useState(false); const [uncertain, setUncertain] = useState(!!saved.pending);
  const active = useRef(true); const flight = useRef(false); const box = useRef<HTMLDivElement>(null); const savedRef = useRef(saved);
  const { modal } = App.useApp(); const desk = ['admin', 'manager', 'letan'].includes(me.user.role);
  function persist(next: Saved) { savedRef.current = next; setSaved(next); write(key, next); }
  async function load() {
    if (flight.current) return;
    flight.current = true;
    try {
      const data = await api<{ messages: ChatMessage[] }>(`/api/chat/conversations/${id}/messages`);
      if (!active.current) return;
      const nearBottom = !box.current || box.current.scrollHeight - box.current.scrollTop - box.current.clientHeight < 100;
      setMessages(data.messages); setError(''); setLoading(false);
      const pending = savedRef.current.pending;
      if (pending && reconcileMessage(data.messages, pending.baseline, pending.text, me.user.id).length === 1) {
        persist({ text: '' }); setUncertain(false);
      }
      if (nearBottom) window.setTimeout(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, 50);
      refresh();
    } catch (e) { if (active.current) { setError((e as Error).message); setLoading(false); if (e instanceof ApiError && [401, 403, 404].includes(e.status)) setMessages([]); } } finally { flight.current = false; }
  }
  useEffect(() => {
    active.current = true; void load();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void load(); }, 5000);
    return () => { active.current = false; window.clearInterval(timer); };
  }, [id]);
  async function send() {
    const text = (savedRef.current.text || '').trim(); if (!text || sending || uncertain || loading || error) return;
    const pending = { text, baseline: messages.map(m => m.matn) }; persist({ text, pending }); setSending(true);
    try { await post(`/api/chat/conversations/${id}/messages`, { noidung: text }); write(key, { text: '' }); if (active.current) { persist({ text: '' }); setUncertain(false); await load(); } }
    catch (e) {
      // Unknown outcomes are read back first. Never automatically repeat a message POST.
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        write(key, { text }); if (active.current) { persist({ text }); setUncertain(false); setError((e as Error).message); }
      } else if (active.current) { setUncertain(true); setError((e as Error).message); await load(); }
    } finally { if (active.current) setSending(false); }
  }
  return <Card className="care-chat-thread"><Space wrap><Button className="care-chat-back" onClick={close}>← Danh sách</Button><h2>{conversation.customer_name}</h2></Space>
    <p>{conversation.assigned_staff_name ? `Phụ trách: ${conversation.assigned_staff_name}` : 'Hộp thư chăm sóc chung'}</p>
    {desk && <Collapse size="small" items={[{ key: 'assign', label: 'Thay đổi người phụ trách', children: <Assignment conversation={conversation} refresh={refresh} /> }]} />}
    <ResourceState loading={loading} error={error} reload={() => { void load(); }} />
    <div ref={box} className="care-messages" aria-label="Nội dung hội thoại" aria-live="polite">{messages.map(m => <article key={m.matn} className={`care-message${m.is_from_staff ? ' sent' : ''}`}><MessageContent text={m.noidung} /><small>{m.is_from_staff ? 'Spa' : 'Khách'} · {utcDate(m.thoigian)}</small></article>)}{!loading && !messages.length && !error && <Empty description="Hội thoại chưa có tin nhắn" />}</div>
    {uncertain && <Alert showIcon type="warning" message="Chưa xác định tin nhắn đã gửi hay chưa" description="Đang đối chiếu lịch sử. Kiểm tra nội dung trước khi gửi thêm để tránh trùng tin." action={<Space direction="vertical"><Button onClick={() => { void load(); }}>Kiểm tra lại</Button><Button onClick={() => modal.confirm({ title: 'Bạn đã kiểm tra lịch sử hội thoại?', content: 'Tin vừa gửi có thể đến trễ. Chỉ tiếp tục soạn sau khi đã kiểm tra; không gửi lại nội dung đã xuất hiện.', okText: 'Đã kiểm tra, tiếp tục soạn', cancelText: 'Chờ kiểm tra thêm', onOk: () => { persist({ text: savedRef.current.text }); setUncertain(false); setError(''); } })}>Tiếp tục soạn sau khi kiểm tra</Button></Space>} />}
    <div className="care-compose"><label htmlFor="chat-message-input">Tin nhắn cho khách</label><Input.TextArea id="chat-message-input" value={saved.text || ''} disabled={sending || uncertain} rows={3} maxLength={5000} showCount placeholder="Nhập nội dung, sau đó bấm Gửi tin nhắn" onChange={e => persist({ text: e.target.value })} />
      <Space wrap><Button data-testid="chat-send" type="primary" loading={sending} disabled={!saved.text?.trim() || uncertain || loading || !!error} onClick={() => { void send(); }}>Gửi tin nhắn</Button><span className="muted">Bản đang viết được giữ khi chuyển trang trong tab này.</span></Space>
    </div>
  </Card>;
}
function Assignment({ conversation, refresh }: { conversation: Conversation; refresh: () => void }) {
  const people = useResource<{ items: { manv: number; hoten: string }[] }>('/api/admin/conversations/assignees');
  const [assigned, setAssigned] = useState<number>(); const [busy, setBusy] = useState(false); const { message } = App.useApp();
  async function assign(remove = false) { setBusy(true); try { await put(`/api/admin/conversations/${conversation.maht}/${remove ? 'unassign' : 'assign'}`, remove ? {} : { manv: assigned }); refresh(); message.success(remove ? 'Đã chuyển về hộp thư chung' : 'Đã phân người phụ trách'); } catch (e) { message.error((e as Error).message); } finally { setBusy(false); } }
  return <><ResourceState {...people} /><Space wrap className="care-section"><Select aria-label="Nhân viên nhận hội thoại" placeholder="Chọn kỹ thuật viên" value={assigned} onChange={setAssigned} style={{ minWidth: 180 }} options={(people.data?.items || []).map(p => ({ value: p.manv, label: p.hoten }))} /><Button disabled={!assigned} loading={busy} onClick={() => { void assign(); }}>Giao phụ trách</Button>{conversation.assigned_staff_id && <Button disabled={busy} onClick={() => { void assign(true); }}>Về hộp thư chung</Button>}</Space></>;
}
function Inbox({ me }: { me: Me }) {
  const [q, query] = useQuery(); const r = useResource<{ conversations: Conversation[] }>('/api/chat/conversations');
  useEffect(() => { const timer = window.setInterval(() => { if (document.visibilityState === 'visible') r.reload(); }, 15000); return () => window.clearInterval(timer); }, [r.reload]);
  const selectedId = Number(q.get('conversation')); const selected = r.data?.conversations.find(c => c.maht === selectedId);
  const rows = (r.data?.conversations || []).filter(c => (!q.get('unread') || c.unread_count > 0 || c.maht === selectedId) && fold(c.customer_name + ' ' + c.last_message).includes(fold(q.get('q') || '')));
  const page = Math.max(1, Number(q.get('page')) || 1); const visible = rows.slice((page - 1) * 15, page * 15);
  return <><div className="page-heading"><h1>Tin nhắn khách hàng</h1><p>Chọn hội thoại để đọc và trả lời khách.</p></div>
    {!r.data && <ResourceState {...r} />}{r.error && r.data && <Alert type="error" message={r.error} action={<Button onClick={r.reload}>Thử lại</Button>} />}
    <div className={`care-chat-grid${selected ? ' has-selection' : ''}`}><Card className="care-chat-sidebar"><div className="care-list"><Input.Search aria-label="Tìm hội thoại" key={q.get('q')} defaultValue={q.get('q') || ''} placeholder="Tên khách hoặc tin nhắn" enterButton="Tìm" onSearch={value => query({ q: value, page: 1 })} /><Select aria-label="Lọc hội thoại" value={q.get('unread') || ''} options={[{ value: '', label: 'Tất cả hội thoại' }, { value: '1', label: 'Có tin chưa đọc' }]} onChange={unread => query({ unread, page: 1 })} />
      <div className="care-conversations">{visible.map(c => <button className="care-conversation" key={c.maht} aria-current={selectedId === c.maht ? 'page' : undefined} onClick={() => query({ conversation: c.maht })}><b>{c.customer_name}</b> <Badge count={c.unread_count} /><p>{c.last_message || 'Chưa có tin nhắn'}</p><small>{utcDate(c.last_message_time)}</small></button>)}{!r.loading && !rows.length && <Empty description="Không có hội thoại phù hợp" />}</div><Pagination simple current={page} total={rows.length} pageSize={15} showSizeChanger={false} onChange={page => query({ page })} /></div></Card>
      {selected ? <Thread key={selected.maht} conversation={selected} me={me} close={() => query({ conversation: null })} refresh={r.reload} /> : <Card className="care-chat-thread"><Empty description={selectedId ? 'Hội thoại không tồn tại hoặc bạn không còn quyền xem' : 'Chọn khách ở danh sách bên cạnh'} /></Card>}
    </div>
  </>;
}
export default function Chat({ me }: { me: Me }) {
  return ['admin', 'manager', 'letan', 'staff'].includes(me.user.role) ? <Inbox me={me} /> : <Result status="403" title="Bạn không có quyền xem tin nhắn" />;
}
