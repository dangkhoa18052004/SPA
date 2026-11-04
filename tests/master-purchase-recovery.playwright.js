async page=>{
  const base='http://127.0.0.1:5089';let posts=0,reads=0;
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
  await page.route('**/api/packages/my-purchases',async route=>{if(++reads>1)await route.fulfill({status:503,json:{message:'Fixture reconciliation offline'}});else await route.continue();});
  await page.route('**/api/packages/3/purchase',async route=>{posts++;await route.abort('failed');});
  await page.goto(base+'/packages/3');await page.locator('[data-buy="3"]').click();await page.locator('#packageMessage').filter({hasText:'Chưa xác minh được đơn mua'}).waitFor();
  const marker=()=>page.evaluate(()=>Object.keys(sessionStorage).some(k=>k.startsWith('binspa.pending-package-purchase:')&&k.endsWith(':3')));
  if(!await marker())throw Error('Uncertain purchase marker lost');
  await page.locator('[data-buy="3"]').click();await page.waitForTimeout(300);if(posts!==1||!await marker())throw Error('Retry posted or lost marker after GET failure');
  await page.reload();await page.locator('#packageMessage').filter({hasText:/Fixture reconciliation offline/}).waitFor();
  await page.unroute('**/api/packages/my-purchases');await page.locator('[data-buy="3"]').click();await page.locator('#packageMessage').filter({hasText:'Chưa xác định kết quả mua gói'}).waitFor();
  if(posts!==1||!await marker())throw Error('Unknown outcome retried POST');await page.unrouteAll({behavior:'wait'});
  return {posts,unknownOutcomePreservedAcrossReload:true,failedGetDoesNotPermitRepost:true};
}
