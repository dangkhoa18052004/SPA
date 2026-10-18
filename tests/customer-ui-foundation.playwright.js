async page => {
  const base = 'http://127.0.0.1:5078';
  const errors = [], failed = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => { if (request.url().startsWith(base)) failed.push(request.url().replace(base,'')); });
  for (const width of [360,390,768,1024,1440]) {
    await page.setViewportSize({width,height:960});
    await page.goto(base + '/services', {waitUntil:'domcontentloaded'});
    await page.locator('#servicesGrid .service-card').first().waitFor();
    const state = await page.evaluate(() => ({
      enabled: document.body.classList.contains('customer-ui'),
      overflow: document.documentElement.scrollWidth > innerWidth,
      font: getComputedStyle(document.body).fontFamily,
      adminCss: [...document.styleSheets].some(s=>s.href?.includes('/assets/portal-')),
    }));
    if (!state.enabled || state.overflow || state.adminCss) throw new Error(JSON.stringify({width,...state}));
    checks.push({width,...state});
    if ([390,1440].includes(width)) await page.screenshot({path:`.test-tmp/customer-ui/foundation-${width}-services.png`});
  }
  await page.goto(base + '/services?ui=legacy');
  if (await page.locator('body.customer-ui').count()) throw new Error('Legacy override ignored');
  await page.goto(base + '/admin/login');
  if (await page.locator('body.customer-ui').count()) throw new Error('Customer theme leaked into admin');
  return {checks,errors,failed};
}
