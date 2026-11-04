// P1-06 visual pass for key flows at 360/390/768/1024/1440: screenshots + measurable checks.
// Checks per page: horizontal overflow, fixed bottom bars covering the last content, first Tab focus visible,
// text contrast below 4.5:1 on solid backgrounds (gradients/images skipped and reported as such).
// usage: node tests/ui-review-run.js tests/ui-review-visual.playwright.js <out> [label] [widths]
async (page, {base, out, args, login, context}) => {
  const label = args[0] || 'visual';
  const widths = (args[1] || '360,390,768,1024,1440').split(',').map(Number);
  const plan = {
    guest: ['/', '/services', '/packages', '/auth/login', '/auth/register'],
    customer: ['/appointments/create', '/profile#appointments', '/profile#treatments', '/profile#loyalty'],
    admin: ['/admin/dashboard', '/admin/appointments', '/admin/package-sales', '/admin/customers', '/admin/packages?tab=treatments'],
    letan: ['/admin/invoices'],
    staff: ['/employee/attendance', '/employee/appointments', '/admin/dashboard'],
  };
  const rows = [];
  for (const [role, paths] of Object.entries(plan)) {
    await context.clearCookies();
    await login(role);
    for (const width of widths) {
      await page.setViewportSize({width, height: width < 768 ? 800 : 900});
      for (const path of paths) {
        await page.goto(base + path);
        await page.waitForTimeout(1200);
        await page.waitForFunction(() => !document.querySelector('.ant-skeleton, .ant-spin-spinning'), null, {timeout: 6000}).catch(() => {});
        const state = await page.evaluate(() => {
          const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const [r, g, b, a = 1] = m[1].split(',').map(Number); return {r, g, b, a}; };
          const lum = ({r, g, b}) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const background = el => {
            for (let e = el; e; e = e.parentElement) {
              const s = getComputedStyle(e);
              if (s.backgroundImage !== 'none') return null; // gradient/image: cannot compute reliably
              const c = parse(s.backgroundColor);
              if (c && c.a >= 0.95) return c;
            }
            return {r: 255, g: 255, b: 255, a: 1};
          };
          const lowContrast = [];
          for (const el of document.querySelectorAll('body *')) {
            if (lowContrast.length >= 8) break;
            const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
            if (!own) continue;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            if (!r.width || !r.height || s.visibility === 'hidden' || +s.opacity < 0.1 || r.bottom < 0 || r.top > innerHeight * 3) continue;
            if (el.closest('[disabled], .ant-btn-disabled, [aria-disabled="true"], .ant-select-selection-placeholder, input, textarea')) continue;
            const fg = parse(s.color), bg = background(el);
            if (!fg || !bg) continue;
            const [l1, l2] = [lum(fg), lum(bg)].sort((a, b) => b - a);
            const ratio = (l1 + 0.05) / (l2 + 0.05);
            const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700);
            if (ratio < (large ? 3 : 4.5)) lowContrast.push({text: el.textContent.trim().slice(0, 40), ratio: +ratio.toFixed(2), color: s.color, cls: String(el.className).slice(0, 40)});
          }
          // Fixed bars at the bottom: does the end of the page stay reachable above them?
          const bars = [...document.querySelectorAll('body *')].filter(e => {
            const s = getComputedStyle(e), r = e.getBoundingClientRect();
            return s.position === 'fixed' && r.height > 30 && r.height < 160 && r.width > innerWidth * 0.6 && Math.abs(r.bottom - innerHeight) < 2 && s.visibility !== 'hidden' && s.display !== 'none';
          });
          return {overflow: document.documentElement.scrollWidth - innerWidth, lowContrast, bars: bars.map(b => Math.round(b.getBoundingClientRect().height)),
            bodyPad: getComputedStyle(document.body).paddingBottom, scrollHeight: document.documentElement.scrollHeight};
        });
        // Scroll to the very end and check that the last visible content is not hidden behind a fixed bar.
        let covered = null;
        if (state.bars.length) {
          await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
          await page.waitForTimeout(250);
          covered = await page.evaluate(() => {
            const bar = [...document.querySelectorAll('body *')].find(e => { const s = getComputedStyle(e), r = e.getBoundingClientRect(); return s.position === 'fixed' && r.height > 30 && r.height < 160 && r.width > innerWidth * 0.6 && Math.abs(r.bottom - innerHeight) < 2; });
            const top = bar.getBoundingClientRect().top;
            const hidden = [...document.querySelectorAll('main a, main button, main input, footer a, .ant-pagination, main p')].filter(e => {
              const r = e.getBoundingClientRect(); return r.width && r.height && !bar.contains(e) && r.bottom > top + 2 && r.top < innerHeight && getComputedStyle(e).position !== 'fixed' && !e.closest('[style*="position: fixed"]');
            });
            return hidden.slice(0, 3).map(e => (e.textContent || e.tagName).trim().slice(0, 30));
          });
          await page.evaluate(() => scrollTo(0, 0));
        }
        // First Tab: visible focus indicator (outline or box-shadow) on the focused element.
        await page.keyboard.press('Tab');
        const focusInfo = await page.evaluate(() => {
          const e = document.activeElement; if (!e || e === document.body) return {el: 'body', visible: false};
          const s = getComputedStyle(e);
          return {el: `${e.tagName}.${String(e.className).slice(0, 30)} ${(e.textContent || '').trim().slice(0, 20)}`, visible: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none'};
        });
        const name = `${label}-${role}-${width}-${path.replace(/\W+/g, '-')}`;
        await page.screenshot({path: `${out}/${name}.png`, fullPage: width <= 390});
        rows.push({role, width, path, ...state, covered, focus: focusInfo});
      }
    }
  }
  return rows;
}
