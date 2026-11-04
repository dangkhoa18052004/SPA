async page => {
  const base = 'http://127.0.0.1:59151', out = 'output/skin-map-react-2026-10-24';
  const errors = [], failures = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => failures.push(r.url()));
  const assert = (value, message) => { if (!value) throw Error(message); };
  const login = async role => {
    await page.goto(base + '/__preview/login?role=' + role);
    await page.evaluate(async role => {
      localStorage.clear(); sessionStorage.clear();
      const result = await (await fetch('/__preview/login?role=' + role)).json();
      localStorage.setItem('admin_token', result.access_token); localStorage.setItem('admin_role', role);
    }, role);
  };
  const current = () => page.evaluate(async () => (await fetch('/api/admin/skin-service-map', {
    headers: { Authorization: 'Bearer ' + localStorage.getItem('admin_token') }
  })).json());
  await login('admin'); await page.setViewportSize({ width: 1440, height: 1000 });
  const initial = await current();
  await page.evaluate(async serviceId => {
    const response = await fetch('/api/admin/skin-service-map', { method: 'PUT',
      headers: { Authorization: 'Bearer ' + localStorage.getItem('admin_token'), 'Content-Type': 'application/json' },
      body: JSON.stringify({ map: { papule: [serviceId] } }) });
    if (!response.ok) throw Error('Could not reset disposable preview mapping');
  }, initial.services[1].madv);
  await page.goto(base + '/admin/dashboard');
  await page.locator('.admin-sidebar .ant-menu-submenu-title').filter({ hasText: 'Chăm sóc' }).click();
  await page.evaluate(() => { window.__skinMapNavigation = 'same-shell'; });
  await page.locator('.admin-sidebar a[href="/admin/skin-service-map"]').click();
  await page.getByRole('heading', { name: 'Dịch vụ theo loại mụn', exact: true }).waitFor();
  await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).waitFor();
  assert(await page.evaluate(() => window.__skinMapNavigation === 'same-shell'), 'Menu navigation reloaded the page');
  const before = await current();
  assert(await page.locator('[data-testid^="skin-map-"]').count() === 5, 'Five acne types are required');
  assert(await page.locator('.skin-map-cards img,.skin-map-cards script').count() === 0, 'Catalog HTML must be rendered as text');
  await page.getByRole('button', { name: 'Nhờ Gemini đề xuất', exact: true }).click();
  await page.getByText('Đây là bản nháp đề xuất, chưa được lưu và duyệt.', { exact: true }).waitFor();
  assert(JSON.stringify((await current()).map) === JSON.stringify(before.map), 'Proposal must not save');
  assert(await page.getByText('Thêm mới', { exact: true }).count() === 2, 'Proposal additions missing');
  assert(await page.getByText('Sẽ bỏ khi lưu:', { exact: true }).count() === 1, 'Proposal removals missing');
  const papule = page.getByTestId('skin-map-papule');
  const combo = papule.getByRole('combobox');
  await combo.focus(); await combo.press('ArrowDown'); await combo.fill('Chăm sóc da');
  await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option').filter({ hasText: 'Chăm sóc da' }).first().click();
  await combo.press('Escape');
  await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  let confirm = page.getByRole('dialog', { name: 'Lưu và duyệt dịch vụ gợi ý?', exact: true });
  await confirm.getByText('Sẩn viêm: 2 dịch vụ', { exact: true }).waitFor();
  await confirm.getByRole('button', { name: 'Kiểm tra lại', exact: true }).click();
  assert(JSON.stringify((await current()).map) === JSON.stringify(before.map), 'Cancel confirmation must not save');
  await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  confirm = page.getByRole('dialog', { name: 'Lưu và duyệt dịch vụ gợi ý?', exact: true });
  const saved = page.waitForResponse(r => r.url().endsWith('/api/admin/skin-service-map') && r.request().method() === 'PUT');
  await confirm.getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  assert((await saved).status() === 200, 'Save failed');
  await page.getByText('Đã lưu và duyệt dịch vụ gợi ý.', { exact: true }).waitFor();
  await page.reload(); await page.getByText(/Người duyệt: Admin Test/).waitFor();
  assert((await current()).map.papule.length === 2, 'Saved selections did not survive reload');
  await page.screenshot({ path: out + '/react-mapping-desktop.png', fullPage: true });
  checks.push('Same-shell menu, five groups, escaped names, proposal draft/differences, manual edit, confirmation cancel/save and reload');

  await page.route('**/api/admin/skin-service-map/proposal', route => route.fulfill({ status: 502, json: { success: false, message: 'AI thử nghiệm tạm lỗi' } }));
  await page.getByRole('button', { name: 'Nhờ Gemini đề xuất', exact: true }).click();
  await page.getByText('AI thử nghiệm tạm lỗi', { exact: true }).waitFor();
  assert(await papule.locator('.ant-select-selection-item').count() === 2, 'Proposal failure lost the selection');
  await page.unroute('**/api/admin/skin-service-map/proposal');
  await page.route('**/api/admin/skin-service-map', async route => {
    if (route.request().method() === 'PUT') await route.fulfill({ status: 503, json: { success: false, message: 'Chưa lưu được trong kiểm thử' } });
    else await route.continue();
  });
  await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  await page.getByRole('dialog', { name: 'Lưu và duyệt dịch vụ gợi ý?', exact: true }).getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  await page.getByText('Chưa lưu được trong kiểm thử', { exact: true }).waitFor();
  assert(await papule.locator('.ant-select-selection-item').count() === 2, 'Save failure lost the selection');
  await page.unroute('**/api/admin/skin-service-map');
  checks.push('Provider/save errors preserve choices without automatic retries');
  await page.locator('.ant-modal-mask').waitFor({ state: 'hidden' });

  for (const width of [390, 360]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
    await page.screenshot({ path: `${out}/react-mapping-${width}.png`, fullPage: true });
  }
  // Empty approval restores the explicitly configured fallback, with a clear confirmation.
  for (const code of Object.keys(before.types)) {
    const field = page.getByTestId('skin-map-' + code).getByRole('combobox');
    while (await page.getByTestId('skin-map-' + code).locator('.ant-select-selection-item').count()) {
      await field.focus(); await field.press('Backspace');
    }
  }
  await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  confirm = page.getByRole('dialog', { name: 'Lưu và duyệt dịch vụ gợi ý?', exact: true });
  await confirm.getByText(/Danh sách trống sẽ dùng lại danh sách cấu hình ban đầu/).waitFor();
  await confirm.getByRole('button', { name: 'Lưu và duyệt', exact: true }).click();
  await page.getByText('Danh sách cấu hình ban đầu', { exact: true }).waitFor();
  assert((await current()).source === 'env', 'Empty map did not restore configured fallback');
  checks.push('390/360px without overflow and explicit empty approval/fallback');

  await login('manager'); await page.goto(base + '/admin/skin-service-map');
  await page.getByRole('heading', { name: 'Dịch vụ theo loại mụn', exact: true }).waitFor();
  assert(await page.locator('#admin-content').getByRole('button', { name: 'Lưu và duyệt', exact: true }).isEnabled(), 'Manager cannot approve');
  await login('letan');
  let forbiddenReads = 0;
  const countForbidden = request => { if (request.url().endsWith('/api/admin/skin-service-map')) forbiddenReads++; };
  page.on('request', countForbidden);
  await page.goto(base + '/admin/skin-service-map');
  await page.getByText('Bạn không có quyền cấu hình dịch vụ theo loại mụn', { exact: true }).waitFor();
  assert(await page.locator('a[href="/admin/skin-service-map"]').count() === 0, 'Receptionist should not see the menu');
  assert(forbiddenReads === 0, 'Forbidden role fetched mapping data');
  page.off('request', countForbidden);
  assert(errors.length === 0, errors.join('; '));
  assert(failures.length === 0, failures.join('; '));
  checks.push('Manager access and receptionist role gate/menu without forbidden API calls');
  return { checks, pageErrors: errors, failedRequests: failures, expectedHttpErrors: [502, 503] };
}
