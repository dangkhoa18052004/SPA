async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/appointments/create?service=1');await page.getByTestId('booking-next').waitFor();
    assert(await page.locator('#booking-service-list article').count()===6,'Keep 6 per page');
    if(width<768)await page.getByTestId('booking-summary-open').click();
    const select=page.locator('.booking-summary [data-treatment-service="1"]');await select.waitFor({state:'visible'});
    assert(await page.locator('[data-treatment-service="1"]').count()===1,'One selector owner');
    const item=await select.locator('option').nth(1).getAttribute('value');await select.selectOption(item);
    assert((await page.getByTestId('booking-total').textContent()).replace(/\D/g,'')==='0','Treatment updates total');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-booking-${width}.png`,fullPage:width>=768});
    await select.selectOption('');assert((await page.getByTestId('booking-total').textContent()).includes('100'),'Normal payment restored');
    if(width<768){await page.keyboard.press('Escape');assert(await page.getByTestId('booking-summary-open').evaluate(b=>document.activeElement===b),'Focus return');}
    await page.getByRole('button',{name:'Trang dịch vụ sau'}).click();assert(await page.locator('#booking-service-list article').count()===6,'Next page');
    if(width<768)await page.getByTestId('booking-summary-open').click();assert(await select.count()===1,'Selection persists');
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'No overflow');
    if(width<768)await page.keyboard.press('Escape');checks.push({width,sourceInSummary:true,paging:6});
  }
  // Real local API: lost response after creation; never blindly POST again.
  await page.goto(base+'/appointments/create?service=1');await page.getByTestId('booking-next').click();
  const date=await page.evaluate(()=>{const d=new Date();d.setDate(d.getDate()+3);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;});
  await page.getByTestId('booking-date').fill(date);await page.locator('[data-slot="10:30"]').click();await page.getByTestId('booking-next').click();
  let creates=0;await page.route('**/api/appointments/create',async route=>{creates++;const r=await route.fetch();assert(r.status()===201,'Fixture booking create');await route.fulfill({status:503,json:{message:'Fixture lost response'}});});
  await page.getByTestId('booking-submit').evaluate(b=>{b.click();b.click();});await page.getByRole('heading',{name:'Kiểm tra kết quả đặt lịch'}).waitFor();assert(creates===1,'No duplicate create');
  await page.reload();await page.getByRole('button',{name:'Kiểm tra lịch đã đặt',exact:true}).click();await page.getByTestId('booking-success').waitFor();assert(creates===1,'Reconcile without repost');await page.unroute('**/api/appointments/create');
  assert(!errors.length,errors.join());return {checks,creates,reconciled:true,errors};
}
