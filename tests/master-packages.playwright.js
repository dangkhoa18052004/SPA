async page=>{
  const base='http://127.0.0.1:5088',errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  for(const legacy of [false,true])for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/packages'+(legacy?'?ui=legacy':''));
    await page.locator('#packageList article').first().waitFor();assert(await page.locator('#packageList article').count()===9,'9 packages');
    await page.locator('#packagePagination button').filter({hasText:/^3$/}).click();assert(await page.locator('#packageList article').count()===7,'7 last page');
    await page.locator('#packageSearch').fill('Gói kiểm thử 01');await page.waitForTimeout(350);assert(await page.locator('#packageList article').count()===1,'1 search result');
    const g=await page.evaluate(()=>({card:document.querySelector('#packageList article').getBoundingClientRect().width,grid:document.getElementById('packageList').getBoundingClientRect().width,overflow:document.documentElement.scrollWidth>innerWidth}));assert(!g.overflow,'No overflow');if(width>=1024)assert(g.card<g.grid*.4,'Single package bounded');
    await page.reload();await page.locator('#packageList article').first().waitFor();assert(await page.locator('#packageList article').count()===1,'Refresh');
    await page.locator('#packageSearch').fill('no-match');await page.waitForTimeout(350);assert(await page.locator('#packageList article').count()===0,'Empty');
    await page.goBack();await page.locator('#packageList article').first().waitFor();assert(await page.locator('#packageList article').count()===1,'Back');
    await page.locator('#packageClear').click();await page.locator('#packageSort').selectOption('price-desc');
    assert((await page.locator('#packageList article').first().textContent()).includes('Gói kiểm thử 25'),'Global sort');
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-packages-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});checks.push({legacy,width,pages:[9,9,7],single:true});
  }
  // Exercise 0/1/9/10/25/100 listing counts with explicit browser-only fixture responses.
  const response=await page.request.get(base+'/api/packages'),data=await response.json(),sample=data.packages[0];
  for(const count of [0,1,9,10,25,100]){
    await page.route('**/api/packages',route=>route.fulfill({json:{success:true,packages:Array.from({length:count},(_,i)=>({...sample,magoi:i+1,tengoi:'Fixture '+i}))}}));
    await page.goto(base+'/packages');await page.waitForFunction(()=>document.getElementById('packageResultCount')?.textContent.includes(' / '));
    assert(await page.locator('#packageList article').count()===Math.min(9,count),'Bounded count '+count);
    assert((await page.locator('#packagePagination button').count()>0)===(count>9),'Pagination visibility '+count);
    await page.unroute('**/api/packages');
  }
  await page.goto(base+'/packages/1');await page.locator('.package-service-list').waitFor();assert((await page.locator('.package-service-list').textContent()).includes('10 buổi'),'Detail full breakdown');
  assert(!errors.length,errors.join());return {checks,countCases:[0,1,9,10,25,100],errors};
}
