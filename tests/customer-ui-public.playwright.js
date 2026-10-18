async page => {
  const base = 'http://127.0.0.1:5078';
  const errors = [], failures = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const url = response.url();
    if (url.startsWith(base) && response.status() >= 400 && !(url.endsWith('/api/auth/restore-session') && response.status() === 401)) failures.push({path:url.replace(base,''),status:response.status()});
  });
  for (const width of [360,390,768,1024,1440]) {
    await page.setViewportSize({width,height:960});
    for (const path of ['/', '/services', '/services/1', '/packages']) {
      await page.goto(base + path, {waitUntil:'domcontentloaded'});
      await page.locator('body.customer-ui').waitFor();
      if (path === '/' || path === '/services') await page.locator('#servicesGrid article').first().waitFor();
      if (path === '/services/1') await page.locator('.service-detail-name').waitFor();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      if (overflow) throw new Error(`Horizontal overflow ${width} ${path}`);
      checks.push({width,path});
      if ([390,1440].includes(width)) await page.screenshot({path:`.test-tmp/customer-ui/public-${width}-${path.replace(/\W+/g,'-')}.png`});
    }
  }
  await page.goto(base + '/services');
  await page.locator('#servicesGrid article').first().waitFor();
  await page.locator('#searchInput').fill('gội');
  await page.locator('#sortSelect').selectOption('price-desc');
  if (await page.locator('#servicesGrid article').count() !== 1) throw new Error('Search failed');
  await page.reload();
  await page.locator('#servicesGrid article').first().waitFor();
  if (await page.locator('#searchInput').inputValue() !== 'gội') throw new Error('Search deep link lost');
  await page.locator('#searchInput').fill('không tồn tại');
  await page.locator('#noResults').waitFor({state:'visible'});
  await page.getByRole('button',{name:'Xóa bộ lọc'}).click();
  if (await page.locator('#servicesGrid article').count() !== 4) throw new Error('Reset filters failed');
  await page.locator('#servicesGrid article').first().getByRole('link',{name:/Chi tiết/}).click();
  await page.locator('.service-detail-name').waitFor();
  if (await page.locator('.service-actions-detail a').getAttribute('href') !== '/appointments/create?service=1') throw new Error('Booking service id lost');
  if (errors.length || failures.length) throw new Error(JSON.stringify({errors,failures}));
  return {checks, searchRefreshReset:true, serviceDeepLink:true, errors,failures};
}
