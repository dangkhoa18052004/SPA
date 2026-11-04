async page => {
  const base='http://127.0.0.1:5088', results=[];
  const login = async role => {
    await page.goto(base+'/__qa/ping');
    await page.evaluate(async role=>{localStorage.clear();const d=await(await fetch('/__qa/login/'+role)).json();if(d.access_token)localStorage.setItem(role==='customer'?'access_token':'admin_token',d.access_token);},role);
  };
  for(const width of [390,1440]) {
    await page.setViewportSize({width,height:960});
    for(const [role,path,ready] of [
      ['guest','/services','#servicesGrid .service-card'],['guest','/packages','#packageList article'],
      ['customer','/appointments/create','.booking-summary'],['admin','/admin/chat','.care-inbox'],
      ['admin','/admin/loyalty?tab=redemptions','.admin-shell'],['staff','/employee/account','.employee-header']
    ]) {
      await login(role); await page.goto(base+path);
      // Shell selectors are recorded even when a route's feature gate falls back.
      await page.waitForFunction(()=>document.readyState==='complete');
      if(path==='/services') await page.locator(ready).first().waitFor();
      if(path==='/packages') await page.locator(ready).first().waitFor();
      await page.waitForTimeout(800);
      const metrics=await page.evaluate(()=>({cards:document.querySelectorAll('#servicesGrid .service-card,#packageList article').length,overflow:document.documentElement.scrollWidth>innerWidth,title:document.title,react:!!document.querySelector('script[type=module]')}));
      results.push({width,role,path,...metrics});
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/before-runtime-${width}-${path.replace(/\W+/g,'-')}.png`,fullPage:true});
    }
  }
  return results;
}
