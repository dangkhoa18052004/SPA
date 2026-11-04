async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  for(const legacy of [false,true])for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/services'+(legacy?'?ui=legacy':''));await page.waitForFunction(()=>document.getElementById('servicesGrid')?.getAttribute('aria-busy')==='false');
    if(width<640){await page.getByRole('button',{name:'Bộ lọc',exact:true}).click();await page.locator('#catalogFilterDialog').waitFor({state:'visible'});}
    else await page.locator('.catalog-advanced summary').click();
    await page.locator('#min_price').fill('300000');await page.locator('#min_price').press('Tab');
    if(width<640)await page.getByRole('button',{name:'Xem kết quả',exact:true}).click();
    await page.waitForFunction(()=>document.getElementById('servicesGrid')?.getAttribute('aria-busy')==='false');assert(await page.locator('#servicesGrid .service-card').count()===5,'Price range before pagination');
    await page.reload();await page.waitForFunction(()=>document.getElementById('servicesGrid')?.getAttribute('aria-busy')==='false');assert(await page.locator('#min_price').inputValue()==='300000','Range URL restore');
    await page.route('**/api/services?**',r=>r.fulfill({status:503,json:{message:'Fixture unavailable'}}));
    await page.locator('#searchInput').fill('keep draft');await page.waitForTimeout(350);await page.locator('#servicesGrid [role=alert]').waitFor();assert(await page.locator('#searchInput').inputValue()==='keep draft','Error preserves query');await page.unroute('**/api/services?**');
    await page.locator('#servicesGrid').getByRole('button',{name:'Thử lại'}).click();await page.locator('#noResults').waitFor({state:'visible'});assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'No overflow');checks.push({legacy,width,drawer:width<640,errorRetry:true});
  }
  // Package request failure is a visible retry; state must not be mistaken for empty.
  await page.route('**/api/packages',r=>r.fulfill({status:503,json:{message:'Fixture packages offline'}}));await page.goto(base+'/packages');await page.locator('#packageList [role=alert]').waitFor();await page.unroute('**/api/packages');await page.locator('[data-retry-packages]').click();await page.locator('#packageList article').first().waitFor();
  // Browser-only legacy/refactor contrast checks with text enlarged, no account mutation.
  for(const legacy of [false,true]){
    await page.goto(base+'/services'+(legacy?'?ui=legacy':''));await page.locator('#servicesGrid .service-card').first().waitFor();
    await page.evaluate(()=>{document.documentElement.style.fontSize='200%';});assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Text resize overflow');
  }
  assert(!errors.length,errors.join());return {checks,packageErrorRetry:true,textResize:true,errors};
}
