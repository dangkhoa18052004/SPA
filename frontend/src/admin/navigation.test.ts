import { describe, expect, it } from 'vitest';
import type { Me } from '../types';
import { adminMenu, findPage, isAppPath, normalizePath } from './navigation';

const me = (role: string, features: Partial<Me['features']> = {}): Me => ({ user: { id: 1, name: 'An', role }, branches: [], managed_branch_ids: [],
  features: { attendance: true, payroll: true, employee_portal: true, business_portal: true, crm: true, bi: true, staff_security: true, ...features } });
const hrefs = (value: Me) => adminMenu(value).flatMap(g => g.items.map(i => i.href));

describe('shared admin menu', () => {
  it('uses the agreed group order and drops empty groups', () => {
    expect(adminMenu(me('admin')).map(g => g.label)).toEqual(['Tổng quan', 'Chấm công', 'Vận hành', 'Nhân sự', 'Công và lương', 'Danh mục', 'Chăm sóc', 'Báo cáo', 'Hệ thống']);
    expect(adminMenu(me('staff')).map(g => g.key)).not.toContain('reports');
  });
  it('keeps check-in/check-out one click away for every role', () => {
    for (const role of ['admin', 'manager', 'letan', 'staff']) {
      const group = adminMenu(me(role)).find(g => g.key === 'attendance');
      expect(group).toMatchObject({ leaf: true, items: [{ href: '/employee/attendance' }] });
    }
    expect(adminMenu(me('staff', { attendance: false })).some(g => g.key === 'attendance')).toBe(false);
    expect(adminMenu(me('staff', { employee_portal: false })).some(g => g.key === 'attendance')).toBe(false);
  });
  it('offers each role only its own tasks', () => {
    const admin = hrefs(me('admin')), manager = hrefs(me('manager')), desk = hrefs(me('letan')), staff = hrefs(me('staff'));
    expect(admin).toEqual(expect.arrayContaining(['/admin/staff', '/admin/services', '/admin/operations/payroll', '/admin/reports']));
    expect(manager).toContain('/admin/operations/payroll');
    expect(manager).not.toContain('/admin/staff');
    expect(manager).toEqual(expect.arrayContaining(['/admin/shifts', '/admin/approve-shifts']));
    expect(manager).not.toContain('/admin/salary');
    expect(admin).toContain('/admin/salary');
    expect(staff).toEqual(expect.arrayContaining(['/admin/my-schedule', '/admin/register-shift']));
    expect(staff).not.toContain('/admin/shifts');
    expect(desk).toEqual(expect.arrayContaining(['/admin/appointments', '/admin/package-sales', '/admin/crm']));
    expect(desk.some(h => h.startsWith('/admin/operations'))).toBe(false);
    expect(desk).not.toContain('/admin/reviews');
    expect(desk).not.toContain('/admin/packages');
    expect(staff).toContain('/admin/packages');
    expect(staff).toEqual(expect.arrayContaining(['/employee/appointments', '/employee/income']));
    expect(staff).not.toContain('/admin/appointments');
  });
  it('follows feature flags', () => {
    const off = hrefs(me('admin', { employee_portal: false, crm: false, bi: false }));
    expect(off).toContain('/admin/my-salary');
    // Without the employee portal a technician's bookings live on the appointments page (own schedule only).
    expect(hrefs(me('staff', { employee_portal: false }))).toContain('/admin/appointments');
    expect(findPage(me('staff', { employee_portal: false }), '/admin/my-schedule').item?.label).toBe('Lịch làm của tôi');
    expect(off.some(h => h.startsWith('/admin/operations') || h === '/admin/crm' || h === '/admin/reports')).toBe(false);
  });
});

describe('in-app navigation', () => {
  it('opens care screens in the same shell only with the care rollout enabled', () => {
    for (const path of ['/admin/loyalty?tab=redemptions', '/admin/reviews', '/admin/chat?conversation=1']) {
      expect(isAppPath(path, me('admin', { admin_care: true }))).toBe(true);
      expect(isAppPath(path, me('admin', { admin_care: false }))).toBe(false);
    }
    expect(hrefs(me('staff', { admin_care: true }))).toContain('/admin/chat');
  });
  it('only skips the page load for screens this entry renders', () => {
    expect(isAppPath('/admin/operations/payroll?x=1', me('manager'))).toBe(true);
    expect(isAppPath('/admin/dashboard', me('manager'))).toBe(true);
    expect(isAppPath('/admin/dashboard', me('manager', { business_portal: false }))).toBe(false);
    expect(isAppPath('/admin/appointments', me('manager'))).toBe(false);
    expect(isAppPath('/employee/attendance', me('manager'))).toBe(false);
  });
  it('finds the active page and its group for the breadcrumb', () => {
    expect(normalizePath('/admin/operations/')).toBe('/admin/operations/dashboard');
    expect(findPage(me('admin'), '/admin/operations')).toMatchObject({ group: { label: 'Công và lương' }, item: { label: 'Tổng quan công' } });
    expect(findPage(me('admin'), '/admin/profile').item?.label).toBe('Trang cá nhân');
    expect(findPage(me('admin'), '/admin/unknown')).toEqual({});
    expect(findPage(me('admin'), '/admin/packages/12/edit')).toMatchObject({ group: { key: 'catalog' }, item: { href: '/admin/packages' } });
    expect(isAppPath('/admin/packages/12/edit', me('admin', { admin_catalog: true }))).toBe(true);
    expect(isAppPath('/admin/packages/12/edit', me('admin'))).toBe(false);
  });
});
