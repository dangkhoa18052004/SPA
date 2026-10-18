import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App, Button, ConfigProvider, Result } from 'antd';
import viVN from 'antd/locale/vi_VN';
import { ResourceState, useResource } from './components';
import type { Me } from './types';
import './style.css';
import { StepUpGate } from './StepUpGate';
import { useLocation } from './router';
import { AdminShell } from './admin/AdminShell';
import { normalizePath } from './admin/navigation';

const Today = React.lazy(() => import('./Employee').then(m => ({ default: m.Today })));
const Schedule = React.lazy(() => import('./Employee').then(m => ({ default: m.Schedule })));
const History = React.lazy(() => import('./Employee').then(m => ({ default: m.History })));
const Income = React.lazy(() => import('./Employee').then(m => ({ default: m.Income })));
const Account = React.lazy(() => import('./Employee').then(m => ({ default: m.Account })));
const Appointments = React.lazy(() => import('./Appointments'));
const Dashboard = React.lazy(() => import('./Manager').then(m => ({ default: m.Dashboard })));
const ReviewAttendance = React.lazy(() => import('./Manager').then(m => ({ default: m.ReviewAttendance })));
const ReviewAdjustments = React.lazy(() => import('./Manager').then(m => ({ default: m.ReviewAdjustments })));
const Payroll = React.lazy(() => import('./Manager').then(m => ({ default: m.Payroll })));
const Branches = React.lazy(() => import('./Manager').then(m => ({ default: m.Branches })));
const Audit = React.lazy(() => import('./Manager').then(m => ({ default: m.Audit })));
const BusinessDashboard = React.lazy(() => import('./BusinessDashboard'));
const CRM = React.lazy(() => import('./CRM'));
const Reports = React.lazy(() => import('./Reports'));
const Security = React.lazy(() => import('./Security'));
const Profile = React.lazy(() => import('./admin/Profile'));
const Login = React.lazy(() => import('./admin/Login'));
const AdminAppointments = React.lazy(() => import('./admin/booking/Appointments').then(m => ({ default: m.AppointmentsGate })));
const AdminCustomers = React.lazy(() => import('./admin/booking/Customers'));
const AdminInvoices = React.lazy(() => import('./admin/billing/Invoices'));
const AdminPackageSales = React.lazy(() => import('./admin/billing/PackageSales'));
const AdminServices = React.lazy(() => import('./admin/catalog/Services'));
const AdminPackages = React.lazy(() => import('./admin/catalog/Packages'));
const AdminPackagePage = React.lazy(() => import('./admin/catalog/PackageForm'));
const AdminStaff = React.lazy(() => import('./admin/people/Staff'));
const AdminPositions = React.lazy(() => import('./admin/people/Staff').then(m => ({ default: m.Positions })));
const AdminShifts = React.lazy(() => import('./admin/people/Shifts'));
const AdminApproveShifts = React.lazy(() => import('./admin/people/Shifts').then(m => ({ default: m.ApproveShifts })));
const AdminMySchedule = React.lazy(() => import('./admin/people/MySchedule').then(m => ({ default: m.MySchedule })));
const AdminRegisterShift = React.lazy(() => import('./admin/people/MySchedule').then(m => ({ default: m.RegisterShift })));
const AdminLegacySalary = React.lazy(() => import('./admin/people/LegacySalary'));
const AdminLoyalty = React.lazy(() => import('./admin/care/Loyalty'));
const AdminReviews = React.lazy(() => import('./admin/care/Reviews'));
const AdminChat = React.lazy(() => import('./admin/care/Chat'));

const loading = <ResourceState loading error="" reload={() => {}} />;

function adminScreen(me: Me, path: string): React.ReactNode {
  const canManage = ['admin', 'manager'].includes(me.user.role);
  if (path.startsWith('/admin/operations/')) {
    if (!canManage) return <Result status="403" title="Không có quyền truy cập" subTitle="Màn này dành cho quản lý công và lương."
      extra={<Button href="/employee/attendance">Ca của tôi</Button>} />;
    const screens: Record<string, React.ReactNode> = { dashboard: <Dashboard />, attendance: <ReviewAttendance />,
      adjustments: <ReviewAdjustments />, payroll: <Payroll me={me} />, branches: <Branches me={me} />, audit: <Audit /> };
    return screens[path.slice('/admin/operations/'.length)];
  }
  if (me.features.admin_catalog && path.startsWith('/admin/packages/')) return <AdminPackagePage me={me} path={path} />;
  return ({ '/admin/dashboard': <BusinessDashboard me={me} />, '/admin/crm': <CRM me={me} />, '/admin/reports': <Reports me={me} />,
    '/admin/security': <Security me={me} />, '/admin/profile': <Profile me={me} />,
    ...(me.features.admin_care ? { '/admin/loyalty': <AdminLoyalty me={me} />, '/admin/reviews': <AdminReviews me={me} />, '/admin/chat': <AdminChat me={me} /> } : {}),
    ...(me.features.admin_booking ? { '/admin/appointments': <AdminAppointments me={me} />, '/admin/customers': <AdminCustomers me={me} /> } : {}),
    ...(me.features.admin_billing ? { '/admin/invoices': <AdminInvoices me={me} />, '/admin/package-sales': <AdminPackageSales me={me} /> } : {}),
    ...(me.features.admin_catalog ? { '/admin/services': <AdminServices me={me} />, '/admin/packages': <AdminPackages me={me} /> } : {}),
    ...(me.features.admin_people ? { '/admin/staff': <AdminStaff me={me} />, '/admin/roles': <AdminPositions me={me} />, '/admin/shifts': <AdminShifts me={me} />,
      '/admin/approve-shifts': <AdminApproveShifts me={me} />, '/admin/my-schedule': <AdminMySchedule me={me} />, '/admin/register-shift': <AdminRegisterShift me={me} />,
      '/admin/salary': <AdminLegacySalary me={me} /> } : {}) } as Record<string, React.ReactNode>)[path];
}

