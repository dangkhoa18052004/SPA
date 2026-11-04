// UI-012: legacy /admin/login must not widen the page and must scroll when the viewport is short (virtual keyboard).
// usage: node tests/ui-review-run.js tests/ui-review-admin-login.playwright.js <out> <label>
async (page, {base, out, args}) => {
  const label = args[0] || 'check';
  const rows = [];
  for (const [width, height] of [[360, 640], [390, 900], [390, 420], [768, 1024], [1440, 900]]) {
    await page.setViewportSize({width, height});
    await page.goto(base + '/admin/login?ui=legacy');
    await page.locator('#adminLoginForm button[type=submit]').waitFor();
    await page.waitForTimeout(900); // entry animations
    const cardTop = await page.locator('.admin-login-container').evaluate(e => Math.round(e.getBoundingClientRect().top + scrollY));
    // A user (not script) scroll: the wheel must be able to reach the submit button on a short viewport.
    await page.mouse.move(width / 2, height / 2);
    await page.mouse.wheel(0, 1200);
    await page.waitForTimeout(300);
    const state = await page.evaluate(() => {
      const button = document.querySelector('#adminLoginForm button[type=submit]').getBoundingClientRect();
      return {scrollWidth: document.documentElement.scrollWidth, innerWidth, innerHeight, scrollY,
        submitVisible: button.top >= 0 && button.bottom <= innerHeight, submitBottom: Math.round(button.bottom)};
    });
    state.cardTop = cardTop;
    rows.push({width, height, ...state});
    await page.screenshot({path: `${out}/ui012-admin-login-${label}-${width}x${height}.png`});
  }
  const bad = rows.filter(r => r.scrollWidth > r.innerWidth + 1 || !r.submitVisible || r.cardTop < 0);
  if (label === 'after' && bad.length) throw new Error('admin login layout: ' + JSON.stringify(bad));
  return rows;
}
