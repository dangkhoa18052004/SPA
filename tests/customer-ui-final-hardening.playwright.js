// F01/F02/F03: chat lifecycle, compact viewports and metadata on a disposable preview.
async page => {
 const base='http://127.0.0.1:5080',errors=[],failed=[],checks=[],layouts=[];
 const assert=(value,message)=>{if(!value)throw new Error(message);};
 page.on('pageerror',e=>errors.push(e.message));
 page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText});});
 await page.addInitScript(()=>{
  const realSet=window.setInterval.bind(window),realClear=window.clearInterval.bind(window);
  window.__chatTimers=new Set();
  window.setInterval=(callback,delay,...args)=>{const id=realSet(callback,delay,...args);if(delay===10000)window.__chatTimers.add(id);return id;};
  window.clearInterval=id=>{window.__chatTimers.delete(id);realClear(id);};
 });
 await page.request.get(base+'/__preview/session?customer=1');await page.goto(base+'/');
 await page.waitForFunction(()=>!!window.CustomerAuth.getAccessToken());
 assert(await page.evaluate(()=>window.__chatTimers.size)===1,'Chat did not start exactly one refresh loop');
 await page.evaluate(()=>{setupChatRefresh();setupChatRefresh();});
 assert(await page.evaluate(()=>window.__chatTimers.size)===1,'Repeated initialization duplicates chat polling');
 await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
 assert(await page.evaluate(()=>window.__chatTimers.size)===0,'Chat continues polling while page is suspended');
 await page.evaluate(()=>{dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));});
 assert(await page.evaluate(()=>window.__chatTimers.size)===1,'Restored Back/Forward page does not resume exactly one loop');
 await page.evaluate(()=>{dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));CustomerAuth.clearLocalSession();dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));});
 assert(await page.evaluate(()=>window.__chatTimers.size)===0,'Signed-out restored page resumed authenticated polling');
 checks.push('Chat: one loop, suspended on pagehide, resumed once on persisted pageshow, stays stopped without a session');
 await page.goto(base+'/');
 for(const width of [360,390,768,1024,1440]){
  await page.setViewportSize({width,height:600});
  await page.goto(base+'/services/1');
  await page.locator('.service-detail-name').waitFor();
  const meta=await page.evaluate(()=>({title:document.title,description:document.querySelector('meta[name=description]')?.content,canonical:document.querySelector('link[rel=canonical]')?.href,overflow:document.documentElement.scrollWidth>innerWidth,portal:performance.getEntriesByType('resource').some(r=>/\/portal-[^/]+\.js/.test(r.name))}));
  assert(meta.title&&meta.description&&meta.canonical.endsWith('/services/1')&&!meta.portal&&!meta.overflow,'Metadata/public bundle issue '+JSON.stringify(meta));
  if(width<768){
   await page.locator('#chatFloat').click();await page.locator('#chatBox.show').waitFor();
   const geometry=await page.locator('#chatBox').evaluate(root=>{const box=root.getBoundingClientRect(),input=root.querySelector('#chatInput').getBoundingClientRect();return {top:box.top,bottom:box.bottom,inputBottom:input.bottom,height:innerHeight,overflow:root.scrollWidth>root.clientWidth};});
   assert(geometry.top>=0&&geometry.bottom<=geometry.height&&geometry.inputBottom<=geometry.height&&!geometry.overflow,'Chat input is outside compact viewport '+JSON.stringify(geometry));
   await page.screenshot({path:'.test-tmp/customer-ui-final/chat-compact-'+width+'.png'});
   await page.keyboard.press('Escape');
   assert(await page.locator('#chatFloat').evaluate(e=>e===document.activeElement),'Chat ESC did not restore focus');
   layouts.push({width,...geometry});
  }
 }
 checks.push('Service metadata/canonical, public entry excludes portal, compact-height chat input visible');
 // This is CSS text resizing, deliberately not reported as native browser zoom.
 await page.setViewportSize({width:720,height:480});await page.goto(base+'/profile#communication');
 await page.locator('#communicationPreferences [type=submit]:enabled').waitFor();
 await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Preferences text resize overflows compact viewport');
 checks.push('Preferences at compact 720x480 and 200% root text resize');
 assert(errors.length===0&&failed.length===0,'Unexpected final hardening failures '+JSON.stringify({errors,failed}));
 return {checks,layouts,errors,failed,limits:'Synthetic page lifecycle events and compact viewports; native browser zoom and physical mobile keyboard are separate acceptance checks.'};
}
