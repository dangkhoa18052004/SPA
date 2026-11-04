async page => {
  const base = 'http://127.0.0.1:59147', out = 'output/voucher-completion-2026-10-24';
  const checks = [], errors = [], failures = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => failures.push(r.url()));
  const assert = (value, message) => { if (!value) throw Error(message); };
  const call = (path, method = 'GET', body) => page.evaluate(async ([path, method, body]) => {
    const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + localStorage.getItem('admin_token') }, ...(body ? { body: JSON.stringify(body) } : {}) });
    return { status: response.status, data: await response.json() };
  }, [path, method, body]);
  const login = async role => {
    await page.goto(base + '/__qa/ping');
    await page.evaluate(async role => { localStorage.clear(); const d = await (await fetch('/__qa/login/' + role)).json(); localStorage.setItem('admin_token', d.access_token); localStorage.setItem('admin_role', role); }, role);
  };
  const pick = async (dialog, name) => {
    const search = dialog.getByRole('searchbox', { name: 'Tìm mẫu voucher', exact: true });
    await search.fill(name);
    const loaded = page.waitForResponse(r => r.url().includes('/gift-templates?') && r.url().includes('search=') && !r.url().endsWith('search='));
    await search.press('Enter'); await loaded;
    const combo = dialog.getByRole('combobox', { name: 'Mẫu voucher', exact: true });
    await combo.fill(name); await combo.press('ArrowDown');
    await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option').filter({ hasText: name }).first().click();
  };
  await login('admin'); await call('/__qa/mode/react');
  for (const mode of ['react', 'legacy']) {
    await call('/__qa/mode/' + mode);
    await page.setViewportSize({ width: mode === 'react' ? 1440 : 390, height: 1000 });
    await page.goto(base + '/admin/loyalty?tab=rewards');
    if (mode === 'react') await page.getByRole('button', { name: 'Thêm quà / voucher', exact: true }).click();
    else { await page.locator('[data-tab=rewards]').click(); await page.locator('[data-new]').click(); }
    const editor = mode === 'react' ? page.getByRole('dialog', { name: 'Thêm quà hoặc voucher', exact: true }) : page.locator('#rewardForm');
    const field = name => editor.locator(mode === 'react' ? '#' + name : `[name=${name}]`);
    await field('name').fill('Welcome inactive ' + mode + ' ' + Date.now());
    if (mode === 'react') { await field('for_new_customers').click(); await field('active').click(); }
    else { await field('for_new_customers').check(); await field('active').uncheck(); }
    await field('reward_value').fill('50000'); await field('validity_days').fill('30');
    await page.screenshot({ path: `${out}/${mode}-new-customer-editor.png`, fullPage: false });
    const save = page.waitForResponse(r => r.url().endsWith('/api/admin/loyalty/rewards') && r.request().method() === 'POST');
    await editor.getByRole('button', { name: 'Lưu quà', exact: true }).click();
    const response = await save, reward = (await response.json()).reward;
    assert(response.status() === 201 && reward.active === false, mode + ': save inactive welcome');
    const config = (await call('/api/admin/loyalty/welcome-config')).data.config;
    assert(config.enabled && config.reward_id === reward.id, mode + ': welcome configured in normal editor');
    const username = 'inactive-' + mode + '-' + Date.now();
    assert((await call('/api/auth/register', 'POST', { taikhoan: username, matkhau: 'password123', hoten: 'QA', email: username + '@example.test', sdt: '09' + String(Date.now()).slice(-8) })).status === 201, mode + ': register');
    // Read OTP from the isolated fixture's database through its registration endpoint.
    const otp = (await call('/__qa/registration?account=' + username)).data.otp;
    const activated = await call('/api/auth/verify-otp', 'POST', { otp_code: otp });
    assert(activated.status === 200 && activated.data.welcome_voucher.issued, mode + ': inactive template still welcomes');
    await page.goto(base + '/admin/customers');
    // Existing test customer is identified by ID, without depending on translated names.
    const customerRow = mode === 'react' ? page.locator('.desktop-table .ant-table-row').filter({ has: page.getByText('#1', { exact: true }) }) : page.locator('#customers-table tbody tr').filter({ has: page.getByText('#1', { exact: true }) });
    await customerRow.getByRole('button', { name: 'Tặng voucher', exact: true }).click();
    let dialog = mode === 'react' ? page.getByRole('dialog', { name: 'Tặng voucher', exact: true }) : page.locator('[data-dialog]');
    await dialog.waitFor();
    if (mode === 'react') { await pick(dialog, reward.name); await dialog.getByLabel('Lý do nội bộ', { exact: true }).fill('QA inactive template'); }
    else { await dialog.locator('[name=search]').fill(reward.name); await dialog.getByRole('button', { name: 'Tìm mẫu', exact: true }).click(); await dialog.locator(`[name=reward_id] option[value="${reward.id}"]`).waitFor({ state: 'attached' }); await dialog.locator('[name=reward_id]').selectOption(String(reward.id)); await dialog.locator('[name=reason]').fill('QA inactive template'); }
    await page.screenshot({ path: `${out}/${mode}-direct-gift.png`, fullPage: false });
    const sent = page.waitForResponse(r => r.url().endsWith('/voucher-gifts') && r.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Xác nhận tặng 1 voucher', exact: true }).click();
    const gifted = await sent; assert(gifted.status() === 201, mode + ': gift inactive welcome manually');
    await dialog.waitFor({ state: 'hidden' });
    const issued = (await gifted.json()).redemption;
    assert(issued.reward_id === reward.id, mode + ': selected the intended inactive template');
    const rid = issued.id;
    assert((await call('/api/admin/invoices/1/reward', 'POST', { redemption_id: rid })).status === 200, mode + ': apply inactive voucher');
    assert((await call('/api/admin/invoices/1/reward', 'DELETE')).status === 200, mode + ': release inactive voucher');
    checks.push(mode + ': normal editor welcome flag, inactive OTP issuance, list gift action, inactive gift apply/release');
  }
  await login('letan'); await call('/__qa/mode/react'); await page.setViewportSize({ width: 360, height: 844 });
  await page.goto(base + '/admin/customers');
  // Select the first active customer on mobile; each gift dialog must name that recipient.
  await page.locator('.mobile-cards').getByRole('button', { name: 'Tặng voucher', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Tặng voucher', exact: true }); await dialog.waitFor();
  await dialog.getByRole('searchbox', { name: 'Tìm mẫu voucher' }).fill('NO_MATCH_QA');
  await dialog.getByRole('searchbox', { name: 'Tìm mẫu voucher' }).press('Enter');
  await dialog.getByText('Không có mẫu voucher phù hợp để tặng', { exact: true }).waitFor();
  assert(await dialog.getByRole('button', { name: 'Xác nhận tặng 1 voucher', exact: true }).isDisabled(), 'No empty gift submission');
  assert(await dialog.getByRole('link', { name: 'Quản lý mẫu voucher' }).count() === 0, 'Receptionist gets guidance without management link');
  assert(await dialog.evaluate(el => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; }), 'Mobile gift fits viewport');
  await page.screenshot({ path: out + '/receptionist-empty-360.png', fullPage: false });
  checks.push('Receptionist mobile list action, empty-template guidance and disabled submit');
  assert(errors.length === 0, 'Page errors: ' + errors.join('; '));
  assert(failures.length === 0, 'Failed requests: ' + failures.join('; '));
  return { checks, pageErrors: errors, failedRequests: failures };
}
