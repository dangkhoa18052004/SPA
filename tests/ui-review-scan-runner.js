// Runs tests/ui-review-pages.playwright.js in a fresh Chrome context per role; accepts and records alerts.
// usage (repo root, fixture on 5091): node tests/ui-review-scan-runner.js <role> <legacy 0|1> <out.json> [screenshot dir]
const fs=require('fs');const {chromium}=require(require('child_process').execSync('npm root -g').toString().trim()+'/@playwright/cli/node_modules/playwright');
(async()=>{
  const [role,legacy,out,shots]=process.argv.slice(2);
  const fn=eval(fs.readFileSync('tests/ui-review-pages.playwright.js','utf8'));
  const browser=await chromium.launch({channel:'chrome'});const page=await (await browser.newContext()).newPage();
  const alerts=[];page.on('dialog',d=>{alerts.push({url:page.url(),message:d.message()});d.accept();});
  await page.goto(`http://127.0.0.1:5091/__qa/ping?role=${role}${legacy==='1'?'&legacy=1':''}${shots?'&out='+encodeURIComponent(shots):''}`);
  const result=await fn(page);result.alerts=alerts;
  fs.writeFileSync(out,JSON.stringify(result,null,1));await browser.close();
  const r=result.results;console.log(role,legacy,'visits',r.length,'errors',r.filter(x=>x.error).length,'http>=400',r.filter(x=>x.status>=400).length,'overflow',r.filter(x=>x.overflow).length,'broken',r.filter(x=>x.brokenImages?.length).length,'jsErr',result.errors.length,'consoleErr',result.consoleErrors.length,'alerts',alerts.length);
})();
