// Only run against the disposable loopback preview. Creates/cancels fixture
// purchases, never touches the LAN server's orders or a payment provider.
async page => {
  const base='http://127.0.0.1:5080', checks=[],errors=[],failed=[];
  let cancelPosts=0, failNext=false;
  const assert=(condition,message)=>{if(!condition)throw new Error(message);};
  page.on('pageerror',e=>errors.push(e.message));
  page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText});});
  await page.route('**/api/packages/purchases/*/cancel',async route=>{
    assert(new URL(route.request().url()).origin===base,'Cancellation must only use the disposable preview');
    cancelPosts++;
    await new Promise(resolve=>setTimeout(resolve,250));
    if(failNext){failNext=false;return route.fulfill({status:503,json:{message:'Lỗi mạng kiểm thử, vui lòng thử lại.'}});}
    await route.continue();
  });
  await page.request.get(base+'/__preview/session?customer=1');
  for(const mode of ['legacy','refactor']){
    const path='/profile'+(mode==='legacy'?'?ui=legacy':'')+'#treatments';
    await page.goto(base+path);
    await page.waitForFunction(()=>window.PackageCare&&window.CustomerAuth?.getAccessToken());
    const ids=await page.evaluate(async()=>{
      const packageId=(await window.PackageCare.api('/api/packages')).packages[0].magoi;
      const ids=[];
      for(let i=0;i<2;i++)ids.push((await window.PackageCare.api(`/api/packages/${packageId}/purchase`,'POST',{payment_method:'cash'})).purchase.id);
      await window.PackageCare.loadTreatments();return ids;
    });
    const purchaseButton=id=>page.locator(`#myPackagePurchases [data-cancel-purchase="${id}"]`);
    await purchaseButton(ids[0]).waitFor();
    assert(await page.evaluate(()=>!!window.CustomerTreatments)===(mode==='refactor'),'Wrong treatment renderer');
    for(const width of [360,390,768,1024,1440]){
      await page.setViewportSize({width,height:900});
      await purchaseButton(ids[0]).click();
      await page.locator('#packageCancelDialog').waitFor();
      const geometry=await page.locator('#packageCancelDialog').evaluate(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,overflow:e.scrollWidth>e.clientWidth};});
      assert(geometry.x>=0&&geometry.right<=width+1&&geometry.y>=0&&geometry.bottom<=901&&!geometry.overflow,'Cancel dialog does not fit '+mode+'/'+width);
      assert(await page.locator('[data-keep]').evaluate(e=>e===document.activeElement),'Confirmation should focus the non-destructive choice');
      if([390,1440].includes(width))await page.screenshot({path:'.test-tmp/customer-purchase-cancel/confirm-'+mode+'-'+width+'.png'});
      await page.locator('[data-keep]').click();
      await page.locator('#packageCancelDialog').waitFor({state:'detached'});
    }
    assert(cancelPosts===(mode==='legacy'?0:3),'Keeping a purchase submitted cancellation');
    const before=cancelPosts;
    await purchaseButton(ids[0]).click();
    await page.locator('[data-confirm-cancel]').evaluate(e=>{e.click();e.click();});
    await page.locator('#packageCancelDialog').waitFor({state:'detached'});
    assert(cancelPosts===before+1,'Double click sent duplicate cancellation');
    assert(await purchaseButton(ids[0]).count()===0,'Cancelled purchase remained in pending list');
    assert(await purchaseButton(ids[1]).count()===1,'Cancelling one purchase removed another');
    await page.reload();await purchaseButton(ids[1]).waitFor();
    assert(await purchaseButton(ids[0]).count()===0,'Cancelled purchase returned after reload');
    failNext=true;
    await purchaseButton(ids[1]).click();await page.locator('[data-confirm-cancel]').click();
    await page.locator('[data-cancel-error]').filter({hasText:'Lỗi mạng kiểm thử'}).waitFor();
    const pending=await page.evaluate(id=>window.PackageCare.api(`/api/packages/purchases/${id}`),ids[1]);
    assert(pending.purchase.status==='pending','A failed cancellation removed the live fixture purchase');
    await page.locator('[data-confirm-cancel]').click();
    await page.locator('#packageCancelDialog').waitFor({state:'detached'});
    assert(await page.locator('#myPackagePurchases [data-cancel-purchase]').count()===0,'Last cancelled purchase still appears');
    assert((await page.locator('#packagePurchaseStatus').innerText()).includes('Đã hủy'),'No success feedback');
    const cancelled=await page.evaluate(id=>window.PackageCare.api(`/api/packages/purchases/${id}`),ids[0]);
    assert(cancelled.purchase.status==='cancelled','Cancellation did not persist on server');
    await page.goto(base+`/packages?purchase=${ids[0]}`);
    await page.locator('#packagePayment').filter({hasText:'không còn chờ thanh toán'}).waitFor();
    assert(await page.locator('#packagePayment [data-reveal-qr],#packagePayment [data-package-loyalty],#packagePayment [data-pay-points]').count()===0,'Cancelled purchase still offers payment');
    checks.push({mode,viewports:[360,390,768,1024,1440],confirmation:true,singlePost:true,persistentRemoval:true,unrelatedPurchasePreserved:true,errorRetry:true,cancelledResumeHasNoPayment:true});
  }
  assert(errors.length===0,'Browser exception '+JSON.stringify(errors));
  assert(failed.length===0,'Failed request '+JSON.stringify(failed));
  return {checks,cancelPosts,expectedFailures:2,errors,failed};
}
