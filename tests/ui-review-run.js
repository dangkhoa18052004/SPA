// Runs one `async (page, ctx) => result` scenario file in a fresh Chrome context against the 5091 fixture.
// usage (repo root): node tests/ui-review-run.js <scenario.playwright.js> <output dir> [extra args...]
// ctx = {base, out, args, context, browser, login(role, page?), dialogs, pageErrors}. Prints the JSON result; exit 1 on failure.
const fs = require('fs');
const {chromium} = require(require('child_process').execSync('npm root -g').toString().trim() + '/@playwright/cli/node_modules/playwright');
(async () => {
  const [file, out, ...args] = process.argv.slice(2);
  fs.mkdirSync(out, {recursive: true});
  const fn = eval(fs.readFileSync(file, 'utf8'));
  const browser = await chromium.launch({channel: 'chrome'});
  const context = await browser.newContext();
  // VietQR images are external; never fetch them from tests.
  await context.route(/img\.vietqr\.io/, r => r.fulfill({status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg"/>'}));
  const page = await context.newPage();
  const base = 'http://127.0.0.1:5091';
  const dialogs = [], pageErrors = [];
  const watch = p => {
    p.on('dialog', d => { dialogs.push({url: p.url(), message: d.message()}); d.accept(); });
    p.on('pageerror', e => pageErrors.push({url: p.url(), message: e.message}));
  };
  watch(page);
  context.on('page', watch);
  const login = async (role, target = page) => {
    if (!target.url().startsWith(base)) await target.goto(base + '/__qa/ping');
    return target.evaluate(async role => {
      localStorage.clear();
      const d = await (await fetch('/__qa/login/' + role)).json();
      if (d.access_token) {
        localStorage.setItem(role === 'customer' ? 'access_token' : 'admin_token', d.access_token);
        if (role !== 'customer') localStorage.setItem('admin_role', d.role);
      }
      return d;
    }, role);
  };
  let result, failed = false;
  try {
    result = await fn(page, {base, out, args, context, browser, login, dialogs, pageErrors});
  } catch (e) {
    failed = true;
    result = {error: e.message.split('\n').slice(0, 6).join('\n')};
    await page.screenshot({path: `${out}/failure-${file.replace(/\W+/g, '-')}.png`, fullPage: true}).catch(() => {});
  }
  console.log(JSON.stringify({file, failed, result, dialogs, pageErrors}, null, 1));
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
