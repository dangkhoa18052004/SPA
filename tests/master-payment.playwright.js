async page=>{
  const base='http://127.0.0.1:5088',errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
  await page.route('**/api/loyalty/my-rewards?**',async route=>{const r=await route.fetch(),d=await r.json();d.items.forEach(v=>{v.reward.name+=' · '+('Điều kiện voucher dài để kiểm tra xuống dòng. ').repeat(5);});await route.fulfill({json:d});});
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/profile#invoices');
    await page.evaluate(()=>window.LoyaltyPayment.openCustomerInvoice(1));
    const dialog=page.locator('#customerLoyaltyPayment');await dialog.locator('[data-enable]').waitFor();
    await page.evaluate(()=>{window.__paymentNode=document.getElementById('customerLoyaltyPayment');window.__paymentClosed=0;window.__paymentNode.addEventListener('close',()=>window.__paymentClosed++);});
    await dialog.locator('[data-enable]').check();await dialog.locator('[data-points]').fill('0');await dialog.locator('[data-preview]').click();await dialog.locator('[data-result]').filter({hasText:'Nhập số điểm nguyên'}).waitFor();
    await dialog.locator('[data-points]').fill('100');let previews=0;const track=r=>{if(r.url().endsWith('/loyalty/preview'))previews++;};page.on('request',track);
    await dialog.locator('[data-preview]').click();await dialog.locator('[data-result]').filter({hasText:'100 điểm'}).waitFor();page.off('request',track);assert(previews===1,'Preview request once');
    const before=await page.evaluate(async()=>await(await window.CustomerAuth.fetch('/api/payment/invoices/1/loyalty')).json());assert(before.points_used===0,'Preview read-only');
    await dialog.locator('[data-apply]').evaluate(b=>{b.click();b.click();});await dialog.locator('[data-remove]').waitFor();
    assert(await page.evaluate(()=>document.getElementById('customerLoyaltyPayment')===window.__paymentNode&&window.__paymentClosed===0),'Same dialog apply');
    const applied=await page.evaluate(async()=>await(await window.CustomerAuth.fetch('/api/payment/invoices/1/loyalty')).json());assert(applied.points_used===100&&Number(applied.payable_amount)===400000,'Committed server totals');
    await dialog.locator('[data-remove]').click();await dialog.locator('[data-remove]').waitFor({state:'detached'});
    await dialog.locator('[data-voucher]').first().check();await dialog.locator('[data-apply-voucher]').click();await dialog.locator('[data-remove-voucher]').waitFor();
    assert(await page.evaluate(()=>document.getElementById('customerLoyaltyPayment')===window.__paymentNode&&window.__paymentClosed===0),'Same dialog voucher');
    await dialog.locator('[data-remove-voucher]').click();await dialog.locator('[data-voucher]').first().waitFor();
    const overflow=await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left<0||r.right>innerWidth||el.scrollWidth>el.clientWidth;});assert(!overflow,'Voucher dialog fits');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-payment-${width}.png`});
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});checks.push({width,sameDialog:true,previewReadOnly:true,overflow:false});
  }
  // Lost POST response: GET reconciliation must show one committed reservation, no retry POST.
  await page.evaluate(()=>window.LoyaltyPayment.openCustomerInvoice(1));await page.locator('[data-enable]').check();await page.locator('[data-points]').fill('100');let posts=0;
  await page.route('**/api/payment/invoices/1/loyalty',async route=>{if(route.request().method()==='POST'){posts++;const r=await route.fetch();assert(r.status()===200,'Lost-response fixture committed');await route.fulfill({status:503,json:{message:'Fixture response lost'}});}else await route.continue();});
  await page.locator('[data-apply]').click();await page.locator('[data-remove]').waitFor();assert(posts===1,'No repeated mutation after uncertain result');await page.unroute('**/api/payment/invoices/1/loyalty');await page.locator('[data-remove]').click();await page.locator('[data-remove]').waitFor({state:'detached'});
  await page.keyboard.press('Escape');assert(!errors.length,errors.join());return {checks,lostResponsePosts:posts,errors};
}
