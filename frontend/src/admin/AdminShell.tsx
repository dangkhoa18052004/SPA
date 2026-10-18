import React, { useEffect, useState } from 'react';
import { Breadcrumb, Button, Drawer, Dropdown, Menu, Tag } from 'antd';
import type { MenuProps } from 'antd';
import type { Me } from '../types';
import { isPlainClick, navigate } from '../router';
import { logout } from '../session';
import { accountMenu, adminMenu, findPage, isAppPath, roleLabel } from './navigation';
import './admin.css';

const COLLAPSE_KEY = 'binspa_admin_nav_collapsed';
const readCollapsed = () => { try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch { return false; } };

export function AdminShell({ me, path, children }: { me: Me; path: string; children: React.ReactNode }) {
  const groups = adminMenu(me);
  const { group, item } = findPage(me, path);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>(group ? [group.key] : []);
  useEffect(() => { document.title = `Bin Spa · ${item?.label || 'Quản trị'}`; }, [item?.label]);
  useEffect(() => { if (group && !openKeys.includes(group.key)) setOpenKeys(keys => [...keys, group.key]); }, [group?.key]);

  function follow(href: string) {
    return (event: React.MouseEvent) => {
      setDrawer(false);
      if (!isAppPath(href, me) || !isPlainClick(event)) return;
      event.preventDefault(); navigate(href);
    };
  }
  const link = (href: string, label: string) => <a href={href} onClick={follow(href)}>{label}</a>;
  const toggle = () => setCollapsed(value => {
    try { localStorage.setItem(COLLAPSE_KEY, value ? '0' : '1'); } catch { /* Preference only. */ }
    return !value;
  });
  const items: MenuProps['items'] = groups.map(g => g.leaf
    ? { key: g.items[0].href, icon: <span className="nav-icon" aria-hidden>{g.icon}</span>, label: link(g.items[0].href, g.label) }
    : { key: g.key, icon: <span className="nav-icon" aria-hidden>{g.icon}</span>, label: g.label,
      children: g.items.map(i => ({ key: i.href, label: link(i.href, i.label) })) });
  const menu = (inline: boolean) => <Menu mode="inline" className="admin-menu" items={items}
    inlineCollapsed={inline ? false : collapsed} selectedKeys={item ? [item.href] : []}
    {...(inline || !collapsed ? { openKeys, onOpenChange: setOpenKeys } : {})} />;
  const account: MenuProps['items'] = [
    ...accountMenu(me).map(i => ({ key: i.href, label: link(i.href, i.label) })),
    ...(me.features.employee_portal ? [{ key: 'employee', label: <a href="/employee/attendance">Cổng nhân viên</a> }] : []),
    { type: 'divider' as const }, { key: 'logout', label: 'Đăng xuất', danger: true, onClick: () => { void logout(); } }];

  return <div className={`admin-shell${collapsed ? ' is-collapsed' : ''}`}>
    <header className="admin-topbar">
      <div className="admin-topbar-start">
        <Button className="admin-menu-button mobile-only" onClick={() => setDrawer(true)} aria-label="Mở menu">☰</Button>
        <Button className="admin-menu-button desktop-only" type="text" onClick={toggle} aria-expanded={!collapsed}
          aria-label={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}>☰</Button>
        <a className="brand" href="/admin/dashboard" onClick={follow('/admin/dashboard')}><span className="brand-mark">B</span><b>Bin Spa</b></a>
      </div>
      <Dropdown menu={{ items: account }} trigger={['click']} placement="bottomRight">
        <Button type="text" className="admin-account" aria-label="Tài khoản">
          <span className="admin-avatar" aria-hidden>{me.user.name.trim().charAt(0).toUpperCase() || 'B'}</span>
          <span className="admin-account-name">{me.user.name}</span><Tag className="admin-role">{roleLabel[me.user.role] || me.user.role}</Tag>
        </Button>
      </Dropdown>
    </header>
    <aside className="admin-sidebar" aria-label="Menu quản trị">{menu(false)}</aside>
    <Drawer title="Bin Spa · Quản trị" placement="left" open={drawer} onClose={() => setDrawer(false)} width={300} className="admin-drawer">
      {menu(true)}
      <div className="admin-drawer-account">{accountMenu(me).map(i => <div key={i.href}>{link(i.href, i.label)}</div>)}
        <Button block onClick={() => { void logout(); }}>Đăng xuất</Button></div>
    </Drawer>
    <main className="admin-main" id="admin-content">
      {item && group && <Breadcrumb className="admin-breadcrumb" items={[{ title: link('/admin/dashboard', 'Bin Spa') },
        ...(!group.leaf ? [{ title: group.label }] : []), { title: item.label }]} />}
      {children}
    </main>
  </div>;
}
