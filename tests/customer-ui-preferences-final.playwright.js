// E09 regression against disposable previews: 5080 flag on, 5077 flag off.
async page => {
 const base='http://127.0.0.1:5080',fields=['reminders','post_care','review_requests','personalization'];
 const errors=[],failed=[],results=[],typography=[];
 const assert=(value,message)=>{if(!value)throw new Error(message);};
 let stored,gets=0,puts=0,failGet=false,failPut=0,malformed=false,payloads=[];
 const reset=()=>{stored={version:0,...Object.fromEntries(fields.map(k=>[k,false]))};gets=puts=0;failGet=malformed=false;failPut=0;payloads=[];};
 page.on('pageerror',e=>errors.push(e.message));
 page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText});});
 await page.route('**/api/me/communication-preferences',async route=>{
  assert(new URL(route.request().url()).origin===base,'Preferences fixture reached a live server');
  const method=route.request().method();await new Promise(resolve=>setTimeout(resolve,120));
  if(method==='PUT'){
   puts++;const data=route.request().postDataJSON();payloads.push(data);
   assert(Object.keys(data).sort().join()===['version',...fields].sort().join(),'Preference payload contract changed');
   if(failPut){const status=failPut;failPut=0;return route.fulfill({status,json:{message:status===409?'Lựa chọn vừa được thay đổi ở nơi khác. Tải lại trước khi lưu.':status===400?'Lựa chọn chưa hợp lệ. Vui lòng kiểm tra lại.':'Chưa xác nhận được kết quả lưu. Vui lòng tải lại.'}});}
   assert(data.version===stored.version,'Stale preference version submitted');
   stored={...data,version:stored.version+1};return route.fulfill({json:stored});
  }
  gets++;
  if(failGet)return route.fulfill({status:503,json:{message:'Chưa tải được lựa chọn từ máy chủ.'}});
  return route.fulfill({json:malformed?{...stored,version:'wrong'}:stored});
 });
 const measure=async(mode,width,state)=>{
  const report=await page.locator('#communication-section').evaluate(root=>{
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const rgb=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=c;ctx.fillRect(0,0,1,1);const d=ctx.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
   const mix=(a,b)=>a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3])).concat(1);
   const lum=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
   const issues=[];let minimum=21,checked=0;
   for(const e of root.querySelectorAll('*')){
    if(![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())||!e.getBoundingClientRect().width||e.closest('[hidden]'))continue;
    const style=getComputedStyle(e);if(style.visibility!=='visible')continue;
    const chain=[];for(let n=e;n;n=n.parentElement)chain.unshift(n);let bg=[255,255,255,1];for(const n of chain)bg=mix(rgb(getComputedStyle(n).backgroundColor),bg);
    const values=[lum(mix(rgb(style.color),bg)),lum(bg)].sort((a,b)=>b-a),ratio=(values[0]+.05)/(values[1]+.05);checked++;minimum=Math.min(minimum,ratio);
    if(ratio<4.5)issues.push({tag:e.tagName,color:style.color,ratio});
    if(/serif/i.test(style.fontFamily)&&!/sans-serif/i.test(style.fontFamily))issues.push({tag:e.tagName,font:style.fontFamily});
   }
   return {checked,minimum:+minimum.toFixed(2),issues,overflow:root.scrollWidth>root.clientWidth||document.documentElement.scrollWidth>innerWidth};
  });
  assert(!report.overflow&&report.issues.length===0,'Preferences typography '+JSON.stringify({mode,width,state,...report}));typography.push({mode,width,state,...report});
 };
 const ready=()=>page.locator('#communicationPreferences [type=submit]:enabled').waitFor();
 const locked=async()=>assert(await page.locator('#communicationPreferences fieldset:disabled').count()===2&&await page.locator('#communicationPreferences [type=submit]').isDisabled(),'Unknown/stale consent can be edited or submitted');
 await page.request.get(base+'/__preview/session?customer=1');
 for(const mode of ['legacy','refactor']){
  reset();await page.goto(base+'/');await page.goto(base+'/profile'+(mode==='legacy'?'?ui=legacy':'')+'#reviews');
  await page.locator('#myReviews').waitFor();assert(gets===0,'Preferences loaded while hidden');
  await page.locator('.menu-link[data-section=communication]').click();await ready();
  assert(await page.locator('#communication-section .section-title').evaluate(e=>getComputedStyle(e).textAlign)==='left','Preference heading is inconsistent with account sections');
  assert(gets===1&&puts===0,'Initial preferences duplicated or automatically saved');
  assert(await page.locator('#communicationPreferences input:checked').count()===0,'UI opted in without server consent');
  for(const width of [360,390,768,1024,1440]){
   await page.setViewportSize({width,height:960});await measure(mode,width,'unchecked');
   await page.locator('[name=reminders]').focus();await page.keyboard.press('Space');
   assert(await page.locator('[name=reminders]').isChecked(),'Keyboard could not toggle choice');await measure(mode,width,'checked');
   await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
   await page.screenshot({path:'.test-tmp/customer-ui-final/'+mode+'-preferences-'+width+'.png',fullPage:true});
   await page.locator('[name=reminders]').uncheck();
  }
  await page.locator('[name=reminders]').check();await page.locator('#communicationPreferences').evaluate(form=>{form.requestSubmit();form.requestSubmit();});
  await page.getByText('Đã lưu lựa chọn của bạn.',{exact:true}).waitFor();
  assert(puts===1&&payloads[0].version===0&&stored.version===1&&fields.slice(1).every(k=>payloads[0][k]===false),'Duplicate save, version lost or extra opt-in');
  await page.reload();await ready();assert(await page.locator('[name=reminders]').isChecked(),'Saved preference not restored after reload');
  await page.locator('[name=post_care]').check();failPut=400;await page.locator('#communicationPreferences [type=submit]').click();
  await page.getByText('Lựa chọn chưa hợp lệ. Vui lòng kiểm tra lại.',{exact:true}).waitFor();await ready();
  assert(await page.locator('[name=post_care]').isChecked(),'Validation error lost draft');
  failPut=409;stored={...stored,version:2};await page.locator('#communicationPreferences [type=submit]').click();
  await page.getByText('Lựa chọn vừa được thay đổi ở nơi khác. Tải lại trước khi lưu.',{exact:true}).waitFor();await locked();
  assert(payloads.at(-1).version===1,'Conflict request did not send original version');
  const before=puts;await page.locator('#communicationPreferences').evaluate(f=>f.requestSubmit());assert(puts===before,'Conflict can be silently overwritten');
  await page.setViewportSize({width:390,height:960});await measure(mode,390,'conflict-disabled');
  failGet=true;await page.locator('#reloadCommunicationPreferences').click();await page.getByText('Chưa tải được lựa chọn từ máy chủ.',{exact:true}).waitFor();await locked();await measure(mode,390,'load-error');
  failGet=false;await page.locator('#reloadCommunicationPreferences').click();await ready();
  assert(await page.locator('[name=post_care]').isChecked()===false,'Reload did not restore authoritative server choice');
  await page.locator('[name=review_requests]').check();failPut=503;await page.locator('#communicationPreferences [type=submit]').click();
  await page.getByText('Chưa xác nhận được kết quả lưu. Vui lòng tải lại.',{exact:true}).waitFor();await locked();
  malformed=true;await page.locator('#reloadCommunicationPreferences').click();await page.getByText('Chưa nhận được lựa chọn hợp lệ. Vui lòng tải lại.',{exact:true}).waitFor();await locked();
  malformed=false;await page.locator('#reloadCommunicationPreferences').click();await ready();
  await page.locator('[name=personalization]').check();await page.locator('#communicationPreferences [type=submit]').click();await page.getByText('Đã lưu lựa chọn của bạn.',{exact:true}).waitFor();
  assert(stored.personalization&&payloads.at(-1).version===2&&stored.version===3,'Reloaded version not used');
  await page.locator('[name=personalization]').uncheck();await page.locator('#communicationPreferences [type=submit]').click();await page.getByText('Đã lưu lựa chọn của bạn.',{exact:true}).waitFor();
  assert(!stored.personalization&&payloads.at(-1).version===3,'Explicit personalization opt-out not sent');
  results.push({mode,lazy:true,noAutoOptIn:true,keyboard:true,singleSubmit:true,reload:true,validationDraft:true,conflictLocked:true,failedReloadLocked:true,uncertainSaveLocked:true,invalidResponseLocked:true,versionPreserved:true,gets,puts});
 }
 await page.request.get('http://127.0.0.1:5077/__preview/session?customer=1');await page.goto('http://127.0.0.1:5077/profile#communication');
 assert(await page.locator('#communication-section,.menu-link[data-section=communication]').count()===0,'Flag off exposes preferences');
 assert(!await page.evaluate(()=>performance.getEntriesByType('resource').some(r=>r.name.includes('communication-preferences'))),'Flag off still loads preference assets');
 assert(errors.length===0&&failed.length===0,'Unexpected preferences failures '+JSON.stringify({errors,failed}));
 return {results,typography,flagOffHidden:true,errors,failed};
}
