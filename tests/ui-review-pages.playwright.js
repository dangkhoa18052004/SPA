async page => {
  const base = 'http://127.0.0.1:5091';
  const role = new URL(page.url()).searchParams.get('role') || 'admin';
  const legacy = new URL(page.url()).searchParams.get('legacy') === '1';
  const outDir = new URL(page.url()).searchParams.get('out') || 'output/ui-review-2026-10-21';
  const results = [], errors = [], consoleErrors = [];
  const onError = e => errors.push({ url: page.url(), message: e.message });
  const onConsole = m => { if (m.type() === 'error') consoleErrors.push({ url: page.url(), text: m.text().slice(0, 200) }); };
  page.on('pageerror', onError);
  page.on('console', onConsole);
  await page.goto(base + '/__qa/ping');
  await page.evaluate(async role => {
    localStorage.clear();
    const d = await (await fetch('/__qa/login/' + role)).json();
    if (d.access_token) {
      localStorage.setItem(role === 'customer' ? 'access_token' : 'admin_token', d.access_token);
      if (role !== 'customer') localStorage.setItem('admin_role', d.role);
    }
  }, role);
  const publicPages = ['/', '/services', '/services/1', '/packages', '/packages/1', '/appointments/create', '/skin-analysis'];
  const employee = ['attendance', 'appointments', 'schedule', 'history', 'income', 'account'].map(p => '/employee/' + p);
  const admin = ['dashboard', 'appointments', 'customers', 'invoices', 'package-sales', 'packages', 'packages/new', 'packages/1', 'packages/1/edit', 'services', 'staff', 'roles', 'shifts', 'approve-shifts', 'my-schedule', 'register-shift', 'salary', 'my-salary', 'loyalty', 'reviews', 'chat', 'crm', 'reports', 'profile', 'security'].map(p => '/admin/' + p);
  const ops = ['dashboard', 'attendance', 'adjustments', 'payroll', 'branches', 'audit'].map(p => '/admin/operations/' + p);
  const paths = role === 'guest' ? [...publicPages, '/auth/login', '/auth/register', '/auth/forgot-password', '/auth/verify-otp', '/auth/reset-password', '/admin/login']
    : role === 'customer' ? [...publicPages, ...['info','appointments','treatments','invoices','loyalty','reviews','communication','edit','password'].map(p=>'/profile#'+p)]
    : role === 'staff' ? ['/employee', ...employee, '/admin/dashboard', '/admin/packages', '/admin/profile', '/admin/chat', '/admin/security']
    : role === 'letan' ? ['dashboard','appointments','customers','invoices','package-sales','my-schedule','register-shift','loyalty','chat','crm','profile','security'].map(p=>'/admin/'+p)
    : role === 'manager' ? [...admin.filter(p=>!['/admin/staff','/admin/roles'].includes(p)), '/admin/operations', ...ops]
    : [...admin, '/admin/operations', ...ops];
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of paths) {
      const failed = [];
      const track = r => { if (r.status() >= 400 && new URL(r.url()).origin === base) failed.push({ url: new URL(r.url()).pathname, status: r.status() }); };
      page.on('response', track);
      try {
        const url = new URL(base + path);
        if (legacy) url.searchParams.set('ui','legacy');
        const response = await page.goto(url.href);
        await page.locator('main, .admin-content, .auth-container, body').first().waitFor();
        await page.waitForTimeout(450);
        // Wait for loading placeholders instead of screenshotting a skeleton.
        await page.waitForFunction(() => !document.querySelector('.ant-skeleton, .ant-spin-spinning, .skeleton, [aria-busy="true"]'), null, { timeout: 6000 }).catch(() => {});
        const state = await page.evaluate(() => ({
          title: document.title,
          headings: [...document.querySelectorAll('h1')].map(e => e.textContent.trim()),
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
          overflowing: [...document.querySelectorAll('main *, .admin-main *')].filter(e => {
            const r=e.getBoundingClientRect(); return r.width && (r.right>innerWidth+2 || r.left < -2) && getComputedStyle(e).position!=='fixed';
          }).slice(0,5).map(e=>({tag:e.tagName,cls:typeof e.className==='string'?e.className:'',text:e.textContent.slice(0,70)})),
          unnamedButtons: [...document.querySelectorAll('button')].filter(e => e.getBoundingClientRect().width && !e.textContent.trim() && !e.getAttribute('aria-label') && !e.getAttribute('title')).length,
          brokenImages: [...document.images].filter(e=>e.complete && !e.naturalWidth && e.getBoundingClientRect().width).map(e=>e.getAttribute('src')),
          text: document.body.innerText.slice(0,180)
        }));
        results.push({role,width,path,status:response?.status() ?? 200,actual:new URL(page.url()).pathname,...state,failed});
        await page.screenshot({ path:`${outDir}/${legacy?'legacy-':''}${role}-${width}-${path.replace(/\W+/g,'-')||'home'}.png`,fullPage:true });
      } catch (e) { results.push({role,width,path,error:e.message}); }
      page.off('response',track);
    }
  }
  page.off('pageerror', onError);
  page.off('console', onConsole);
  return {role,legacy,results,errors,consoleErrors};
}
