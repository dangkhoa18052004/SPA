async (page, ctx) => {
  // Isolated fixture only (tests/master_ui_preview.py --port 5091 --all-ui). Each run creates its own sale.
  const base='http://127.0.0.1:5091', out=ctx?.out||'output/ui-review-2026-10-21', checks=[], errors=[];
  const assert=(value,message)=>{if(!value)throw Error(message);};
  const onError=e=>errors.push(e.message);
  page.on('pageerror',onError);
  let posts=0;
  const onRequest=r=>{if(/\/api\/admin\/packages\/treatments\/\d+\/gifts$/.test(r.url())&&r.method()==='POST')posts++;};
  page.on('request',onRequest);
  const login=async role=>{
    await page.goto(base+'/__qa/ping');
    await page.evaluate(async role=>{
      localStorage.clear();
      const d=await(await fetch('/__qa/login/'+role)).json();
      localStorage.setItem(role==='customer'?'access_token':'admin_token',d.access_token);
      if(role!=='customer')localStorage.setItem('admin_role',d.role);
    },role);
  };
  const call=(path,method='GET',body)=>page.evaluate(async([path,method,body])=>{
    const token=localStorage.getItem('admin_token')||localStorage.getItem('access_token');
    const r=await fetch(path,{method,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:body?JSON.stringify(body):undefined});
    return {status:r.status,data:await r.json().catch(()=>({}))};
  },[path,method,body]);
  const get=async path=>(await call(path)).data;
  // Ant Select keeps closing popups in the DOM; scope options to the popup this combobox controls.
  const popup=async box=>{const id=await box.getAttribute('aria-controls');return page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').filter({has:page.locator(`[id="${id}"]`)});};
  const pickByMouse=async(box,term,label)=>{await box.click();await box.fill(term);const option=(await popup(box)).locator('.ant-select-item-option').filter({hasText:label});await option.waitFor();await option.click();};
  const pickByKeyboard=async(box,term,label)=>{await box.focus();await box.press('ArrowDown');await box.fill(term);
    await (await popup(box)).locator('.ant-select-item-option-active').filter({hasText:label}).waitFor();await box.press('Enter');};
  try {
    await login('admin');
    await page.setViewportSize({width:1440,height:900});
    await page.goto(base+'/admin/package-sales');
    await pickByMouse(page.getByRole('combobox',{name:'Khách hàng',exact:true}),'0900000002','Khách hàng Test');
    const packageBox=page.getByRole('combobox',{name:'Gói dịch vụ',exact:true});
    await pickByKeyboard(packageBox,'Gói kiểm thử 01','Gói kiểm thử 01');
    assert((await packageBox.locator('xpath=ancestor::div[contains(@class,"ant-select")][1]').textContent()).includes('Gói kiểm thử 01'),'Package chosen with keyboard');
    checks.push('P0-02 customer Select by mouse+search, package Select by keyboard+search');
    const created=page.waitForResponse(r=>r.url().endsWith('/api/admin/package-sales')&&r.request().method()==='POST');
    await page.getByTestId('sale-create').click();
    const purchaseId=(await(await created).json()).purchase.id;
    await page.getByRole('button',{name:'Xác nhận đã nhận tiền',exact:true}).waitFor();
    assert(await page.locator('.ant-modal').getByRole('button',{name:'Tặng thêm dịch vụ'}).count()===0,'G02 no gift before payment');
    const pending=(await get(`/api/admin/package-sales/${purchaseId}`)).purchase;
    assert(pending.status==='pending'&&!pending.mathe,'G02 pending purchase has no treatment');
    await page.getByRole('button',{name:'Xác nhận đã nhận tiền',exact:true}).click();
    await page.getByTestId('package-paid').waitFor();
    const paid=(await get(`/api/admin/package-sales/${purchaseId}`)).purchase;
    const treatment=paid.mathe;
    assert(paid.status==='paid'&&!!treatment,'Payment activated this purchase treatment');
    await page.getByTestId('package-paid').getByRole('button',{name:'Tặng thêm dịch vụ'}).click();
    const modal=page.getByRole('dialog',{name:'Tặng dịch vụ',exact:true});
    await modal.waitFor();
    for(const width of [360,390,768,1024,1440]){
      await page.setViewportSize({width,height:900});
      await page.waitForTimeout(400);
      assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),'Gift page overflow '+width);
      const bounds=await modal.locator('.ant-modal-content').boundingBox();assert(bounds.x>=0&&bounds.x+bounds.width<=width+1,'Gift modal fits '+width);
      await page.screenshot({path:`${out}/gift-form-${width}.png`});
    }
    await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click();
    await modal.getByText('Chọn dịch vụ',{exact:true}).waitFor();
    assert(posts===0,'G05 missing service rejected before POST');
    await pickByMouse(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 02','Dịch vụ 02 massage trong tên');
    await modal.getByLabel('Số buổi',{exact:true}).fill('2');
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Số ngày'}).click();
    await modal.getByRole('spinbutton',{name:'Số ngày'}).fill('30');
    await modal.getByLabel('Ghi chú',{exact:true}).fill('Tặng khi mua combo — kiểm thử riêng');
    await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).evaluate(b=>{b.click();b.click();});
    await modal.waitFor({state:'hidden'});
    let detail=(await get('/api/admin/packages/treatments/'+treatment)).treatment;
    const gifts=detail.items.filter(i=>i.source_type==='gift');
    const gift=gifts[0];
    assert(posts===1&&gifts.length===1,'G09 one POST and one gift row after double click');
    assert(gift.total_sessions===2&&gift.available_sessions===2&&!!gift.effective_expires_at&&!!gift.gifted_by_staff,'G01 two-session gift with expiry and staff audit');
    const afterGift=(await get(`/api/admin/package-sales/${purchaseId}`)).purchase;
    assert(afterGift.amount===paid.amount&&afterGift.payable_amount===paid.payable_amount,'G01 sale amount unchanged by gift');
    checks.push('G01/G02/G05/G09 sale -> payment -> gift, five viewports, double-click guard, price unchanged');
    await page.setViewportSize({width:1440,height:900});
    await page.screenshot({path:`${out}/gift-treatment-admin.png`,fullPage:true});
    // G03 + G10: gift the service already in the package; the server commits but the response is lost.
    const paidItem=detail.items.find(i=>i.source_type!=='gift');
    await page.goto(base+`/admin/packages?tab=treatments&mathe=${treatment}&gift=1`);
    await modal.waitFor();
    await pickByMouse(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),paidItem.tendv.slice(0,10),paidItem.tendv);
    const giftRoute='**/api/admin/packages/treatments/*/gifts';
    await page.route(giftRoute,async route=>{
      const result=await route.fetch();
      await route.fulfill({status:502,json:{message:result.status()===201?'Simulated lost response':'Unexpected '+result.status()}});
    });
    try {
      await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click();
      await modal.getByRole('button',{name:'Kiểm tra liệu trình',exact:true}).click();
      await modal.waitFor({state:'hidden'});
    } finally { await page.unroute(giftRoute); }
    assert(posts===2,'G10 no automatic repost after lost response');
    assert(!new URL(page.url()).searchParams.has('gift'),'G11 gift=1 cleared so reload cannot reopen the form');
    await page.reload();
    await page.getByRole('dialog').filter({hasText:`Liệu trình #${treatment}`}).waitFor();
    assert(await modal.count()===0,'G11 reload after uncertain result does not reopen gift form');
    detail=(await get('/api/admin/packages/treatments/'+treatment)).treatment;
    const samePaid=detail.items.find(i=>i.id===paidItem.id);
    assert(detail.items.filter(i=>i.source_type==='gift').length===2,'G04 both gifts kept');
    assert(samePaid.total_sessions===paidItem.total_sessions&&samePaid.source_type!=='gift','G03 paid item not increased by same-service gift');
    checks.push('G03/G04/G10/G11 same-service gift is separate, lost response not reposted, reload safe');
    // G08 permissions: server rejects letan and customer even without UI.
    const giftBody={makh:detail.makh,madv:gift.madv,quantity:1,gift_note:'permission probe'};
    await login('letan');
    const letan=await call(`/api/admin/packages/treatments/${treatment}/gifts`,'POST',giftBody);
    await page.goto(base+'/admin/package-sales');
    await page.getByRole('heading',{name:'Bán gói tại quầy'}).waitFor();
    assert(await page.getByRole('button',{name:'Tặng thêm dịch vụ',exact:true}).count()===0,'Reception sees no gift button');
    await login('customer');
    const customerProbe=await call(`/api/admin/packages/treatments/${treatment}/gifts`,'POST',giftBody);
    assert([401,403].includes(letan.status)&&[401,403].includes(customerProbe.status),`G08 server rejects letan(${letan.status})/customer(${customerProbe.status})`);
    // Staff entry point creates a real gift in the fixture.
    await login('staff');
    await page.setViewportSize({width:390,height:900});
    await page.goto(base+'/employee/account');
    await page.getByRole('link',{name:'Liệu trình / tặng dịch vụ',exact:true}).click();
    const card=page.locator('.mobile-cards .ant-card').filter({hasText:`#${treatment} ·`});
    await card.getByRole('button',{name:'Tặng thêm dịch vụ',exact:true}).click();
    await modal.waitFor();
    await modal.getByRole('button',{name:'Hủy',exact:true}).click();
    await modal.waitFor({state:'hidden'});
    assert(posts===4,'Staff cancel does not gift (2 UI gifts + 2 rejected permission probes)');
    await page.getByRole('button',{name:'Tặng dịch vụ',exact:true}).click();
    await pickByMouse(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 04','Dịch vụ 04 massage trong tên');
    await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click();
    await modal.waitFor({state:'hidden'});
    await page.screenshot({path:`${out}/gift-staff-mobile.png`,fullPage:true});
    detail=(await get('/api/admin/packages/treatments/'+treatment)).treatment;
    const staffGift=detail.items.find(i=>i.source_type==='gift'&&i.tendv.startsWith('Dịch vụ 04'));
    assert(posts===5&&staffGift&&staffGift.total_sessions===1,'Staff created one gift');
    checks.push('G08 staff gifts via account entry; letan/customer rejected by API and UI');
    // G12/G13 customer sees and books the exact gift item.
    await login('customer');
    await page.goto(base+'/profile#treatments');
    const giftHref=`/appointments/create?treatment=${treatment}&service=${gift.madv}&item=${gift.id}`;
    await page.locator(`a[href="${giftHref}"]`).waitFor();
    await page.screenshot({path:`${out}/gift-customer-mobile.png`,fullPage:true});
    await page.locator(`a[href="${giftHref}"]`).click();
    await page.getByTestId('booking-next').click();
    const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh'}).format(new Date(Date.now()+3*864e5));
    await page.getByTestId('booking-date').fill(day);
    await page.locator('[data-slot]:not([disabled])').first().click();
    await page.getByTestId('booking-next').click();
    await page.getByText('Toàn bộ dịch vụ dùng lượt gói / quà tặng. Không cần thanh toán thêm.').waitFor();
    await page.getByTestId('booking-submit').click();
    await page.getByTestId('booking-success').waitFor();
    await page.screenshot({path:`${out}/gift-customer-booked.png`,fullPage:true});
    const after=(await get('/api/packages/my-treatments/'+treatment)).treatment;
    assert(after.items.find(i=>i.id===gift.id).reserved===1,'G13 booked exact gift item');
    assert(after.items.filter(i=>i.source_type!=='gift').every(i=>i.reserved===0),'G13 paid package sessions untouched');
    checks.push('G12/G13 customer sees gift and books one free session from the exact item');
    assert(!errors.length,errors.join('\n'));
    return {checks,posts,purchaseId,treatment,giftItem:gift.id,letan:letan.status,customer:customerProbe.status,errors};
  } finally {
    page.off('pageerror',onError);page.off('request',onRequest);
  }
}
