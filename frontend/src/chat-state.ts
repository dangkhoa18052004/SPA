import { useEffect, useState } from 'react';
import { api } from './api';
import type { Me } from './types';
import type { Conversation } from './admin/care/model';

export const newestConversations = (rows: Conversation[]) => [...rows].sort((a, b) =>
  (Date.parse(b.last_message_time || '') || 0) - (Date.parse(a.last_message_time || '') || 0) || b.maht - a.maht);
type State = { data?: { conversations: Conversation[] }; loading: boolean; error: string };
type Store = { state: State; listeners: Set<(state: State) => void>; reload: () => void; start: () => void; stop: () => void };
const stores = new Map<string, Store>();

function createStore(): Store {
  let sequence = 0, timer: number | undefined;
  const store: Store = { state: { loading: true, error: '' }, listeners: new Set(), reload, start, stop };
  const emit = (state: State) => { store.state = state; store.listeners.forEach(fn => fn(state)); };
  function reload() {
    window.clearTimeout(timer);
    if (document.visibilityState !== 'visible') return;
    const request = ++sequence;
    if (!store.state.data) emit({ ...store.state, loading: true, error: '' });
    // This API only reads lists; it never marks any thread read. Sequence guards
    // prevent a slow older poll from restoring unread counts after a thread read.
    void api<{ conversations: Conversation[] }>('/api/chat/conversations').then(data => {
      if (request === sequence) emit({ data: { conversations: newestConversations(data.conversations) }, loading: false, error: '' });
    }).catch(error => { if (request === sequence) emit({ ...store.state, loading: false, error: error.message }); })
      .finally(() => { if (request === sequence && store.listeners.size) timer = window.setTimeout(reload, 15000); });
  }
  function start() { document.addEventListener('visibilitychange', reload); window.addEventListener('focus', reload); reload(); }
  function stop() { ++sequence; window.clearTimeout(timer); document.removeEventListener('visibilitychange', reload); window.removeEventListener('focus', reload); }
  return store;
}

/** One polling lifecycle per signed-in identity, shared by shell and inbox. */
export function useChatConversations(me: Me) {
  const enabled = !!me.features.admin_care && ['admin', 'manager', 'letan', 'staff'].includes(me.user.role);
  const key = `${me.user.role}:${me.user.id}`;
  const [state, setState] = useState<State & { identity?: string }>({ loading: enabled, error: '' });
  useEffect(() => {
    if (!enabled) { setState({ loading: false, error: '' }); return; }
    let store = stores.get(key);
    if (!store) { store = createStore(); stores.set(key, store); }
    const receive = (value: State) => setState({ ...value, identity: key });
    store.listeners.add(receive); receive(store.state);
    if (store.listeners.size === 1) store.start();
    return () => { store.listeners.delete(receive); if (!store.listeners.size) { store.stop(); stores.delete(key); } };
  }, [key, enabled]);
  const reload = () => stores.get(key)?.reload();
  const visible = enabled && state.identity === key ? state : { loading: enabled, error: '', data: undefined };
  return { ...visible, reload, totalUnread: visible.data?.conversations.reduce((sum, c) => sum + Math.max(0, c.unread_count || 0), 0) || 0 };
}
