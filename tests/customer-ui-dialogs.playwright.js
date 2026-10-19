// Playwright CLI: start on the target's public home page. All payment API data
// below is browser-mocked; no appointment, points, voucher or QR is changed live.
async page => {
  const origin=new URL(page.url()).origin, results=[], errors=[], requests=[];
  const manifestResponse=await page.request.get(origin+'/static/portal/.vite/manifest.json');
  if(!manifestResponse.ok())throw new Error('Build manifest is required to check the refactor stylesheet');
  const publicStyles=(await manifestResponse.json())['src/customer-main.ts'].css;
  page.on('pageerror',error=>errors.push(error.message));
  const state={wallet:{available_points:1000},redeem_enabled:true,max_points_allowed:1000,
    points_used:510,original_total:1500000,loyalty_discount:510000,payable_amount:990000};
  await page.route('**/api/payment/invoices/900001**',async route=>{
    const path=new URL(route.request().url()).pathname;
    requests.push({method:route.request().method(),path,mocked:true});
    const data=path.endsWith('/loyalty/preview')?{points_allowed:510,discount_amount:510000,payable_amount:990000}
      :path.endsWith('/loyalty')?state
      :path.endsWith('/generate-qr')?{qrCodeUrl:'/static/images/default-package.svg',accountName:'Tài khoản kiểm thử',accountNo:'TEST123',bank:'TEST',description:'TEST HD900001',amount:990000}
      :{trangthai:'Chưa thanh toán',tongtien:1500000,payable_amount:990000};
    await route.fulfill({json:data});
  });
  await page.route('**/api/loyalty/my-rewards?**',route=>route.fulfill({json:{items:[{id:900001,status:'available',code:'TEST-VOUCHER',reward:{name:'Voucher kiểm thử',reward_type:'voucher_amount',reward_value:50000,apply_to:'both'}}]}}));
  const expect=(condition,message)=>{if(!condition)throw new Error(message);};
  const inspect=async selector=>page.locator(selector).evaluate(root=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
    const context=canvas.getContext('2d',{willReadFrequently:true});
    const rgb=color=>{context.clearRect(0,0,1,1);context.fillStyle=color;context.fillRect(0,0,1,1);const p=context.getImageData(0,0,1,1).data;return [p[0],p[1],p[2],p[3]/255];};
    const mix=(a,b)=>a.slice(0,3).map((x,i)=>x*a[3]+b[i]*(1-a[3])).concat(1);
    const lum=color=>color.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
    const bg=e=>{const parents=[];for(let n=e;n;n=n.parentElement)parents.unshift(n);return parents.reduce((color,n)=>mix(rgb(getComputedStyle(n).backgroundColor),color),[255,255,255,1]);};
    const rect=root.getBoundingClientRect(),styles=getComputedStyle(root),buttons=[];
    for(const e of root.querySelectorAll('button')){
      const r=e.getBoundingClientRect();if(!r.width||!r.height||e.disabled||e.closest('[hidden]'))continue;
      const s=getComputedStyle(e),background=bg(e),values=[lum(mix(rgb(s.color),background)),lum(background)].sort((a,b)=>b-a);
      buttons.push({label:e.textContent.trim(),ratio:+((values[0]+.05)/(values[1]+.05)).toFixed(2),color:s.color,bg:s.backgroundColor});
    }
    return {x:rect.x,y:rect.y,width:rect.width,height:rect.height,viewport:innerWidth,viewportHeight:innerHeight,overflow:root.scrollWidth>root.clientWidth,font:styles.fontFamily,buttons};
  });
  for(const shell of ['legacy','refactor-css','booking']) {
    await page.goto(origin+(shell==='booking'?'/appointments/create':'/'),{waitUntil:'domcontentloaded'});
    if(shell==='booking')expect(await page.locator('body').evaluate(e=>e.classList.contains('customer-booking')),'Target does not expose the React booking shell');
    else await page.addStyleTag({url:origin+'/static/css/customers/profile.css'});
    // Exercise the shared dialogs against the built public CSS without changing
    // the server's rollout flags or claiming its public templates are enabled.
    if(shell==='refactor-css') {
      for(const file of publicStyles)await page.addStyleTag({url:origin+'/static/portal/'+file});
      await page.locator('body').evaluate(e=>e.classList.add('customer-ui'));
    }
    await page.addStyleTag({url:origin+'/static/css/change-services.css'});
    await page.addScriptTag({url:origin+'/static/js/change-services.js'});
    await page.waitForFunction(()=>window.ChangeServicesDialog&&window.LoyaltyPayment&&window.CustomerAuth);
    for(const width of [360,390,768,1024,1440]) {
      await page.setViewportSize({width,height:900});
      for(const count of width===1440?[2,55]:[55]) {
        await page.evaluate(count=>window.ChangeServicesDialog.open({title:'Đổi dịch vụ',subtitle:'Dữ liệu kiểm thử hiển thị',services:Array.from({length:count},(_,i)=>({madv:i+1,tendv:'Dịch vụ kiểm thử '+(i+1),gia:150000,thoiluong:45})),current:new Map([[1,{}]]),submit:async()=>{throw new Error('Không được gửi thay đổi trong kiểm thử giao diện');}}),count);
        const dialog=await inspect('#csDialog');
        expect(Math.abs(dialog.x-(width-dialog.width)/2)<2,'Change dialog is not horizontally centered '+shell+'/'+width);
        expect(Math.abs(dialog.y-(900-dialog.height)/2)<2,'Change dialog is not vertically centered '+shell+'/'+width);
        expect(!dialog.overflow,'Change dialog overflows horizontally '+shell+'/'+width);
        const footer=await page.locator('#csDialog .cs-actions').boundingBox();
        expect(footer.y+footer.height<=900,'Change actions are outside viewport '+shell+'/'+width);
        await page.locator('#csDialog [data-toggle="2"]').click();
        const save=await page.locator('#csDialog [data-save]').evaluate(e=>({enabled:!e.disabled,color:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor}));
        expect(save.enabled,'Service selection did not enable save');
        if([390,1440].includes(width))await page.screenshot({path:'.test-tmp/customer-ui-2026-10-19/change-after-'+shell+'-'+width+'-'+count+'.png'});
        await page.keyboard.press('Escape');
        await page.locator('#csDialog').waitFor({state:'detached'});
        expect(await page.locator('#csDialog').count()===0,'Change dialog did not close');
        results.push({shell,width,count,change:dialog,save});
      }
      await page.evaluate(()=>window.LoyaltyPayment.openCustomerInvoice(900001));
      await page.locator('#customerLoyaltyPayment [data-apply-voucher]').waitFor();
      const payment=await inspect('#customerLoyaltyPayment');
      expect(!payment.overflow,'Payment dialog overflows '+shell+'/'+width);
      expect(payment.buttons.length>=7,'Payment editor controls were not rendered');
      for(const button of payment.buttons)expect(button.ratio>=4.5,'Unreadable payment button '+JSON.stringify({shell,width,...button}));
      await page.locator('#customerLoyaltyPayment [data-preview]').click();
      await page.locator('#customerLoyaltyPayment [data-result]').filter({hasText:'Cho phép 510 điểm'}).waitFor();
      await page.locator('#customerLoyaltyPayment [data-max]').hover();await page.waitForTimeout(350);
      const hover=await inspect('#customerLoyaltyPayment');
      for(const button of hover.buttons)expect(button.ratio>=4.5,'Unreadable payment hover '+button.label);
      if([390,1440].includes(width))await page.screenshot({path:'.test-tmp/customer-ui-2026-10-19/payment-after-'+shell+'-'+width+'.png'});
      await page.locator('#customerLoyaltyPayment [data-pay]').click();
      await page.locator('#customerLoyaltyPayment [data-copy]').first().waitFor();
      const qr=await inspect('#customerLoyaltyPayment');
      for(const button of qr.buttons)expect(button.ratio>=4.5,'Unreadable QR button '+button.label);
      await page.locator('#customerLoyaltyPayment [data-close]').click();
      results.push({shell,width,payment,hover,qr});
    }
  }
  expect(errors.length===0,'Browser exceptions: '+JSON.stringify(errors));
  return {results,errors,requests};
}
