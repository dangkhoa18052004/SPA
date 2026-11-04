async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();await fetch('/__qa/login/guest');});
  for(const legacy of [true,false])for(const width of [390,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/?'+(legacy?'ui=legacy':''));await page.locator('#servicesGrid .service-card').first().waitFor();
    assert(await page.locator('#servicesGrid .service-card').count()===6,'Home top six');assert(await page.locator('#homeCategories button').count()===3,'Real home category chips');
    const hotline=page.locator('a[href="tel:0387829152"]');assert((await hotline.textContent()).replace(/\D/g,'')==='0387829152','Confirmed CS1 text/href');
    const contrast=await page.locator('.service-price').first().evaluate(el=>{const color=getComputedStyle(el).color.match(/[\d.]+/g).slice(0,3).map(Number);const luminance=color.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);return 1.05/(luminance+.05);});assert(contrast>=4.5,'Price AA contrast on white card');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-home-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});
    await page.goto(base+'/services/1'+(legacy?'?ui=legacy':''));await page.locator('#serviceDetailContainer h1').waitFor();await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-service-detail-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'No detail overflow');checks.push({legacy,width,hotline:true});
  }
  const metrics=await page.evaluate(async()=>{const rows=[];for(const query of ['', '?page=1&per_page=9']){const start=performance.now(),r=await fetch('/api/services'+query),body=await r.text(),d=JSON.parse(body);rows.push({query,services:d.services.length,utf8Bytes:new TextEncoder().encode(body).length,elapsedMs:Math.round(performance.now()-start)});}return rows;});
  assert(!errors.length,errors.join());return {checks,metrics,metricScope:'same isolated 25-service fixture, compatible full-list vs paged response; single local sample, not a latency benchmark',errors};
}
