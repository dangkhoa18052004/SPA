async page=>{
  const base='http://127.0.0.1:5089',errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  // QR art is intercepted; no image request reaches a bank/provider.
  await page.route('https://img.vietqr.io/**',r=>r.fulfill({status:200,contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180"><rect width="180" height="180" fill="#eef3ef"/><text x="20" y="90">QA ONLY</text></svg>'}));
  await page.goto(base+'/');await page.evaluate(async()=>{localStorage.clear();sessionStorage.clear();const r=await fetch('/api/auth/login/customer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({taikhoan:'customer_test',matkhau:'password'})});const d=await r.json();if(!r.ok)throw Error('Fixture customer login');localStorage.setItem('access_token',d.access_token);});
  for(const width of [390,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/services?category=acne&search=Dịch+vụ+01');
    await page.locator('#servicesGrid .service-card').waitFor();await page.locator('#servicesGrid .service-card').getByRole('link',{name:/Đặt lịch/}).click();
    await page.getByTestId('booking-next').waitFor();await page.getByRole('textbox',{name:'Tìm dịch vụ',exact:true}).fill('Dịch vụ 20');await page.locator('#booking-service-list [data-service-id="20"]').click();
    if(width<768)await page.getByTestId('booking-summary-open').click();
    const selector=page.locator('[data-treatment-service="1"]'),item=await selector.locator('option').nth(1).getAttribute('value');await selector.selectOption(item);
    assert((await page.getByTestId('booking-total').textContent()).includes('290'),'Selected package usage + regular service');
    if(width<768)await page.keyboard.press('Escape');await page.getByTestId('booking-next').click();
    const date=await page.evaluate(()=>{const d=new Date();d.setDate(d.getDate()+3);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;});
    await page.getByTestId('booking-date').fill(date);await page.locator(`[data-slot="${width<768?'11:00':'14:00'}"]`).click();await page.getByTestId('booking-next').click();
    await page.getByTestId('booking-prepay').check();let appointment;
    const capture=async response=>{if(response.url().endsWith('/api/appointments/create')&&response.status()===201)appointment=(await response.json()).appointment;};page.on('response',capture);
    await page.getByTestId('booking-submit').click();const dialog=page.locator('#customerLoyaltyPayment');await dialog.locator('[data-apply-voucher]').waitFor();page.off('response',capture);
    await dialog.locator('[data-voucher]').first().check();await dialog.locator('[data-apply-voucher]').click();await dialog.locator('[data-remove-voucher]').waitFor();
    await dialog.locator('[data-enable]').check();await dialog.locator('[data-points]').fill('100');await dialog.locator('[data-preview]').click();await dialog.locator('[data-result]').filter({hasText:'100 điểm'}).waitFor();
    await dialog.locator('[data-apply]').click();await dialog.locator('[data-remove]').waitFor();
    const summary=await page.evaluate(async id=>await(await window.CustomerAuth.fetch(`/api/payment/invoices/${id}/loyalty`)).json(),appointment.invoice_id);
    assert(Number(summary.payable_amount)===103000,'Combined discount server amount');await dialog.locator('[data-pay]').click();await dialog.locator('[data-bank] img').waitFor();
    assert((await dialog.locator('[data-bank]').textContent()).includes('103.000'),'QR matches server payable');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-customer-flow-qr-${width}.png`});
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
    const invoice=await page.evaluate(async id=>await(await window.CustomerAuth.fetch(`/api/payment/invoices/${id}`)).json(),appointment.invoice_id);assert(invoice.trangthai==='Chưa thanh toán','Closing does not pay');
    await page.goto(base+'/profile#invoices');await page.locator('#invoicesList').getByRole('button',{name:'Tiếp tục thanh toán',exact:true}).first().waitFor();checks.push({width,booking:true,treatmentUsage:true,points:100,voucherPercent:30,payable:103000,paid:false});
  }
  // Real package purchase; response lost after commit must reconcile, never repost.
  await page.goto(base+'/packages/2');let purchases=0;
  await page.route('**/api/packages/2/purchase',async route=>{purchases++;const r=await route.fetch();assert(r.status()===201,'Purchase fixture');await route.fulfill({status:503,json:{message:'Fixture: lost purchase response'}});});
  await page.locator('[data-buy="2"]').evaluate(b=>{b.click();b.click();});await page.locator('#packagePaymentDialog[open]').waitFor();await page.locator('#packageMessage').filter({hasText:'Đã tìm thấy đơn mua trước đó'}).waitFor();assert(purchases===1,'One purchase after double click');await page.unroute('**/api/packages/2/purchase');await page.keyboard.press('Escape');
  const pending=await page.evaluate(async()=>{const d=await(await window.CustomerAuth.fetch('/api/packages/my-purchases')).json();return d.purchases.find(p=>p.status==='pending');});assert(!!pending,'Pending purchase persisted');
  await page.goto(base+`/packages/2?purchase=${pending.id}`);await page.locator('#packagePaymentDialog[open]').waitFor();await page.locator('[data-reveal-qr]').click();await page.locator('[data-package-qr] img').waitFor();assert(purchases===1,'Resume no duplicate purchase');
  await page.keyboard.press('Escape');assert(!errors.length,errors.join());return {checks,purchases,resumedPending:true,errors};
}
