// P1-05 error/permission matrix: unknown routes, unknown IDs, forbidden roles, expired sessions, legacy variants.
// usage: node tests/ui-review-run.js tests/ui-review-errors.playwright.js <out> [label] [who,who...]
// Records per case: document status, final URL, visible title, a way back, main-frame navigations (loop check)
// and successful data API responses while a forbidden page is shown (leak check).
async (page, {base, out, args, browser}) => {
  const label = args[0] || 'run';
  const cases = {
    guest: ['/khong-ton-tai', '/services/99999', '/services/abc', '/packages/99999', '/profile', '/appointments/create',
      '/skin-analysis', '/admin/dashboard', '/admin/khong-ton-tai', '/employee', '/employee/attendance', '/admin/dashboard?ui=legacy',
      '/terms', '/privacy'],
    customer: ['/admin/dashboard', '/admin/reports', '/employee', '/appointments/create?service=99999',
      '/appointments/create?treatment=99999', '/profile#khong-ton-tai', '/admin/customers?ui=legacy'],
    staff: ['/admin/customers', '/admin/reports', '/admin/staff', '/admin/invoices', '/admin/package-sales', '/admin/services',
      '/admin/packages/new', '/admin/salary', '/employee/khong-ton-tai', '/employee/appointments?view=999999',
      '/admin/operations/payroll', '/admin/customers?ui=legacy', '/admin/reports?ui=legacy'],
    letan: ['/admin/reports', '/admin/salary', '/admin/staff', '/admin/roles', '/admin/services', '/admin/packages',
      '/admin/operations/payroll', '/admin/appointments?view=999999', '/admin/reports?ui=legacy', '/admin/packages?ui=legacy'],
    manager: ['/admin/staff', '/admin/roles', '/admin/packages/99999', '/admin/packages/99999/edit', '/admin/appointments?view=999999'],
    admin: ['/admin/khong-ton-tai', '/admin/packages/99999', '/admin/packages/99999/edit',
      '/admin/packages?tab=treatments&mathe=99999', '/admin/operations/khong-ton-tai', '/admin/package-sales?view=999999',
      '/admin/packages/99999?ui=legacy'],
    'expired:staff': ['/admin/dashboard', '/employee/attendance', '/admin/dashboard?ui=legacy'],
    'expired:admin': ['/admin/appointments'],
    'expired:customer': ['/profile', '/appointments/create'],
    'legacy:staff': ['/admin/customers?ui=legacy', '/admin/invoices?ui=legacy', '/admin/services?ui=legacy', '/admin/appointments?ui=legacy'],
    'legacy:letan': ['/admin/services?ui=legacy', '/admin/customers?ui=legacy', '/admin/invoices?ui=legacy'],
  };
  const only = args[1] ? args[1].split(',') : null;
  const rows = [];
  for (const [who, paths] of Object.entries(cases)) {
    if (only && !only.includes(who)) continue;
    for (const width of [390, 1440]) {
      const context = await browser.newContext({viewport: {width, height: 900}});
      await context.route(/img\.vietqr\.io/, r => r.abort());
      const p = await context.newPage();
      const dialogs = [];
      p.on('dialog', d => { dialogs.push(d.message()); d.accept(); });
      await p.goto(base + '/__qa/ping');
      const [mode, role] = who.includes(':') ? who.split(':') : ['login', who];
      await p.evaluate(async ({mode, role}) => {
        localStorage.clear();
        const d = await (await fetch(mode === 'expired' ? '/__qa/expired-token/' + role : '/__qa/login/' + role)).json();
        if (d.access_token) {
          localStorage.setItem(role === 'customer' ? 'access_token' : 'admin_token', d.access_token);
          if (role !== 'customer') localStorage.setItem('admin_role', role);
        }
      }, {mode, role});
      for (const path of paths) {
        dialogs.length = 0;
        let navigations = 0;
        const onNav = f => { if (f === p.mainFrame()) navigations++; };
        const apiOk = [];
        const onResponse = r => {
          const u = new URL(r.url());
          if (u.origin === base && u.pathname.startsWith('/api/') && r.status() < 300 && r.request().method() === 'GET'
            && !/\/api\/(auth|me$|admin\/me|me\/profile|notifications|chat\/unread|config)/.test(u.pathname)) apiOk.push(u.pathname);
        };
        p.on('framenavigated', onNav);
        p.on('response', onResponse);
        let status = null, error = null;
        try {
          const response = await p.goto(base + path);
          status = response?.status() ?? null;
          await p.waitForTimeout(1500);
          await p.waitForFunction(() => !document.querySelector('.ant-skeleton, .ant-spin-spinning'), null, {timeout: 5000}).catch(() => {});
        } catch (e) { error = e.message.split('\n')[0]; }
        p.off('framenavigated', onNav);
        p.off('response', onResponse);
        const state = await p.evaluate(() => {
          const visible = e => e && e.getBoundingClientRect().width > 0;
          const title = [...document.querySelectorAll('.ant-result-title, h1, h2')].filter(visible).map(e => e.textContent.trim()).filter(Boolean)[0] || '';
          const back = [...document.querySelectorAll('a[href], button')].filter(visible).map(e => e.textContent.trim())
            .filter(t => /^(Về|Quay lại|Trang chủ|Đăng nhập|Xem dịch vụ|Xem gói|Bán gói|Kỳ công|Tổng quan)/i.test(t)).slice(0, 3);
          const shell = !!document.querySelector('.ant-layout-sider, .admin-sidebar, nav, header');
          return {title: title.slice(0, 80), back, shell, text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 140)};
        }).catch(e => ({title: '', back: [], text: 'evaluate failed: ' + e.message.slice(0, 80)}));
        const actual = new URL(p.url());
        rows.push({who, width, path, status, actual: actual.pathname + actual.search, navigations, dialogs: [...dialogs], apiOk: [...new Set(apiOk)].slice(0, 6), error, ...state});
        if (width === 390) await p.screenshot({path: `${out}/err-${label}-${who.replace(':', '-')}-${path.replace(/\W+/g, '-')}.png`});
      }
      await context.close();
    }
  }
  return rows;
}
