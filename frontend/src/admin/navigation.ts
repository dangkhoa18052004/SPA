import type { Me } from '../types';

export type NavItem = { href: string; label: string };
export type NavGroup = { key: string; label: string; icon: string; items: NavItem[]; leaf?: boolean };

export const roleLabel: Record<string, string> = { admin: 'Quản trị viên', manager: 'Quản lý', letan: 'Lễ tân', staff: 'Nhân viên' };

const OPERATIONS = '/admin/operations';

/** `/admin/operations` and `/admin/operations/` open the same screen as its dashboard. */
export function normalizePath(path: string) {
  const clean = path.replace(/\/+$/, '') || '/';
  return clean === OPERATIONS ? `${OPERATIONS}/dashboard` : clean;
}

function roles(me: Me) {
  const role = me.user.role;
  const finance = role === 'admin' || role === 'manager';
  const frontDesk = role === 'letan';
  return { role, finance, frontDesk, internal: finance || frontDesk, admin: role === 'admin' };
}

/**
 * One menu for every internal role. Entries only appear when the role is offered that task;
 * the server still checks every request, so hiding a link is never the permission check.
 */
export function adminMenu(me: Me): NavGroup[] {
  const { role, finance, frontDesk, internal, admin } = roles(me);
  const f = me.features;
  const employeePortal = !!f.employee_portal;
  const myAppointments = employeePortal ? '/employee/appointments' : '/admin/appointments';
  const groups: NavGroup[] = [
    { key: 'overview', label: 'Tổng quan', icon: 'T', leaf: true, items: [{ href: '/admin/dashboard', label: 'Tổng quan công việc' }] },
    // Check-in/check-out is a daily task for every role: keep it one click away, never inside a collapsed group.
    { key: 'attendance', label: 'Chấm công', icon: 'G', leaf: true, items: employeePortal && f.attendance ? [{ href: '/employee/attendance', label: 'Chấm công vào/ra' }] : [] },
    { key: 'operations', label: 'Vận hành', icon: 'V', items: internal ? [
      { href: '/admin/appointments', label: 'Lịch hẹn' }, { href: '/admin/customers', label: 'Khách hàng' },
      { href: '/admin/invoices', label: 'Hóa đơn' }, { href: '/admin/package-sales', label: 'Bán gói' }]
      : [{ href: myAppointments, label: 'Lịch hẹn của tôi' }] },
    { key: 'people', label: 'Nhân sự', icon: 'N', items: [
      ...(admin ? [{ href: '/admin/staff', label: 'Nhân viên' }, { href: '/admin/roles', label: 'Chức vụ' }] : []),
      // Managers create and assign shifts too (the API allows it; per-shift attendance needs it).
      ...(finance ? [{ href: '/admin/shifts', label: 'Ca làm' }, { href: '/admin/approve-shifts', label: 'Duyệt đăng ký ca' }] : []),
      { href: '/admin/my-schedule', label: 'Lịch làm của tôi' }, { href: '/admin/register-shift', label: 'Đăng ký ca' }] },
    { key: 'payroll', label: 'Công và lương', icon: 'C', items: [
      ...(finance && employeePortal ? [{ href: `${OPERATIONS}/dashboard`, label: 'Tổng quan công' },
        { href: `${OPERATIONS}/attendance`, label: 'Bảng công' }, { href: `${OPERATIONS}/adjustments`, label: 'Yêu cầu chấm công' },
        { href: `${OPERATIONS}/payroll`, label: 'Kỳ công và lương' },
        { href: `${OPERATIONS}/branches`, label: f.simple_attendance ? 'Địa điểm chấm công' : 'Cơ sở và GPS' }] : []),
      ...(employeePortal ? [...(f.attendance ? [] : [{ href: '/employee/attendance', label: 'Ca của tôi' }]), { href: '/employee/income', label: 'Thu nhập của tôi' }]
        : [{ href: '/admin/my-salary', label: 'Lương của tôi' }]),
      ...(admin ? [{ href: '/admin/salary', label: 'Lịch sử lương cũ' }] : [])] },
    { key: 'catalog', label: 'Danh mục', icon: 'D', items: [
      ...(admin ? [{ href: '/admin/services', label: 'Dịch vụ' }] : []),
      ...(!frontDesk ? [{ href: '/admin/packages', label: role === 'staff' ? 'Liệu trình khách hàng' : 'Gói dịch vụ' }] : [])] },
    { key: 'care', label: 'Chăm sóc', icon: 'K', items: [
      ...(internal && f.crm ? [{ href: '/admin/crm', label: 'Chăm sóc khách hàng' }] : []),
      ...(internal ? [{ href: '/admin/loyalty', label: 'Điểm thưởng' }, { href: '/admin/chat', label: 'Tin nhắn' }] : f.admin_care ? [{ href: '/admin/chat', label: 'Tin nhắn của tôi' }] : []),
      ...(!frontDesk ? [{ href: '/admin/reviews', label: 'Đánh giá' }] : [])] },
    { key: 'reports', label: 'Báo cáo', icon: 'B', items: finance && f.bi ? [{ href: '/admin/reports', label: 'Kinh doanh và vận hành' }] : [] },
    { key: 'system', label: 'Hệ thống', icon: 'H', items: finance && employeePortal ? [{ href: `${OPERATIONS}/audit`, label: 'Nhật ký thao tác' }] : [] },
  ];
  return groups.filter(group => group.items.length);
}