function EmployeePortal({ me, path }: { me: Me; path: string }) {
  const canManage = ['admin', 'manager'].includes(me.user.role);
  const screen = path.split('/').filter(Boolean).slice(1).join('/') || 'attendance';
  const items = [['attendance', 'Hôm nay'], ['appointments', 'Lịch hẹn'], ['schedule', 'Lịch ca'], ['income', 'Thu nhập'], ['account', 'Tài khoản']];
  const screens: Record<string, React.ReactNode> = { attendance: <Today />, appointments: <Appointments />, schedule: <Schedule />,
    history: <History />, income: <Income />, account: <Account me={me} /> };
  const adminHome = me.features.business_portal ? '/admin/dashboard' : '/admin/operations';
  return <div className="portal employee-portal">
    <header className="portal-header"><a className="brand" href="/employee/attendance"><span className="brand-mark">B</span><b>Bin Spa</b></a>
      <div className="header-actions"><span className="user-name">{me.user.name}</span>
        {(canManage || (me.user.role === 'letan' && me.features.business_portal)) && <a href={adminHome}>Về trang quản trị</a>}</div></header>
    <main className="portal-main"><div className="section-toolbar"><a className="profile-return" href="/admin/profile">← Trang cá nhân và các chức năng khác</a>
      {me.features.staff_security && <a href="/admin/security">Bảo mật tài khoản</a>}</div>
      <React.Suspense fallback={loading}>
        {screens[screen] || <Result status="404" title="Không tìm thấy trang" extra={<Button href="/employee/attendance">Về trang chính</Button>} />}
      </React.Suspense></main>
    <nav className="employee-nav" aria-label="Cổng nhân viên">
      {items.map(([key, label]) => <a key={key} href={`/employee/${key}`} aria-current={screen === key || (key === 'attendance' && screen === 'history') ? 'page' : undefined}>{label}</a>)}
    </nav>
  </div>;
}

function Portal({ path }: { path: string }) {
  const resource = useResource<Me>('/api/me/operations');
  const [, setClock] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 30000); return () => window.clearInterval(timer); }, []);
  if (resource.loading && !resource.data) return <div className="portal-loading">{loading}</div>;
  if (resource.error || !resource.data) return <div className="portal-loading"><ResourceState {...resource} /></div>;
  const me = resource.data;
  if (path === '/employee' || path.startsWith('/employee/')) return <EmployeePortal me={me} path={path} />;
  const screen = adminScreen(me, path);
  return <AdminShell me={me} path={path}>
    <ScreenBoundary key={path}><React.Suspense fallback={loading}>
      {screen || <Result status="404" title="Không tìm thấy trang" extra={<Button href="/admin/dashboard">Về tổng quan</Button>} />}
    </React.Suspense></ScreenBoundary>
  </AdminShell>;
}

function Root() {
  const path = normalizePath(useLocation().pathname);
  if (path === '/admin/login') return <React.Suspense fallback={<div className="portal-loading">{loading}</div>}><Login /></React.Suspense>;
  return <Portal path={path} />;
}

class ScreenBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <Result status="error" title="Trang chưa tải được" subTitle="Vui lòng tải lại trang để tiếp tục."
    extra={<Button onClick={() => window.location.reload()}>Tải lại</Button>} /> : this.props.children; }
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><ConfigProvider locale={viVN} theme={{
  token: { colorPrimary: '#16675b', colorLink: '#16675b', colorText: '#20352f', colorBgLayout: '#f5f7f6', colorBorder: '#dbe3df',
    borderRadius: 10, fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif', fontSize: 15,
    controlHeight: 44, colorError: '#b42318' }, components: { Button: { primaryShadow: 'none' }, Card: { boxShadow: 'none' },
    Menu: { itemHeight: 44, itemSelectedBg: '#e9f3ef', itemSelectedColor: '#16675b', subMenuItemBg: '#fff' } }
}}><App><ScreenBoundary><Root /><StepUpGate /></ScreenBoundary></App></ConfigProvider></React.StrictMode>);
