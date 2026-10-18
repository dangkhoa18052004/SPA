async page => {
  const results=[];
  for(const width of [390,1440])for(const port of [5077,5079]){
    const tab=await page.context().newPage();
    await tab.setViewportSize({width,height:960});
    await tab.addInitScript(()=>{
      window.__vitals={lcp:0,cls:0};
      new PerformanceObserver(list=>{for(const e of list.getEntries())window.__vitals.lcp=e.startTime;}).observe({type:'largest-contentful-paint',buffered:true});
      new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.__vitals.cls+=e.value;}).observe({type:'layout-shift',buffered:true});
    });
    await tab.goto(`http://127.0.0.1:${port}/`,{waitUntil:'load'});
    await tab.locator('#servicesGrid .service-card').first().waitFor();
    await tab.waitForFunction(()=>window.__vitals.lcp>0);
    await tab.screenshot({path:`.test-tmp/customer-ui/performance-${port}-${width}.png`});
    results.push({ui:port===5077?'legacy':'new',width,...await tab.evaluate(()=>window.__vitals)});
    await tab.close();
  }
  return {conditions:'Local loopback, Edge, existing browser cache, no network shaping; single lab sample, not field data',results};
}