export function accountMenu(me: Me): NavItem[] {
  return [{ href: '/admin/profile', label: 'Trang cá nhân' },
    ...(me.features.staff_security ? [{ href: '/admin/security', label: 'Bảo mật tài khoản' }] : [])];
}

/** Screens this React entry renders. Others are server pages and need a full page load. */
export function isAppPath(href: string, me: Me) {
  const path = normalizePath(href.split(/[?#]/)[0]);
  const f = me.features;
  if (path.startsWith(`${OPERATIONS}/`)) return !!f.employee_portal;
  if (/^\/admin\/packages\/(new|\d+(\/edit)?)$/.test(path)) return !!f.admin_catalog;
  return ({
    '/admin/dashboard': !!f.business_portal, '/admin/profile': !!f.business_portal,
    '/admin/appointments': !!f.admin_booking, '/admin/customers': !!f.admin_booking,
    '/admin/invoices': !!f.admin_billing, '/admin/package-sales': !!f.admin_billing,
    '/admin/services': !!f.admin_catalog, '/admin/packages': !!f.admin_catalog,
    '/admin/staff': !!f.admin_people, '/admin/roles': !!f.admin_people, '/admin/shifts': !!f.admin_people, '/admin/approve-shifts': !!f.admin_people,
    '/admin/my-schedule': !!f.admin_people, '/admin/register-shift': !!f.admin_people, '/admin/salary': !!f.admin_people,
    '/admin/crm': !!f.crm, '/admin/reports': !!f.bi, '/admin/security': !!f.staff_security,
    '/admin/loyalty': !!f.admin_care, '/admin/reviews': !!f.admin_care, '/admin/chat': !!f.admin_care,
  } as Record<string, boolean>)[path] ?? false;
}

export function findPage(me: Me, path: string): { group?: NavGroup; item?: NavItem } {
  // Sub-pages (package detail/create/edit) highlight their list in the menu.
  const target = normalizePath(path).replace(/^\/admin\/packages\/.+$/, '/admin/packages');
  for (const group of adminMenu(me)) {
    const item = group.items.find(i => normalizePath(i.href) === target);
    if (item) return { group, item };
  }
  const item = accountMenu(me).find(i => i.href === target);
  return item ? { group: { key: 'account', label: 'Tài khoản', icon: '', items: [] }, item } : {};
}
