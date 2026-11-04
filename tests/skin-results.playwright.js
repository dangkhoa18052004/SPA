async page => {
  const base = 'http://127.0.0.1:59152', out = 'output/skin-results-2026-10-24';
  const errors = [], failures = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => failures.push(r.url()));
  let recommendationRequests = 0;
  page.on('request', r => { if (/\/skin-analyses\/\d+\/recommendations$/.test(r.url())) recommendationRequests++; });
  const assert = (condition, message) => { if (!condition) throw Error(message); };
  const expected = data => data.lesions.slice().sort((a, b) => (b.probability ?? -1) - (a.probability ?? -1) || a.id - b.id).map(l => l.id);
  await page.goto(base + '/__preview/session?customer=1');
  await page.evaluate(() => sessionStorage.removeItem('skin-analysis-recommendation:v1'));
  await page.locator('#skinForm').waitFor();
  const encoded = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = 600; canvas.height = 800;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#debb9c'; ctx.fillRect(0, 0, 600, 800);
    ctx.fillStyle = '#bb9278'; ctx.fillRect(200, 200, 150, 300);
    return canvas.toDataURL('image/jpeg').split(',')[1];
  });
  const analyze = async mode => {
    await page.evaluate(mode => fetch('/__preview/mode?ai=' + mode + '&gemini=ok'), mode);
    await page.locator('#skinFile').setInputFiles({ name: 'synthetic.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(encoded, 'base64') });
    await page.locator('#skinConsent').check();
    const response = page.waitForResponse(r => r.url().endsWith('/api/me/skin-analyses') && r.request().method() === 'POST');
    await page.locator('#skinSubmit').click();
    const data = (await (await response).json()).data;
    await page.locator('#skinResult').waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.querySelector('#skinSubmit').disabled);
    return data;
  };
  const shown = () => page.locator('#skinHighlights [data-select]').evaluateAll(nodes => nodes.map(n => Number(n.dataset.select)));
  await page.setViewportSize({ width: 1440, height: 1000 });
  const demo = await analyze('demo');
  assert((await shown()).join() === expected(demo).slice(0, 8).join(), 'Demo overview must show the top 8 actual points');
  assert(await page.locator('#skinBanner').isHidden(), 'Trial banner must be removed');
  assert(!(await page.locator('#skinResult').innerText()).includes('Chưa đủ độ tin cậy để xác định loại.'), 'Old empty message must be removed');
  const layout = await page.evaluate(() => ({ image: document.querySelector('#skinFigure').getBoundingClientRect().right, results: document.querySelector('.skin-highlights').getBoundingClientRect().left }));
  assert(layout.results > layout.image, 'Desktop results must be on the right of the image');
  const first = expected(demo)[0];
  await page.locator(`#skinHighlights [data-select="${first}"]`).click();
  assert(await page.locator('#skinBoxes g.is-selected').count() === 1, 'Selecting an overview point must highlight its box');
  assert((await page.locator('#skinHighlights').innerText()).includes(Math.round(demo.lesions.find(l => l.id === first).probability * 100) + '%'), 'Actual confidence must be displayed');
  await page.getByRole('button', { name: 'Đồng ý và xem gợi ý', exact: true }).click();
  await page.locator('.skin-rec').first().waitFor();
  const recText = await page.locator('#skinRecsBody').innerText();
  assert(recText.includes('Dựa trên loại mụn AI phân loại ở chế độ thử nghiệm, chỉ để tham khảo. Hãy đặt lịch để chuyên viên tư vấn chính xác.'), 'Requested recommendation wording missing');
  assert(!recText.includes('Gợi ý thử nghiệm:'), 'Old trial prefix remains');
  const requestsBeforeDetail = recommendationRequests;
  const savedSnapshot = await page.evaluate(() => sessionStorage.getItem('skin-analysis-recommendation:v1'));
  await page.locator('#skinResult').scrollIntoViewIfNeeded();
  await page.screenshot({ path: out + '/overview-desktop.png', fullPage: true });
  await page.locator('#skinDetailLink').click();
  await page.waitForURL(base + '/skin-analysis/' + demo.id);
  await page.locator('#skinTable tr').last().waitFor();
  assert(await page.locator('#skinTable tr').count() === demo.lesions.length, 'Detail page must show every point');
  const detailIds = await page.locator('#skinTable .skin-point').evaluateAll(nodes => nodes.map(n => Number(n.textContent.trim())));
  assert(detailIds.join() === expected(demo).join(), 'Detail confidence ordering incorrect');
  assert(await page.locator('#skinCapture').isHidden(), 'Detail page must not show upload form');
  await page.reload(); await page.locator('#skinTable tr').last().waitFor();
  assert(await page.locator('#skinTable tr').count() === demo.lesions.length, 'Direct refresh must preserve detail');
  await page.getByRole('link', { name: 'Quay lại kết quả nổi bật', exact: true }).click();
  await page.locator('#skinDetailLink').waitFor();
  assert((await shown()).length === 8, 'Back link must reopen the same overview');
  await page.locator('.skin-rec').first().waitFor();
  assert(await page.locator('#skinRecsBody').innerText() === recText, 'Back link lost the recommendation cards');
  assert(recommendationRequests === requestsBeforeDetail, 'Back link unnecessarily requested recommendations again');
  await page.reload(); await page.locator('.skin-rec').first().waitFor();
  assert(recommendationRequests === requestsBeforeDetail, 'Reload unnecessarily requested recommendations again');
  await page.goBack(); await page.locator('#skinTable tr').last().waitFor();
  await page.goBack(); await page.locator('.skin-rec').first().waitFor();
  assert((await shown()).length === 8, 'Browser Back lost the saved analysis');
  assert(await page.locator('#skinImage').evaluate(img => img.complete && img.naturalWidth > 0), 'Browser Back lost the private image');
  assert(await page.locator('#skinRecsBody').innerText() === recText, 'Browser Back lost the recommendation cards');
  await page.goForward(); await page.locator('#skinTable tr').last().waitFor();
  await page.goForward(); await page.locator('.skin-rec').first().waitFor();
  assert(recommendationRequests === requestsBeforeDetail, 'Back/Forward generated another recommendation request');
  await page.evaluate(() => dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })));
  await page.locator('.skin-rec').first().waitFor();
  assert(recommendationRequests === requestsBeforeDetail, 'Restoring a cached document requested recommendations again');
  await page.screenshot({ path: out + '/recommendations-after-return.png', fullPage: true });
  checks.push('Back link, browser Back/Forward and reload preserve exact recommendations and private image with zero extra recommendation requests');
  checks.push('Actual upload → 8 ranked demo points on right, exact scores, removed messages, recommendation wording, dedicated detail page and reload/back');

  for (const width of [390, 360]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
    await page.screenshot({ path: `${out}/overview-${width}.png`, fullPage: true });
  }
  const many = await analyze('many');
  await page.getByRole('button', { name: 'Đồng ý và xem gợi ý', exact: true }).waitFor();
  assert(await page.locator('#skinRecsBody').innerText() !== recText, 'Another analysis reused the previous recommendations');
  assert((await shown()).join() === expected(many).slice(0, 8).join(), 'Many-point overview ordering incorrect');
  await page.locator('#skinDetailLink').click(); await page.locator('#skinTable tr').last().waitFor();
  assert(await page.locator('#skinTable tr').count() === 128, 'All 128 points must be immediately visible in detail');
  const allIds = await page.locator('#skinTable .skin-point').evaluateAll(nodes => nodes.map(n => Number(n.textContent.trim())));
  assert(allIds.join() === expected(many).join(), 'Full detail must sort known probabilities first and unknown last');
  await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
  await page.screenshot({ path: out + '/detail-360.png', fullPage: true });
  await page.getByRole('link', { name: 'Quay lại kết quả nổi bật', exact: true }).click();
  await page.locator('#skinDetailLink').waitFor();
  checks.push('390/360px without horizontal overflow; all 128 points reachable immediately and sorted on detail page');

  const few = await analyze('few');
  assert(few.lesions.length === 2 && (await shown()).length === 2, 'Fewer than 5 real points must not be padded');
  await analyze('empty');
  await page.getByText('Chưa phát hiện điểm trong ảnh này.', { exact: false }).waitFor();
  assert(await page.locator('#skinDetailLink').isHidden(), 'Empty result must not link to nonexistent points');
  await analyze('location_only');
  assert((await shown()).length === 8, 'Location-only results must remain available');
  assert((await page.locator('#skinHighlights').innerText()).includes('Độ tin cậy của AI: Chưa có'), 'Unknown scores must not be invented');
  await analyze('retake');
  assert(await page.locator('#skinResultBody').isHidden(), 'Retake response must not show stale results');
  assert((await page.locator('#skinBanner').innerText()).includes('Ảnh chưa đạt'), 'Retake instruction must remain');
  await page.route('**/api/me/skin-analyses/999999', route => route.fulfill({ status: 404, json: { success: false, message: 'Không tìm thấy kết quả phân tích.' } }));
  await page.goto(base + '/skin-analysis/999999');
  await page.locator('#skinStatus').filter({ hasText: 'Không tìm thấy kết quả phân tích.' }).waitFor();
  assert(await page.locator('#skinResult').isHidden(), 'Missing or unauthorized result must not show data');
  checks.push('Fewer/zero points, location-only unknown scores, retake and missing result preserve accurate states');

  // A tab-local snapshot must never bypass ownership or a changed consent version/expired lifetime.
  await page.unroute('**/api/me/skin-analyses/999999');
  for (const mode of ['expired', 'owner', 'version']) {
    await page.evaluate(({ mode, id }) => {
      const token = window.CustomerAuth.getAccessToken();
      const owner = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub;
      const previous = JSON.parse(sessionStorage.getItem('skin-analysis-recommendation:v1'));
      sessionStorage.setItem('skin-analysis-recommendation:v1', JSON.stringify({ owner: mode === 'owner' ? 'customer:999999' : owner,
        consentVersion: mode === 'version' ? 'old-version' : previous.consentVersion,
        expires: Date.now() + (mode === 'expired' ? -1000 : 60000), accepted: true,
        data: { analysis_id: id, status: 'ok', recommendations: [], summary: 'Must not restore' } }));
    }, { mode, id: demo.id });
    const beforeRequests = recommendationRequests;
    await page.goto(base + '/skin-analysis?analysis=' + demo.id);
    await page.getByRole('button', { name: 'Đồng ý và xem gợi ý', exact: true }).waitFor();
    assert(recommendationRequests === beforeRequests + 1, 'Invalid snapshot was restored: ' + mode);
  }
  await page.route('**/api/me/skin-analyses/' + demo.id, route => route.fulfill({ status: 404, json: { success: false, message: 'Không tìm thấy kết quả phân tích.' } }));
  await page.evaluate(snapshot => sessionStorage.setItem('skin-analysis-recommendation:v1', snapshot), savedSnapshot);
  await page.goto(base + '/skin-analysis?analysis=' + demo.id);
  await page.locator('#skinStatus').filter({ hasText: 'Không tìm thấy kết quả phân tích.' }).waitFor();
  assert(await page.locator('#skinRecs').isHidden(), 'Snapshot bypassed result ownership/deletion check');
  checks.push('Snapshots are isolated by account/analysis, expire and respect consent version; no restoration if result API denies access');
  assert(errors.length === 0, errors.join('; ')); assert(failures.length === 0, failures.join('; '));
  return { checks, pageErrors: errors, failedRequests: failures, expectedHttpErrors: [404] };
}
