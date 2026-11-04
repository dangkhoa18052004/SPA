async page => {
  const base = 'http://127.0.0.1:59150', out = 'output/ai-errors-2026-10-24';
  const errors = [], failures = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => failures.push(r.url()));
  const assert = (value, message) => { if (!value) throw Error(message); };
  const login = async role => {
    await page.goto(base + '/api/ai/status');
    await page.evaluate(async role => {
      localStorage.clear(); const d = await (await fetch('/__qa/login/' + role)).json();
      localStorage.setItem(role === 'customer' ? 'access_token' : 'admin_token', d.access_token);
      if (role !== 'customer') localStorage.setItem('admin_role', 'admin');
    }, role);
  };
  await login('admin'); await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base + '/admin/dashboard');
  const panel = page.locator('#ai-summary-panel');
  await panel.getByRole('button', { name: 'Tạo tóm tắt cho khoảng đang xem', exact: true }).click();
  await panel.getByText(/Chưa tạo được tóm tắt kinh doanh vì AI phản hồi quá chậm/).waitFor();
  assert(!(await panel.innerText()).includes('Đặt lịch'), 'Business error must not refer to booking');
  await panel.scrollIntoViewIfNeeded();
  await page.screenshot({ path: out + '/business-timeout-context.png' });
  await page.goto(base + '/admin/skin-service-map');
  await page.getByText(/Cấu hình gợi ý dịch vụ chưa được cập nhật/).waitFor();
  assert(await page.getByRole('button', { name: 'Lưu và duyệt', exact: true }).isDisabled(), 'Missing schema blocks save with explanation');
  await page.screenshot({ path: out + '/mapping-readiness.png' });
  await login('customer'); await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base + '/skin-analysis');
  await page.locator('#skinHistoryToggle').click();
  await page.locator('[data-open="1"]').click();
  await page.locator('#skinRecs').getByText(/Hiện chưa có dịch vụ được Bin Spa chọn sẵn/).waitFor();
  assert(await page.locator('#skinRecs .is-error').count() === 0, 'Missing mapping is an empty state, not a retryable server error');
  await page.locator('#skinRecs').scrollIntoViewIfNeeded();
  await page.screenshot({ path: out + '/recommendations-empty-mobile.png' });
  assert(errors.length === 0, errors.join('; '));
  assert(failures.length === 0, failures.join('; '));
  return { checks: ['business timeout has business context', 'missing schema clearly blocks mapping save', 'skin recommendations missing mapping remains readable'], pageErrors: errors, failedRequests: failures };
}
