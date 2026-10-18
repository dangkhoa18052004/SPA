async page => {
  globalThis.qa = { errors: [], failed: [], blocked: [], responses: [] };
  await page.context().route('**/*', async route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
      qa.blocked.push(route.request().url());
      return route.abort('blockedbyclient');
    }
    return route.continue();
  });
  page.on('pageerror', error => qa.errors.push({url: page.url(), message: error.message}));
  page.on('console', message => { if (message.type() === 'error') qa.errors.push({url:page.url(),message:message.text()}); });
  page.on('requestfailed', request => { if (new URL(request.url()).hostname === '127.0.0.1') qa.failed.push({url: request.url(), error: request.failure()?.errorText}); });
  page.on('response', response => { if (response.status() >= 400) qa.responses.push({url:response.url(),status:response.status()}); });
  await page.goto('https://127.0.0.1:5000/', {waitUntil:'networkidle'});
  return { title: await page.title(), links: await page.locator('a[href]').evaluateAll(nodes => [...new Set(nodes.map(n=>n.getAttribute('href')))].filter(s=>s.startsWith('/'))), errors:qa.errors, failed:qa.failed,responses:qa.responses,blocked: [...new Set(qa.blocked)] };
}
