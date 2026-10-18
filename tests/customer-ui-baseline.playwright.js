async page => {
  const origin = 'http://127.0.0.1:5077';
  const errors = [], failed = [], results = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => failed.push({url: request.url().replace(origin, ''), error: request.failure()?.errorText}));
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 960});
    for (const path of ['/', '/services', '/services/1', '/packages', '/auth/login', '/appointments/create']) {
      await page.goto(origin + path);
      await page.locator('body').waitFor();
      if (path === '/services') await page.locator('#servicesGrid .service-card').first().waitFor();
      await page.screenshot({path: `.test-tmp/customer-ui/before-${width}-${path.replace(/\W+/g, '-') || 'home'}.png`});
      results.push({width, path, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)});
    }
    await page.goto(origin + '/__preview/session?customer=1');
    await page.locator('#userName').filter({hasText: 'Khách hàng Test'}).waitFor();
    await page.screenshot({path: `.test-tmp/customer-ui/before-${width}-profile.png`});
    await page.goto(origin + '/__preview/session');
    await page.evaluate(() => localStorage.clear());
  }
  return {results, errors, failed};
}
