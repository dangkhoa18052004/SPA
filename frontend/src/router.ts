import { useCallback, useEffect, useState } from 'react';

// Flask still serves every URL on a direct load or reload; this only avoids a full reload
// when moving between screens that the same React entry already renders.
const EVENT = 'binspa:navigate';
const current = () => window.location.pathname + window.location.search;

export function navigate(href: string, replace = false) {
  if (href === current()) return;
  window.history[replace ? 'replaceState' : 'pushState'](null, '', href);
  window.dispatchEvent(new Event(EVENT));
  if (!replace) window.scrollTo(0, 0);
}

export function useLocation() {
  const [href, setHref] = useState(current);
  useEffect(() => {
    const update = () => setHref(current());
    window.addEventListener('popstate', update); window.addEventListener(EVENT, update);
    return () => { window.removeEventListener('popstate', update); window.removeEventListener(EVENT, update); };
  }, []);
  const url = new URL(href, window.location.origin);
  return { pathname: url.pathname, search: url.search };
}

/** Filters and pagination kept in the query string so Back/Reload restore the same view. */
export function useQuery(): [URLSearchParams, (patch: Record<string, string | number | null | undefined>, replace?: boolean) => void] {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const update = useCallback((patch: Record<string, string | number | null | undefined>, replace = false) => {
    const next = new URLSearchParams(window.location.search);
    Object.entries(patch).forEach(([key, value]) => value === null || value === undefined || value === '' ? next.delete(key) : next.set(key, String(value)));
    const query = next.toString();
    navigate(window.location.pathname + (query ? `?${query}` : ''), replace);
  }, []);
  return [params, update];
}

/** Plain left click on an in-app link: keep new-tab and modifier clicks native. */
export function isPlainClick(event: { button?: number; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean }) {
  return (event.button ?? 0) === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}
