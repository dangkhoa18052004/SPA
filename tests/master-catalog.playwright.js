async page => {
  const base='http://127.0.0.1:5088',errors=[],failures=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().startsWith(base)&&r.status()>=500)failures.push(r.url());});
  const ready=()=>page.waitForFunction(()=>document.getElementById('servicesGrid')?.getAttribute('aria-busy')==='false');
  const assert=(v,m)=>{if(!v)throw Error(m);};
  for(const legacy of [false,true])for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});
    await page.goto(base+'/services'+(legacy?'?ui=legacy':''));await ready();
    assert(await page.locator('#servicesGrid .service-card').count()===9,'9 first page');
    await page.locator('#catalogCategories [data-category=acne]').waitFor();
    assert(await page.locator('#catalogCategories button').count()===3,'Only real populated categories');
    await page.locator('#catalogPagination button').filter({hasText:/^3$/}).click();await ready();
    assert(await page.locator('#servicesGrid .service-card').count()===7,'7 last page');
    await page.locator('#searchInput').fill('Dịch vụ 01');await page.waitForTimeout(350);await ready();
    assert(await page.locator('#servicesGrid .service-card').count()===1,'1 match');
    assert(!new URL(page.url()).searchParams.has('page'),'Filters reset page');
    const geometry=await page.evaluate(()=>{const g=document.getElementById('servicesGrid').getBoundingClientRect(),c=document.querySelector('#servicesGrid .service-card').getBoundingClientRect();return {grid:g.width,card:c.width,overflow:document.documentElement.scrollWidth>innerWidth};});
    assert(!geometry.overflow,'No overflow');if(width>=1024)assert(geometry.card<geometry.grid*.4,'Single card width');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-services-single-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});
    await page.reload();await ready();assert(await page.locator('#servicesGrid .service-card').count()===1,'Refresh query');
    await page.locator('#searchInput').fill('no-match');await page.waitForTimeout(350);await ready();assert(await page.locator('#noResults').isVisible(),'Empty state');
    await page.goBack();await ready();assert(await page.locator('#servicesGrid .service-card').count()===1,'Back restores query');
    await page.locator('.services-filter-section').getByRole('button',{name:'Xóa bộ lọc',exact:true}).click();await ready();
    await page.locator('#sortSelect').selectOption('price-desc');await ready();
    const prices=await page.locator('#servicesGrid .service-price').allTextContents();assert(prices[0].includes('340'),'Whole-catalog sort');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-services-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});
    await page.goto(base+'/'+(legacy?'?ui=legacy':''));await page.locator('#homeCategories button').nth(1).waitFor();
    assert(await page.locator('#homeCategories button').count()===3,'Home categories');
    await page.locator('#homeCategories button').nth(2).click();assert(await page.locator('#servicesGrid .service-card').count()===6,'Home filter entire dataset');
    checks.push({legacy,width,singleCard:geometry.card,pagination:'9/9/7',overflow:false});
  }
  assert(!errors.length,'Page errors '+errors.join());assert(!failures.length,'Server errors '+failures.join());
  return {checks,errors,failures};
}
