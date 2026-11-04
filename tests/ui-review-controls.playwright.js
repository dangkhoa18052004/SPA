async (page, ctx) => {
  // Isolated fixture only (tests/master_ui_preview.py --port 5091 --all-ui). Totals are read from the API,
  // so the script also works after ui-review-gifts.playwright.js created extra sales.
  const base='http://127.0.0.1:5091', out=ctx?.out||'output/ui-review-2026-10-21', checks=[], errors=[], notes={};
  const assert=(v,m)=>{if(!v)throw Error(m);};
  const onError=e=>errors.push(e.message);
  page.on('pageerror',onError);
  notes.alerts=[];
  const onDialog=d=>{notes.alerts.push(page.url().replace(base,'')+' :: '+d.message());d.accept();};
  page.on('dialog',onDialog);
  let giftPosts=0;
  const onRequest=r=>{if(/\/api\/admin\/packages\/treatments\/\d+\/gifts$/.test(r.url())&&r.method()==='POST')giftPosts++;};
  page.on('request',onRequest);
  const login=async role=>{await page.goto(base+'/__qa/ping');await page.evaluate(async role=>{
    localStorage.clear();const d=await(await fetch('/__qa/login/'+role)).json();
    if(d.access_token){localStorage.setItem(role==='customer'?'access_token':'admin_token',d.access_token);if(role!=='customer')localStorage.setItem('admin_role',d.role);}
  },role);};
  const get=path=>page.evaluate(async path=>(await(await fetch(path,{headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}})).json()),path);
  try{
    // P1-03 registration password toggles: mouse, keyboard, accessible name and pressed state.
    await login('guest');await page.setViewportSize({width:390,height:900});
    await page.goto(base+'/auth/register');
    const show=page.getByRole('button',{name:'Hiện mật khẩu',exact:true});
    assert(await show.getAttribute('aria-controls')==='matkhau'&&await show.getAttribute('aria-pressed')==='false','Password toggle wired to input');
    await show.click();
    assert(await page.locator('#matkhau').getAttribute('type')==='text','Password visible');
    const hide=page.getByRole('button',{name:'Ẩn mật khẩu',exact:true});
    assert(await hide.getAttribute('aria-pressed')==='true','Pressed state follows visibility');
    await hide.focus();await page.keyboard.press('Enter');
    assert(await page.locator('#matkhau').getAttribute('type')==='password','Enter hides password');
    const showConfirm=page.getByRole('button',{name:'Hiện mật khẩu xác nhận',exact:true});
    await showConfirm.focus();await page.keyboard.press('Space');
    assert(await page.locator('#confirm_password').getAttribute('type')==='text','Space shows confirmation');
    await page.getByRole('button',{name:'Ẩn mật khẩu xác nhận',exact:true}).click();
    assert(await page.locator('#confirm_password').getAttribute('type')==='password','Confirmation hidden');
    checks.push('P1-03 register password toggles: mouse, Enter, Space, aria-pressed, aria-label');
    // P1-04 policy links: evidence only, content must come from the spa owner.
    notes.policyLinks=await page.evaluate(async()=>Promise.all(['/terms','/privacy'].map(async path=>({path,status:(await fetch(path)).status}))));

    // P1-01 pagination with more than 30 receipts.
    await login('admin');
    const seeded=await page.evaluate(async()=>{
      const headers={Authorization:'Bearer '+localStorage.getItem('admin_token'),'Content-Type':'application/json'};
      const list=async()=>(await(await fetch('/api/admin/package-sales',{headers})).json()).purchases;
      let purchases=await list();
      const paid=purchases.find(p=>p.status==='paid'&&p.mathe);
      for(let n=purchases.length;n<34;n++){
        const r=await fetch('/api/admin/package-sales',{method:'POST',headers,body:JSON.stringify({makh:paid.makh,magoi:paid.magoi,payment_method:'cash'})});
        if(!r.ok)throw Error('Fixture purchase creation '+r.status);
      }
      purchases=await list();
      return {total:purchases.length,paid,purchases:purchases.map(p=>({id:p.id,status:p.status,mathe:p.mathe}))};
    });
    const pages=Math.ceil(seeded.total/10), lastCount=seeded.total%10||10;
    await page.goto(base+'/admin/package-sales');
    await page.locator('.mobile-cards .small-card').first().waitFor();
    assert(await page.locator('.mobile-cards .small-card').count()===10,'Ten mobile receipts per page');
    await page.locator(`.ant-pagination-item-${pages}`).click();
    assert(await page.locator('.mobile-cards .small-card').count()===lastCount,`Mobile last page has ${lastCount}`);
    await page.screenshot({path:`${out}/sales-mobile-last-page.png`,fullPage:true});
    await page.setViewportSize({width:1440,height:900});
    assert(await page.locator('.desktop-table tbody tr[data-row-key]').count()===lastCount,'Desktop keeps the same page after resize');
    await page.locator('input[aria-label="Tìm phiếu"]').fill('Khách hàng Test');
    await page.keyboard.press('Enter');
    await page.waitForFunction(()=>location.search.includes('q='));
    await page.locator('.desktop-table tbody tr[data-row-key]').first().waitFor();
    assert(await page.locator('.ant-pagination-item-active').first().textContent()==='1','Filter resets to page 1, no blank page');
    checks.push(`P1-01 ${seeded.total} receipts: ${pages} pages, last page ${lastCount}, resize keeps page, filter resets`);
    notes.apiHistoryLimit='GET /api/admin/package-sales returns at most 200 rows (limit(200)); older receipts are reachable only by search.';

    // P0-01 legacy package sales: gift link per paid row, receipt resilience, print.
    await page.goto(base+'/admin/package-sales?ui=legacy');
    await page.locator('#saleHistory tr [data-receipt]').first().waitFor();
    const legacyRows=await page.evaluate(()=>[...document.querySelectorAll('#saleHistory tr')].map(tr=>({receipt:tr.querySelector('[data-receipt]')?.dataset.receipt,gift:tr.querySelector('[data-gift-link]')?.dataset.giftLink,href:tr.querySelector('[data-gift-link]')?.getAttribute('href'),text:tr.querySelector('[data-gift-link]')?.textContent})));
    for(const row of legacyRows.filter(r=>r.receipt)){
      const p=seeded.purchases.find(x=>String(x.id)===row.receipt);
      if(!p)continue;
      if(p.status==='paid'&&p.mathe)assert(row.gift===String(p.mathe)&&row.text==='Tặng thêm dịch vụ'&&row.href.endsWith('&ui=legacy'),`Paid receipt ${p.id} links to treatment ${p.mathe}`);
      else assert(!row.gift,`Receipt ${p.id} (${p.status}) has no gift link`);
    }
    const paidId=seeded.paid.id;
    const secondary=`**/api/admin/package-sales/${paidId}`;
    await page.route(secondary,route=>route.fulfill({status:500,json:{message:'Simulated secondary failure'}}));
    try{
      await page.locator(`[data-receipt="${paidId}"]`).click();
      await page.locator('#saleReceiptDialog[open]').waitFor();
      await page.waitForTimeout(300);
      assert(await page.locator('#saleReceipt').textContent().then(t=>t.trim().length>0),'Receipt shown although secondary request failed');
      assert(await page.locator('#saleReceipt [data-gift-link]').count()===0,'No gift link when secondary request failed');
    }finally{await page.unroute(secondary);}
    await page.locator('#closeSaleReceipt').click();
    await page.locator(`[data-receipt="${paidId}"]`).click();
    await page.locator('#saleReceipt [data-gift-link]').waitFor();
    await page.screenshot({path:`${out}/legacy-receipt-gift-1440.png`});
    await page.emulateMedia({media:'print'});
    assert(!await page.locator('#saleReceipt [data-gift-link]').isVisible(),'Gift link hidden when printing');
    await page.emulateMedia({media:'screen'});
    await page.locator('#closeSaleReceipt').click();
    checks.push('P0-01 legacy: paid rows link to exact treatment, others none; receipt survives secondary failure; link hidden in print');
    await page.setViewportSize({width:390,height:900});
    await page.screenshot({path:`${out}/legacy-sales-history-390.png`,fullPage:true});
    // Legacy gift form: opens from the row, keeps ui=legacy, clears gift=1, survives a lost response.
    await page.locator(`#saleHistory [data-gift-link="${seeded.paid.mathe}"]`).first().click();
    await page.locator('#giftServiceDialog[open]').waitFor();
    assert(new URL(page.url()).searchParams.get('ui')==='legacy'&&!new URL(page.url()).searchParams.has('gift'),'Legacy link stays legacy and clears gift=1');
    await page.setViewportSize({width:360,height:900});await page.waitForTimeout(300);
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),'Legacy gift dialog fits 360');
    await page.screenshot({path:`${out}/legacy-gift-form-360.png`});
    await page.locator('#giftServiceDialog [data-cancel]').click();
    assert(giftPosts===0,'Cancel does not gift');
    const before=(await get(`/api/admin/packages/treatments/${seeded.paid.mathe}`)).treatment.items.filter(i=>i.source_type==='gift').length;
    await page.locator('#giftServiceButton').click();
    await page.locator('#giftServiceDialog select[name="madv"]').selectOption({index:4});
    const giftRoute='**/api/admin/packages/treatments/*/gifts';
    await page.route(giftRoute,async route=>{await route.fetch();await route.fulfill({status:502,json:{message:'Simulated lost response'}});});
    try{
      await page.locator('#giftServiceDialog [type="submit"]').click();
      await page.locator('#giftServiceDialog button',{hasText:'Kiểm tra liệu trình'}).waitFor();
      await page.locator('#giftServiceDialog form').evaluate(f=>f.requestSubmit?.());
      await page.locator('#giftServiceDialog button',{hasText:'Kiểm tra liệu trình'}).click();
      await page.locator('#giftServiceDialog').waitFor({state:'hidden'});
    }finally{await page.unroute(giftRoute);}
    const afterGifts=(await get(`/api/admin/packages/treatments/${seeded.paid.mathe}`)).treatment.items.filter(i=>i.source_type==='gift').length;
    assert(giftPosts===1&&afterGifts===before+1,`Legacy lost response: one POST (${giftPosts}), one new gift (${before}->${afterGifts})`);
    await page.goto(base+'/admin/packages?tab=treatments&mathe=999999&gift=1&ui=legacy');
    await page.locator('#treatmentDetailContent',{hasText:'Không tìm thấy liệu trình'}).waitFor();
    assert(await page.locator('#giftServiceDialog[open]').count()===0,'Unknown treatment does not open gift form');
    await login('letan');
    // The legacy page itself answers letan with a blocking alert (observed manually); assert the server rule here.
    notes.letanTreatmentApi=await page.evaluate(async id=>(await fetch('/api/admin/packages/treatments/'+id,{headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}})).status,seeded.paid.mathe);
    assert(notes.letanTreatmentApi===403,'Reception cannot load treatment detail or gift form');
    checks.push('P0-01 legacy gift form: stays legacy, gift=1 cleared, 360px fits, cancel safe, lost response not reposted, unknown id and letan blocked');

    // P1-02 dashboard row opens the exact appointment; reload and close behave.
    await login('admin');await page.setViewportSize({width:1440,height:900});
    const today=(await get('/api/dashboard/appointments/today')).appointments;
    assert(today.length>=2,'Fixture has two appointments today');
    for(const visit of today.slice(0,2)){
      await page.goto(base+'/admin/dashboard');
      const row=page.locator('.desktop-table tbody tr').filter({hasText:visit.khachhang_hoten});
      await row.getByRole('link',{name:'Mở lịch hẹn'}).or(row.getByRole('button',{name:'Mở lịch hẹn'})).click();
      await page.waitForURL(u=>new URL(u).searchParams.get('view')===String(visit.malh));
      const dialog=page.getByRole('dialog').filter({hasText:`Chi tiết lịch hẹn #${visit.malh}`});
      await dialog.getByText(visit.khachhang_hoten).first().waitFor();
      await page.reload();
      await dialog.getByText(visit.khachhang_hoten).first().waitFor();
      await dialog.locator('.ant-drawer-close,.ant-modal-close').first().click();
      await page.waitForURL(u=>!new URL(u).searchParams.has('view'));
    }
    await page.screenshot({path:`${out}/dashboard-deeplink-after-close.png`});
    checks.push('P1-02 admin dashboard -> exact appointment for two customers; reload keeps it; close clears ?view');
    // P1-02 staff: dashboard -> own appointment in the employee portal; another employee's id shows nothing.
    await login('staff');await page.setViewportSize({width:390,height:900});
    const mine=(await get('/api/dashboard/appointments/my-schedule-today')).appointments;
    assert(mine.length>=1,'Fixture has a staff appointment today');
    const visit=mine[0];
    await page.goto(base+'/admin/dashboard');
    await page.locator('.mobile-cards .business-appointment').filter({hasText:visit.khachhang_hoten}).getByRole('link',{name:'Mở lịch hẹn'})
      .or(page.locator('.mobile-cards .business-appointment').filter({hasText:visit.khachhang_hoten}).getByRole('button',{name:'Mở lịch hẹn'})).click();
    await page.waitForURL(u=>new URL(u).pathname==='/employee/appointments'&&new URL(u).searchParams.get('view')===String(visit.malh));
    const staffDrawer=page.getByRole('dialog').filter({hasText:'Chi tiết lịch hẹn'});
    await staffDrawer.getByText(`#${visit.malh}`,{exact:true}).waitFor();
    assert((await staffDrawer.textContent()).includes(visit.khachhang_hoten),'Staff drawer shows the clicked customer');
    await page.reload();
    await staffDrawer.getByText(`#${visit.malh}`,{exact:true}).waitFor();
    await page.screenshot({path:'output/ui-review-2026-10-22/staff-deeplink-390.png'});
    await staffDrawer.locator('.ant-drawer-close').click();
    await page.waitForURL(u=>!new URL(u).searchParams.has('view'));
    await page.goBack();
    await staffDrawer.getByText(`#${visit.malh}`,{exact:true}).waitFor();
    await staffDrawer.locator('.ant-drawer-close').click();
    const foreign=today.find(v=>!mine.some(m=>m.malh===v.malh));
    assert(foreign,'Fixture has another employee appointment today');
    await page.goto(base+`/employee/appointments?view=${foreign.malh}`);
    await page.getByRole('alert').filter({hasText:`Không tìm thấy lịch hẹn #${foreign.malh} trong lịch của bạn.`}).waitFor();
    assert(await staffDrawer.count()===0&&!(await page.textContent('body')).includes(foreign.khachhang_hoten),'Other employee appointment not shown');
    await page.screenshot({path:'output/ui-review-2026-10-22/staff-deeplink-foreign-390.png'});
    checks.push('P1-02 staff dashboard -> own appointment (390px); reload keeps, close clears, back reopens; other employee id shows a notice only');
    assert(!errors.length,errors.join('\n'));
    return {checks,notes,errors};
  }finally{page.off('pageerror',onError);page.off('request',onRequest);page.off('dialog',onDialog);}
}
