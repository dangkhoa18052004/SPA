// P1-06: virtual-keyboard approximation. With the viewport cut to 390x420, a user scroll (wheel, not script)
// must reach each form's submit button and no horizontal overflow may appear.
// usage: node tests/ui-review-run.js tests/ui-review-short-viewport.playwright.js <out>
async (page, {base, out, login, context}) => {
  const forms = [
    ['guest', '/auth/login', 'form button[type=submit]'],
    ['guest', '/auth/register', 'form button[type=submit]'],
    ['guest', '/auth/forgot-password', 'form button[type=submit]'],
    ['guest', '/admin/login', 'button[type=submit]'],
    ['guest', '/admin/login?ui=legacy', '#adminLoginForm button[type=submit]'],
    ['customer', '/profile#password', 'button[type=submit]:has-text("Đổi mật khẩu")'],
  ];
  const rows = [];
  for (const [role, path, submit] of forms) {
    await context.clearCookies();
    await page.setViewportSize({width: 390, height: 420});
    await login(role);
    await page.goto(base + path);
    await page.waitForTimeout(1500);
    const button = page.locator(submit).filter({visible: true}).last();
    const found = await button.count();
    if (!found) { rows.push({path, error: 'submit not found'}); continue; }
    // Focus the first text field like a user opening the keyboard, then scroll with the wheel.
    await page.locator('input:visible').first().focus().catch(() => {});
    await page.mouse.move(195, 210);
    for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 400); await page.waitForTimeout(120); }
    const box = await button.boundingBox();
    const state = await page.evaluate(() => ({overflow: document.documentElement.scrollWidth - innerWidth, scrollY: Math.round(scrollY)}));
    const reachable = !!box && box.y >= 0 && box.y + box.height <= 420;
    rows.push({path, reachable, ...state, buttonY: box && Math.round(box.y)});
    await page.screenshot({path: `${out}/short-${path.replace(/\W+/g, '-')}.png`});
  }
  return rows;
}
