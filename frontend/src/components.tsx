import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Empty, Form, Input, Pagination, Skeleton, Tag } from 'antd';
import { api } from './api';
import { statusLabel } from './attendance';
import type { Page } from './types';

export function useResource<T>(path: string) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(n => n + 1), []);
  useEffect(() => {
    let active = true;
    if (!path) { setLoading(false); setError(''); return; }  // '' = nothing to load yet
    setLoading(true); setError('');
    api<T>(path).then(value => { if (active) setData(value); })
      .catch(error => { if (active) setError(error.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, revision]);
  return { data, error, loading, reload };
}

export function ResourceState({ loading, error, reload, empty }: {
  loading: boolean; error: string; reload: () => void; empty?: boolean }) {
  if (loading) return <Skeleton active paragraph={{ rows: 3 }} />;
  if (error) return <Alert type="error" showIcon message={error} action={<Button onClick={reload}>Thử lại</Button>} />;
  if (empty) return <Empty description="Chưa có dữ liệu" />;
  return null;
}

export function Status({ value }: { value: string }) {
  const colors: Record<string, string> = { OPEN: 'blue', SUBMITTED: 'gold', APPROVED: 'green', LOCKED: 'green', REJECTED: 'red', PENDING: 'gold' };
  return <Tag color={colors[value]}>{statusLabel[value] || value}</Tag>;
}

export function Pager({ data, setPage }: { data?: Page<unknown>; setPage: (n: number) => void }) {
  return data && data.total > data.per_page ? <Pagination className="pager" current={data.page} total={data.total}
    pageSize={data.per_page} showSizeChanger={false} onChange={setPage} /> : null;
}

export function Reason() {
  return <Form.Item label="Lý do / ghi chú đối soát" name="reason" rules={[{ required: true, min: 3, max: 2000, message: 'Nhập lý do ít nhất 3 ký tự' }]}>
    <Input.TextArea rows={3} maxLength={2000} /></Form.Item>;
}

export const localInput = (value: string) => {
  const date = new Date(Date.parse(value) + 7 * 60 * 60 * 1000);
  return date.toISOString().slice(0, 16);
};
export const inputUtc = (value: string) => new Date(`${value}:00+07:00`).toISOString();
