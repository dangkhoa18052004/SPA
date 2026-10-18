async page => {
  await page.context().unrouteAll({behavior:'ignoreErrors'});
  const state = {errors:[],failed:[],httpErrors:[],blocked:[],pages:[]};
  await page.context().route('**/*', route => {
    if (!['127.0.0.1','localhost','[::1]'].includes(new URL(route.request().url()).hostname)) {state.blocked.push(route.request().url());return route.abort('blockedbyclient');}
    return route.continue();
  });
  const error = e => state.errors.push({page:page.url(),message:e.message});
  const failed = r => {if (new URL(r.url()).hostname==='127.0.0.1') state.failed.push({url:r.url(),error:r.failure()?.errorText});};
  const response = r => {if(r.status()>=400) state.httpErrors.push({page:page.url(),url:r.url(),status:r.status()});};
  page.on('pageerror',error);page.on('requestfailed',failed);page.on('response',response);
  const routes=[['home','/'],['services','/services'],['detail','/services/3'],['booking','/appointments/create'],['login','/auth/login']];
  for(const width of [1920,1366,768,390]) {
    await page.setViewportSize({width,height:width===390?844:width===768?1024:1080});
    for(const [name,path] of routes){
      const res=await page.goto('https://127.0.0.1:5000'+path,{waitUntil:'domcontentloaded'});
      const ready={home:'.service-card',services:'.service-card',detail:'.service-detail-name',booking:'#root form, #appointmentForm, .booking-login-gate, .booking-step, .booking-service-card',login:'#loginForm'}[name];
      try {await page.locator(ready).first().waitFor({state:'visible',timeout:8000});} catch{}
      await page.evaluate(()=>document.fonts.ready);
      const data=await page.evaluate(()=>({title:document.title,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,brokenImages:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>({src:i.getAttribute('src')?.slice(0,100),alt:i.alt})),overflow:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&s.position!=='fixed'&&(r.right>innerWidth+2||r.left < -2)&&s.visibility!=='hidden'&&s.display!=='none';}).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.trim().slice(0,50)})),headings:[...document.querySelectorAll('h1,h2')].map(e=>e.textContent.trim()).slice(0,5)}));
      state.pages.push({name,status:res.status(),...data});
      await page.screenshot({path:'output/binspa-qa/'+name+'-'+width+'-before.png',fullPage:true,animations:'disabled'});
    }
  }
  page.off('pageerror',error);page.off('requestfailed',failed);page.off('response',response);
  state.blocked=[...new Set(state.blocked)];
  return state;
}
