async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/admin')).json();localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role',d.role);localStorage.setItem('admin_user',JSON.stringify({hoten:'Admin Test',role:'admin'}));});
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});let reads=0;const track=r=>{if(/\/messages$/.test(r.url())&&r.method()==='GET')reads++;};page.on('request',track);
    await page.goto(base+'/admin/chat?ui=legacy');await page.locator('.conversation-item').first().waitFor();
    if(reads)throw Error('Legacy list marked read');
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Legacy inbox overflow '+width);
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-inbox-legacy-${width}.png`});page.off('request',track);checks.push({width,reads});
  }
  if(errors.length)throw Error(errors.join());return {checks,errors};
}
