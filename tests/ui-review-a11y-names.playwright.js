// P1-06: buttons/links whose computed accessible name is empty (the page scanner only reads text/aria-label).
// usage: node tests/ui-review-run.js tests/ui-review-a11y-names.playwright.js <out>
async (page, {base, login, context}) => {
  const plan = {
    guest: ['/', '/services', '/packages', '/auth/login', '/auth/register', '/auth/reset-password', '/auth/forgot-password'],
    customer: ['/', '/services/1', '/packages/1', '/appointments/create', '/profile'],
    admin: ['/admin/dashboard', '/admin/appointments', '/admin/customers', '/admin/services', '/admin/packages', '/admin/invoices',
      '/admin/package-sales', '/admin/staff', '/admin/chat', '/admin/reviews', '/admin/reports', '/admin/loyalty'],
    staff: ['/employee/attendance', '/employee/appointments', '/admin/packages'],
    'admin:legacy': ['dashboard', 'appointments', 'customers', 'invoices', 'package-sales', 'packages', 'services', 'staff',
      'shifts', 'approve-shifts', 'salary', 'loyalty', 'reviews', 'chat', 'profile', 'login'].map(p => `/admin/${p}?ui=legacy`),
    'customer:legacy': ['/', '/services', '/packages', '/appointments/create', '/profile'].map(p => p + '?ui=legacy'),
  };
  const rows = [];
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 900});
    for (const [role, paths] of Object.entries(plan)) {
      await context.clearCookies();
      await login(role.split(':')[0]);
      for (const path of paths) {
        await page.goto(base + path);
        await page.waitForTimeout(1500);
        const cdp = await context.newCDPSession(page);
        const {nodes} = await cdp.send('Accessibility.getFullAXTree');
        await cdp.detach();
        const unnamed = [];
        for (const n of nodes) {
          const r = n.role?.value;
          if (n.ignored || !['button', 'link', 'combobox', 'textbox', 'checkbox', 'radio'].includes(r)) continue;
          // Icon fonts expose private-use glyphs from ::before as a "name"; screen readers cannot read them.
          if ((n.name?.value || '').replace(/[\uE000-\uF8FF]/g, '').trim()) continue;
          // Describe the DOM node so it can be located.
          let desc = '';
          if (n.backendDOMNodeId) {
            const c2 = await context.newCDPSession(page);
            try {
              const {object} = await c2.send('DOM.resolveNode', {backendNodeId: n.backendDOMNodeId});
              const {result} = await c2.send('Runtime.callFunctionOn', {objectId: object.objectId, returnByValue: true,
                functionDeclaration: 'function(){const r=this.getBoundingClientRect();return r.width&&r.height?this.outerHTML.slice(0,160):""}'});
              desc = result.value;
            } catch (e) { desc = ''; } finally { await c2.detach(); }
          }
          if (desc) unnamed.push({role: r, html: desc});
        }
        rows.push({width, who: role, path, unnamed});
      }
    }
  }
  return rows.filter(r => r.unnamed.length);
}
