// Replays HEAD assets only inside the isolated browser, after the original PR0 capture.
async page=>{
  const base='http://127.0.0.1:5088',checks=[];
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
  await page.route('**/static/css/chat-theme.css*',r=>r.fulfill({body:'',contentType:'text/css'}));
  await page.route('**/static/css/customers/catalog.css*',r=>r.fulfill({body:'',contentType:'text/css'}));
  await page.route('**/static/css/customers/style.css*',r=>r.fulfill({path:'.test-tmp/master-baseline-assets/style.css'}));
  await page.route('**/static/css/loyalty.css*',r=>r.fulfill({path:'.test-tmp/master-baseline-assets/loyalty.css'}));
  await page.route('**/static/js/loyalty-payment.js*',r=>r.fulfill({path:'.test-tmp/master-baseline-assets/loyalty-payment.js'}));
  await page.route('**/api/ai/status',r=>r.fulfill({json:{configured:true}}));
  await page.route('**/api/loyalty/my-rewards?**',async route=>{const d=await(await route.fetch()).json();d.items.forEach(v=>{v.reward.name+=' · '+('Điều kiện voucher dài để kiểm tra xuống dòng. ').repeat(5);});await route.fulfill({json:d});});
  for(const width of [390,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/?ui=legacy');await page.evaluate(()=>openChat());await page.locator('#chatBox.show').waitFor();
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/before-head-live-chat-${width}.png`});
    await page.locator('#chatBox .chat-close').click();await page.locator('.ai-fab').click();await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/before-head-ai-chat-${width}.png`});await page.locator('.ai-icon-btn[data-close]').click();
    await page.goto(base+'/profile?ui=legacy#invoices');await page.evaluate(()=>window.LoyaltyPayment.openCustomerInvoice(1));await page.locator('#customerLoyaltyPayment [data-voucher]').waitFor();
    await page.locator('[data-enable]').check();await page.locator('[data-points]').fill('100');await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/before-head-payment-${width}.png`});
    await page.evaluate(()=>window.__beforePayment=document.getElementById('customerLoyaltyPayment'));await page.locator('[data-apply]').click();await page.locator('[data-remove]').waitFor();
    const replaced=await page.evaluate(()=>document.getElementById('customerLoyaltyPayment')!==window.__beforePayment);if(!replaced)throw Error('HEAD flicker did not reproduce');
    await page.locator('[data-remove]').click();await page.locator('[data-remove]').waitFor({state:'detached'});await page.keyboard.press('Escape');checks.push({width,headPaymentDialogReplaced:replaced});
  }
  await page.unrouteAll({behavior:'wait'});return {assetSource:'git HEAD 61b8a54',environment:'isolated SQLite/browser replay',checks};
}
