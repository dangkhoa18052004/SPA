async page => {
  const base = 'http://127.0.0.1:5087', results = [], errors = [], failures = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => failures.push({url:r.url().replace(base,''),error:r.failure()?.errorText}));
  for (const width of [360,390,768,1024,1440]) {
    await page.setViewportSize({width,height:960});
    for (const path of ['/', '/services', '/packages', '/services/1', '/appointments/create']) {
      await page.goto(base + path);
      if (path === '/' || path === '/services') await page.locator('#servicesGrid .service-card').first().waitFor();
      if (path === '/packages') await page.locator('#packageList article').first().waitFor();
      results.push({width,path,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),assets:await page.locator('script[type=module]').count()});
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/before-${width}-${path.replace(/\W+/g,'-')||'home'}.png`,fullPage:true});
    }
  }
  return {results,errors,failures};
}
