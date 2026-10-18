import { useRef } from 'react';
import { Button } from 'antd';
import type { ButtonProps } from 'antd';
import { isPlainClick, navigate } from '../../router';

/** Real link styled as an antd button; plain clicks stay in the app, new-tab clicks work as usual. */
export function AppLink({ href, children, type, size }: { href: string; children: React.ReactNode; type?: ButtonProps['type']; size?: ButtonProps['size'] }) {
  return <Button href={href} type={type} size={size} onClick={e => { if (isPlainClick(e)) { e.preventDefault(); navigate(href); } }}>{children}</Button>;
}

/** Button that opens a hidden file input (keyboard and screen-reader friendly). */
export function FilePick({ accept, label, onPick }: { accept: string; label: string; onPick: (file?: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <>
    <Button onClick={() => input.current?.click()}>Chọn ảnh</Button>
    <input ref={input} type="file" accept={accept} aria-label={label} style={{ display: 'none' }}
      onChange={e => { onPick(e.target.files?.[0]); e.target.value = ''; }} />
  </>;
}
