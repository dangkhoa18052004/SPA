import { useState } from 'react';
import { Alert, App, Button, Card, Drawer, Empty, Form, Input, Pagination, Rate, Result, Select, Space, Tag } from 'antd';
import { del, put } from '../../api';
import { ResourceState, useResource } from '../../components';
import { useQuery } from '../../router';
import type { Me } from '../../types';
import { options, utcDate } from './model';
import './care.css';

type Review = { madg: number; malh: number; rating: number; comment: string; created_at: string; customer_name: string;
  staff_name: string; services: string; verified: boolean; reply: { content: string; staff_name: string; created_at: string } | null };
type ReviewsData = { reviews: Review[]; total: number; page: number; per_page: number;
  services: { madv: number; tendv: string }[]; staff: { manv: number; hoten: string }[] };
function Reply({ review, close, saved }: { review: Review; close: () => void; saved: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [form] = Form.useForm(); const { message, modal } = App.useApp();
  const onClose = () => { if (busy) return; if (!form.isFieldsTouched()) close(); else modal.confirm({ title: 'Bỏ phản hồi chưa lưu?', okText: 'Bỏ thay đổi', cancelText: 'Tiếp tục viết', onOk: close }); };
  return <Drawer open title="Phản hồi đánh giá" width={560} onClose={onClose} maskClosable={!busy}><h2>{review.customer_name}</h2><Rate disabled value={review.rating} /><p className="care-text">{review.comment || 'Khách chỉ chấm sao'}</p><p>{review.services} · {review.staff_name}</p>
    <Alert showIcon type="info" message="Phản hồi được công khai cùng đánh giá. Không đưa số điện thoại hoặc thông tin riêng của khách vào nội dung." />
    {error && <Alert type="error" className="care-section" message={error} />}<Form form={form} layout="vertical" className="care-section" initialValues={{ content: review.reply?.content || '' }} disabled={busy} onFinish={async v => {
      setBusy(true); setError(''); try { await put(`/api/reviews/${review.madg}/reply`, { content: v.content.trim() }); message.success('Đã lưu phản hồi'); saved(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
    }}><Form.Item name="content" label="Nội dung phản hồi" rules={[{ required: true, whitespace: true, max: 5000 }]}><Input.TextArea rows={6} showCount maxLength={5000} /></Form.Item><Space><Button htmlType="submit" type="primary" loading={busy}>Lưu phản hồi</Button><Button onClick={onClose}>Hủy</Button></Space></Form>
  </Drawer>;
}
export default function Reviews({ me }: { me: Me }) {
  const [q, query] = useQuery(); const [selected, select] = useState<Review | null>(null); const { modal, message } = App.useApp();
  const allowed = ['admin', 'manager', 'staff'].includes(me.user.role);
  // Render the role gate before mounting the data component, so forbidden accounts make no API request.
  return allowed ? <ReviewList me={me} q={q} query={query} selected={selected} select={select} modal={modal} message={message} /> : <Result status="403" title="Bạn không có quyền xem đánh giá" />;
}
function ReviewList({ me, q, query, selected, select, modal, message }: { me: Me; q: URLSearchParams; query: ReturnType<typeof useQuery>[1]; selected: Review | null; select: (r: Review | null) => void; modal: ReturnType<typeof App.useApp>['modal']; message: ReturnType<typeof App.useApp>['message'] }) {
  const params = new URLSearchParams(); ['rating', 'service', 'staff', 'replied', 'search', 'page'].forEach(k => { if (q.get(k)) params.set(k, q.get(k)!); });
  const r = useResource<ReviewsData>(`/api/reviews/manage?${params}`);
  return <><div className="page-heading"><h1>Đánh giá của khách</h1><p>{me.user.role === 'staff' ? 'Đánh giá từ các lịch hẹn bạn thực hiện.' : 'Đọc nhận xét và trả lời khách sau khi sử dụng dịch vụ.'}</p></div>
    <div className="care-toolbar"><Input.Search key={q.get('search')} aria-label="Tìm đánh giá theo tên khách" placeholder="Tìm theo tên khách" defaultValue={q.get('search') || ''} enterButton="Tìm" onSearch={search => query({ search, page: 1 })} />
      <Select aria-label="Số sao" value={q.get('rating') || ''} options={options({ '': 'Mọi số sao', '5': '5 sao', '4': '4 sao', '3': '3 sao', '2': '2 sao', '1': '1 sao' })} onChange={rating => query({ rating, page: 1 })} />
      <Select aria-label="Trạng thái phản hồi" value={q.get('replied') || ''} options={options({ '': 'Mọi phản hồi', no: 'Chưa phản hồi', yes: 'Đã phản hồi' })} onChange={replied => query({ replied, page: 1 })} />
      <Select aria-label="Dịch vụ được đánh giá" value={q.get('service') || ''} options={[{ value: '', label: 'Mọi dịch vụ' }, ...(r.data?.services || []).map(s => ({ value: String(s.madv), label: s.tendv }))]} onChange={service => query({ service, page: 1 })} />
      {me.user.role !== 'staff' && <Select aria-label="Nhân viên được đánh giá" value={q.get('staff') || ''} options={[{ value: '', label: 'Mọi nhân viên' }, ...(r.data?.staff || []).map(s => ({ value: String(s.manv), label: s.hoten }))]} onChange={staff => query({ staff, page: 1 })} />}
      <Button onClick={() => query({ rating: null, service: null, staff: null, replied: null, search: null, page: 1 })}>Xóa bộ lọc</Button>
    </div><ResourceState {...r} />{!r.loading && !r.error && <><p>{r.data?.total || 0} đánh giá phù hợp</p><div className="care-list">{r.data?.reviews.length ? r.data.reviews.map(row => <Card key={row.madg} data-testid={`review-${row.madg}`}><div className="card-head"><h3>{row.customer_name}</h3><Rate disabled value={row.rating} /></div><p>{row.services} · {row.staff_name} · {utcDate(row.created_at)}</p><p className="care-text">{row.comment || 'Khách chỉ chấm sao'}</p>{row.verified && <Tag color="green">Đã sử dụng dịch vụ</Tag>}{row.reply && <blockquote className="care-text"><b>Spa đã phản hồi</b><p>{row.reply.content}</p><small>{row.reply.staff_name} · {utcDate(row.reply.created_at)}</small></blockquote>}<Space wrap><Button type={row.reply ? 'default' : 'primary'} onClick={() => select(row)}>{row.reply ? 'Sửa phản hồi' : 'Trả lời khách'}</Button>{row.reply && <Button danger onClick={() => modal.confirm({ title: 'Xóa phản hồi của spa?', content: 'Đánh giá của khách vẫn được giữ.', okText: 'Xóa phản hồi', cancelText: 'Giữ lại', onOk: async () => { try { await del(`/api/reviews/${row.madg}/reply`); r.reload(); } catch (e) { message.error((e as Error).message); } } })}>Xóa phản hồi</Button>}</Space></Card>) : <Empty description="Không có đánh giá phù hợp" />}</div><Pagination className="care-section" current={r.data?.page || 1} total={r.data?.total || 0} pageSize={20} showSizeChanger={false} onChange={page => query({ page })} /></>}
    {selected && <Reply key={selected.madg} review={selected} close={() => select(null)} saved={() => { select(null); r.reload(); }} />}
  </>;
}
