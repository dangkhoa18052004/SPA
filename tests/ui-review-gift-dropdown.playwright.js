// UI-016 investigation: after a rejected gift submit, does the "Dịch vụ tặng" dropdown reopen and cover "Số buổi"?
// Real clicks/keys only (no force). Isolated fixture with --payments not required.
// usage: node tests/ui-review-run.js tests/ui-review-gift-dropdown.playwright.js <out> <label>
async (page, {base, out, args, login}) => {
  const label = args[0] || 'check';
  const assert = (v, m) => { if (!v) throw Error(m); };
  await login('admin');
  const call = (path, method = 'GET', body) => page.evaluate(async ([path, method, body]) => {
    const r = await fetch(path, {method, headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + localStorage.getItem('admin_token')}, body: body ? JSON.stringify(body) : undefined});
    return {status: r.status, data: await r.json().catch(() => ({}))};
  }, [path, method, body]);
  const qa = body => page.evaluate(async body => (await fetch('/__qa/state', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json(), body);
  const makh = (await call('/api/admin/package-sales/customers?search=0900000002')).data.customers[0].makh;
  const sale = await call('/api/admin/package-sales', 'POST', {makh, magoi: 2, payment_method: 'cash'});
  const paid = await call(`/api/admin/packages/purchases/${sale.data.purchase.id}/confirm-payment`, 'POST', {cash_received: sale.data.purchase.payable_amount});
  assert(paid.data.mathe, 'treatment created');
  const services = (await call('/api/admin/packages/treatments/' + paid.data.mathe)).data.services;
  const svc = services.find(s => s.tendv.startsWith('Dịch vụ 09'));
  const open = () => page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').count();
  const focus = () => page.evaluate(() => { const e = document.activeElement; return e ? `${e.tagName}#${e.id}.${String(e.className).slice(0, 40)}` : ''; });
  const rows = [];
  for (const [width, how] of [[1440, 'mouse'], [390, 'mouse'], [1440, 'keyboard'], [1440, 'fast'], [390, 'fast']]) {
    await page.setViewportSize({width, height: 900});
    await page.goto(base + `/admin/packages?tab=treatments&mathe=${paid.data.mathe}&gift=1`);
    const modal = page.locator('.ant-modal').filter({hasText: 'Tặng dịch vụ'});
    await modal.waitFor();
    const box = modal.getByRole('combobox', {name: 'Dịch vụ tặng', exact: true});
    if (how !== 'keyboard') {
      await box.click();
      await box.fill('Dịch vụ 09');
      const id = await box.getAttribute('aria-controls');
      await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').filter({has: page.locator(`[id="${id}"]`)})
        .locator('.ant-select-item-option').filter({hasText: 'Dịch vụ 09 massage trong tên'}).click();
    } else {
      await box.focus();
      await page.keyboard.type('Dịch vụ 09');
      await page.waitForTimeout(200);
      await page.keyboard.press('Enter');
    }
    if (how !== 'fast') await page.waitForTimeout(400); // 'fast': submit while the list is still closing
    const afterPick = {open: await open(), focus: await focus()};
    await qa({service: svc.madv, active: false});
    try {
      const sent = page.waitForResponse(r => /\/gifts$/.test(r.url()) && r.request().method() === 'POST');
      if (how !== 'keyboard') await modal.getByRole('button', {name: 'Xác nhận tặng', exact: true}).click();
      else { await page.keyboard.press('Tab'); await page.keyboard.press('Enter'); } // focus to Số buổi, Enter submits
      const response = await sent;
      await modal.getByRole('alert').filter({hasText: 'ngừng hoạt động'}).waitFor();
      // Sample right after the error appears: a reopening dropdown may only show for an animation frame or two.
      const timeline = [];
      for (let t = 0; t <= 1000; t += 100) {
        const visible = await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').evaluateAll(ds => ds.map(d => getComputedStyle(d).opacity).join(','));
        timeline.push(`${t}:${visible || '-'}`);
        await page.waitForTimeout(100);
      }
      const quantity = await modal.getByLabel('Số buổi').boundingBox();
      const dropdown = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)');
      const dropBox = (await dropdown.count()) ? await dropdown.first().boundingBox() : null;
      const covers = !!(dropBox && quantity && dropBox.y < quantity.y + quantity.height && dropBox.y + dropBox.height > quantity.y);
      const afterError = {open: await open(), focus: await focus()};
      // Keyboard users continue from where focus is: the next Tab must stay inside the dialog.
      await page.keyboard.press('Tab');
      afterError.tabInsideModal = await page.evaluate(() => !!document.activeElement?.closest('.ant-modal'));
      afterError.tabFocus = await focus();
      rows.push({width, how, status: response.status(), afterPick, timeline: timeline.join(' '), afterError, coversQuantity: covers});
      await page.screenshot({path: `${out}/ui016-gift-error-${label}-${how}-${width}.png`});
      await modal.getByRole('button', {name: 'Hủy', exact: true}).click();
    } finally { await qa({service: svc.madv, active: true}); }
  }
  if (label === 'after') assert(rows.every(r => !r.coversQuantity && !r.afterError.open), 'dropdown still reopens: ' + JSON.stringify(rows));
  return rows;
}
