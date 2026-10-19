// Run against tests/customer_ui_preview.py --new-ui --port 5080.
// Package data and failures are browser fixtures; this test submits no purchases.
async page => {
  const base='http://127.0.0.1:5080', checks=[], errors=[], failed=[], expectedHttp=[], typography=[];
  let listMode='normal', purchaseError=false, historyError=true, listCalls=0, purchaseCalls=0, historyCalls=0;
  const item={id:8,madv:1,tendv:'Massage thư giãn với tên dịch vụ dài để kiểm tra xuống dòng',source_type:'package',total_sessions:5,consumed:2,reserved:1,available_sessions:2,usable:true,effective_expires_at:'2029-01-20'};
  const cards=[{mathe:101,tengoi:'Liệu trình chăm sóc với tên dài và <nội dung API> phải được hiển thị an toàn',status:'active',image_url:'/static/images/default-package.svg',purchased_at:'2026-10-01',activated_at:'2026-10-02',expires_at:'2029-01-20',items:[item,{...item,id:9,source_type:'gift',tendv:'Quà tặng chăm sóc cơ thể',total_sessions:2,consumed:0,reserved:0,available_sessions:2,valid_from:'2026-10-01',effective_expires_at:'2029-03-20'}]},
    {mathe:102,tengoi:'Liệu trình đã hết hạn',status:'expired',purchased_at:'2025-01-01',expires_at:'2025-04-01',items:[{...item,id:10,usable:false,effective_expires_at:'2025-04-01'}]},
    {mathe:103,tengoi:'Liệu trình đã hủy',status:'cancelled',purchased_at:'2026-10-01',expires_at:null,items:[{...item,id:11,usable:false}]}];
  const purchases=[{id:401,tengoi:'Gói đang chờ thanh toán',status:'pending',amount:600000,payable_amount:450000},{id:402,tengoi:'Gói đã thanh toán',status:'paid',amount:600000}];
  const assert=(condition,message)=>{if(!condition)throw new Error(message);};
  page.on('pageerror',error=>errors.push(error.message));
  page.on('requestfailed',request=>{if(request.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText});});
  await page.route('**/api/packages/my-treatments',async route=>{
    listCalls++;const mode=listMode;
    if(mode==='delayed'||mode==='stale')await new Promise(resolve=>setTimeout(resolve,700));
    if(mode==='error'){expectedHttp.push(503);return route.fulfill({status:503,json:{message:'Mất kết nối kiểm thử'}});}
    return route.fulfill({json:{success:true,treatments:mode==='empty'?[]:mode==='stale'?[{...cards[0],tengoi:'Dữ liệu cũ không được ghi đè'}]:cards}});
  });
  await page.route('**/api/packages/my-purchases',route=>{
    purchaseCalls++;
    if(purchaseError){expectedHttp.push(503);return route.fulfill({status:503,json:{message:'Không tải được giao dịch kiểm thử'}});}
    return route.fulfill({json:{success:true,purchases}});
  });
  await page.route('**/api/packages/my-treatments/*',async route=>{
    historyCalls++;await new Promise(resolve=>setTimeout(resolve,200));
    if(historyError){expectedHttp.push(503);return route.fulfill({status:503,json:{message:'Lỗi lịch sử kiểm thử'}});}
    return route.fulfill({json:{success:true,treatment:{...cards[0],history:[
      {id:1,malh:94,the_item_id:8,tendv:item.tendv,source_type:'package',state:'reserved',reserved_at:'2026-10-19'},
      {id:2,malh:93,the_item_id:9,tendv:'Quà tặng chăm sóc cơ thể',source_type:'gift',state:'consumed',consumed_at:'2026-10-18'},
      {id:3,malh:92,the_item_id:8,tendv:item.tendv,source_type:'package',state:'released',released_at:'2026-10-17'},
    ]}}});
  });
  await page.request.get(base+'/__preview/session?customer=1');
  await page.goto(base+'/profile#info');
  await page.waitForFunction(()=>document.querySelector('#userName')?.textContent!=='Đang tải…');
  assert(listCalls===0&&purchaseCalls===0,'Treatments were fetched before the tab became active');
  listMode='delayed';
  await page.locator('.menu-link[data-section=treatments]').click();
  await page.getByText('Đang tải liệu trình…',{exact:true}).waitFor();
  await page.locator('#myTreatments .customer-treatment').first().waitFor();
  listMode='normal';
  assert(await page.locator('#myTreatments .customer-treatment').count()===3,'Missing treatment cards');
  assert(await page.locator('#myTreatments .customer-treatment-group').filter({hasText:'Dịch vụ tặng'}).count()===1,'Gifts were not separated');
  assert(await page.locator('#myTreatments article').nth(1).locator('a[href^="/appointments/create"]').count()===0,'Expired item can be booked');
  assert(await page.locator('#myTreatments article').nth(2).locator('a[href^="/appointments/create"]').count()===0,'Cancelled item can be booked');
  assert((await page.locator('#myPackagePurchases').innerText()).includes('450.000'),'Pending purchase ignores server payable amount');
  assert(await page.locator('#myPackagePurchases a').getAttribute('href')==='/packages?purchase=401','Purchase resume ID changed');
  assert(await page.locator('#myTreatments nội-dung-api,#myTreatments nội').count()===0,'API text became HTML');
  checks.push('Lazy loading, loading state, mixed package/gift availability and pending purchase');
  const firstHistory=page.locator('#myTreatments [data-history="101"]');
  await firstHistory.evaluate(button=>{button.click();button.click();});
  await page.locator('#history-101 [role=alert]').waitFor();
  assert(historyCalls===1,'Repeated history click issued duplicate requests');
  historyError=false;
  await firstHistory.click();
  await page.locator('#history-101 .customer-treatment-timeline').waitFor();
  assert((await page.locator('#history-101').innerText()).includes('Lượt tặng'),'History lost gift source');
  assert((await page.locator('#history-101').innerText()).includes('Đã trả lại lượt'),'History lost released state');
  await firstHistory.click();
  assert(await firstHistory.getAttribute('aria-expanded')==='false','History collapse state is wrong');
  await firstHistory.click();
  await page.locator('#history-101 .customer-treatment-timeline').waitFor();
  assert(historyCalls===3,'History was not refreshed on reopen');
  checks.push('History request deduplication, retry, collapse and fresh reopen');
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});
    await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);});
    await page.waitForTimeout(200);
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Treatments overflow '+width);
    const style=await page.locator('#myTreatments').evaluate(e=>({font:getComputedStyle(e).fontFamily,color:getComputedStyle(e).color}));
    assert(style.font.includes('Segoe UI'),'Treatment font is not the shared system font');
    const contrast=await page.locator('#treatments-section').evaluate(root=>{
      const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
      const context=canvas.getContext('2d',{willReadFrequently:true});
      const rgb=color=>{context.clearRect(0,0,1,1);context.fillStyle=color;context.fillRect(0,0,1,1);const d=context.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
      const mix=(a,b)=>a.slice(0,3).map((x,i)=>x*a[3]+b[i]*(1-a[3])).concat(1);
      const lum=color=>color.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
      let minimum=21,checked=0;const issues=[];
      for(const e of root.querySelectorAll('*')){
        if(![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())||!e.getBoundingClientRect().width||e.closest('[hidden]'))continue;
        const parents=[];for(let n=e;n;n=n.parentElement)parents.unshift(n);
        const bg=parents.reduce((c,n)=>mix(rgb(getComputedStyle(n).backgroundColor),c),[255,255,255,1]);
        const s=getComputedStyle(e),l=[lum(mix(rgb(s.color),bg)),lum(bg)].sort((a,b)=>b-a),ratio=(l[0]+.05)/(l[1]+.05);
        checked++;minimum=Math.min(minimum,ratio);
        if(ratio<4.5)issues.push({tag:e.tagName,color:s.color,ratio});
      }
      return {checked,minimum:+minimum.toFixed(2),issues};
    });
    assert(contrast.issues.length===0,'Treatment text lacks contrast '+JSON.stringify(contrast.issues));
    typography.push({width,...style,...contrast});
    if([390,1440].includes(width))await page.screenshot({path:'.test-tmp/customer-ui-treatments/after-'+width+'.png',fullPage:true});
  }
  purchaseError=true;
  await page.evaluate(()=>window.PackageCare.loadTreatments());
  await page.locator('#myPackagePurchases [role=alert]').waitFor();
  assert(await page.locator('#myTreatments .customer-treatment').count()===3,'Purchase failure erased valid treatments');
  const previousListCalls=listCalls;purchaseError=false;
  await page.locator('[data-retry-purchases]').click();
  await page.locator('.customer-treatment-purchases').waitFor();
  assert(listCalls===previousListCalls,'Purchase retry reloaded unrelated treatment cards');
  listMode='error';await page.evaluate(()=>window.PackageCare.loadTreatments());
  await page.locator('#myTreatments [role=alert]').waitFor();
  listMode='normal';await page.locator('[data-retry-treatments]').click();
  await page.locator('#myTreatments .customer-treatment').first().waitFor();
  listMode='empty';await page.evaluate(()=>window.PackageCare.loadTreatments());
  await page.locator('#myTreatments .package-empty').waitFor();
  assert(await page.locator('.customer-treatment-purchases').count()===1,'Pending purchase disappeared on empty treatments');
  checks.push('Independent purchase failure/retry, list failure/retry and empty state');
  listMode='stale';const previous=listCalls;
  await page.evaluate(()=>{void window.PackageCare.loadTreatments();});
  while(listCalls===previous)await page.waitForTimeout(25);
  listMode='normal';await page.evaluate(()=>window.PackageCare.loadTreatments());
  await page.waitForTimeout(800);
  assert(!(await page.locator('#myTreatments').innerText()).includes('Dữ liệu cũ'),'Stale response overwrote newer data');
  checks.push('Stale response cannot overwrite a newer refresh');
  await page.locator('a[href="/appointments/create?treatment=101&service=1&item=9"]').click();
  await page.locator('[data-treatment-service="1"]').waitFor();
  assert(await page.locator('[data-treatment-service="1"]').inputValue()==='9','Booking did not keep the gifted treatment item');
  checks.push('Gift booking deep link preserves treatment/service/item selection');
  await page.goto(base+'/profile?ui=legacy#treatments');
  await page.locator('#myTreatments .treatment-card').first().waitFor();
  assert(!await page.evaluate(()=>!!window.CustomerTreatments),'Legacy fallback loaded the new treatment renderer');
  assert(await page.locator('#myTreatments .customer-treatment').count()===0,'Two treatment renderers own the legacy root');
  checks.push('Legacy fallback remains independent');
  assert(errors.length===0,'Unexpected browser exception '+JSON.stringify(errors));
  assert(failed.length===0,'Unexpected failed request '+JSON.stringify(failed));
  return {checks,viewports:[360,390,768,1024,1440],typography,listCalls,purchaseCalls,historyCalls,expectedHttp,errors,failed};
}
