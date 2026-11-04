// P1-01 follow-up: package-sale history beyond the API page of 200 (isolated 5091 fixture; creates pending cash receipts).
// usage: node tests/ui-review-run.js tests/ui-review-history-paging.playwright.js <out>
async (page, {base, out, login}) => {
  const assert = (v, m) => { if (!v) throw Error(m); };
  await login('admin');
  const token = await page.evaluate(() => localStorage.getItem('admin_token'));
  const call = async (path, method = 'GET', data) => (await page.request.fetch(base + path, {method, data, headers: {Authorization: 'Bearer ' + token}})).json();
  const makh = (await call('/api/admin/package-sales/customers?search=0900000099')).customers[0].makh;
  let total = (await call('/api/admin/package-sales')).purchases.length;
  for (let first = await call('/api/admin/package-sales'); !first.has_more; first = await call('/api/admin/package-sales')) {
    await Promise.all(Array.from({length: 20}, () => call('/api/admin/package-sales', 'POST', {makh, magoi: 4, payment_method: 'cash'})));
  }
  const all = [];
  for (let cursor = null; ;) {
    const page_ = await call('/api/admin/package-sales' + (cursor ? '?before_id=' + cursor : ''));
    all.push(...page_.purchases);
    if (!page_.has_more) break;
    cursor = page_.next_before_id;
  }
  total = all.length;
  const results = [];
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 900});
    await page.goto(base + '/admin/package-sales');
    const more = page.getByRole('button', {name: /Tải thêm phiếu cũ hơn/});
    await more.waitFor({timeout: 15000});
    const label = await more.innerText();
    assert(label.includes('200 phiếu'), 'button shows the loaded count: ' + label);
    await more.click();
    await more.waitFor({state: 'detached', timeout: 15000});
    // Last pagination page must contain the oldest receipt.
    const pager = page.locator('.ant-pagination').first();
    await pager.locator('.ant-pagination-item').last().click();
    const oldest = all.at(-1).receipt_code;
    await page.getByText(oldest, {exact: true}).filter({visible: true}).first().waitFor();
    await page.screenshot({path: `${out}/history-oldest-${width}.png`, fullPage: width < 768});
    results.push({width, before: label, oldest});
  }
  // Legacy page tells the user that only the newest 200 are listed.
  await page.goto(base + '/admin/package-sales?ui=legacy');
  await page.getByText('Đang hiển thị 200 phiếu mới nhất').waitFor({timeout: 15000});
  await page.screenshot({path: `${out}/history-legacy-notice-1440.png`});
  return {total, results};
}
