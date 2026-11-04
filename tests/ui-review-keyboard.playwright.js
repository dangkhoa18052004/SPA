// P1-06 keyboard pass: open overlays with the keyboard, close with Escape, focus must return to the opener.
// usage: node tests/ui-review-run.js tests/ui-review-keyboard.playwright.js <out>
async (page, {base, out, login, context}) => {
  const results = [];
  const active = () => page.evaluate(() => { const e = document.activeElement; return e ? `${e.tagName}|${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30)}` : ''; });
  const visible = sel => page.locator(sel).first().isVisible().catch(() => false);
  // Opens `opener` with Enter, waits for `overlay`, presses Escape and checks overlay gone + focus back on opener.
  const check = async (name, opener, overlay, {width = 390} = {}) => {
    const row = {name, width};
    try {
      await opener.waitFor({timeout: 8000});
      await opener.focus();
      const before = await active();
      await page.keyboard.press('Enter');
      await page.locator(overlay).first().waitFor({state: 'visible', timeout: 5000});
      await page.waitForTimeout(400);
      row.focusInside = await page.evaluate(sel => !!document.activeElement?.closest(sel), overlay);
      await page.screenshot({path: `${out}/kbd-${name}-open.png`});
      await page.keyboard.press('Escape');
      await page.waitForTimeout(600);
      row.closed = !(await visible(overlay));
      row.focusBack = (await active()) === before;
      row.focusAfter = await active();
    } catch (e) { row.error = e.message.split('\n')[0]; }
    results.push(row);
  };
  // Customer pages (390).
  await page.setViewportSize({width: 390, height: 800});
  await login('customer');
  await page.goto(base + '/services');
  await check('services-filter-dialog', page.locator('.catalog-mobile-filter'), '#catalogFilterDialog');
  await page.goto(base + '/');
  await check('customer-mobile-menu', page.locator('#mobileMenuBtn'), '#navMenu.active, #navMenu.open, #navMenu.show');
  await page.goto(base + '/appointments/create');
  await page.locator('.ant-spin-spinning').waitFor({state: 'detached'}).catch(() => {});
  // Pick one service so the summary button is enabled.
  const add = page.getByRole('button', {name: /Chọn dịch vụ/}).first();
  await add.waitFor({timeout: 8000}).catch(() => {});
  if (await add.count()) { await add.focus(); await page.keyboard.press('Enter'); }
  await check('booking-summary-dialog', page.getByTestId('booking-summary-open'), '.booking-summary-dialog[open]');
  // Admin (390 and 1440).
  await context.clearCookies();
  await login('admin');
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 900});
    await page.goto(base + '/admin/appointments');
    if (width === 390) await check('admin-shell-menu', page.getByRole('button', {name: /menu/i}).first(), '.ant-drawer-open', {width});
    await check(`admin-appointment-view-${width}`, page.getByRole('button', {name: /^Xem chi tiết lịch/}).first(), '.ant-drawer-open', {width});
    await check(`admin-create-appointment-${width}`, page.getByRole('button', {name: /Tạo lịch hẹn/}).first(), '.ant-drawer-open', {width});
    await page.goto(base + '/admin/customers');
    await check(`admin-customer-view-${width}`, page.getByRole('button', {name: 'Hồ sơ', exact: true}).first(), '.ant-drawer-open, .ant-modal-wrap', {width});
  }
  // Staff portal account menu (390).
  await context.clearCookies();
  await login('staff');
  await page.setViewportSize({width: 390, height: 800});
  await page.goto(base + '/employee/attendance');
  await check('employee-account-menu', page.getByRole('button', {name: /Tài khoản/}).first(), '.ant-dropdown:not(.ant-dropdown-hidden)');
  return results;
}
