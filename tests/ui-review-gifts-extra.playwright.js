async (page, ctx) => {
  // Gift matrix G06, G07, G14-G18. Isolated fixture only:
  // python tests/master_ui_preview.py --port 5091 --all-ui --payments  (fake bank details; bank confirmation via /__qa/state).
  const base='http://127.0.0.1:5091', out=ctx?.out||'output/ui-review-2026-10-22', checks=[], notes=[], errors=[];
  const assert=(value,message)=>{if(!value)throw Error(message);};
  const onError=e=>errors.push(e.message);
  page.on('pageerror',onError);
  const bodies=[];
  const onRequest=r=>{if(/\/api\/admin\/packages\/treatments\/\d+\/gifts$/.test(r.url())&&r.method()==='POST')bodies.push(r.postDataJSON());};
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
  const qa=body=>page.evaluate(async body=>(await fetch('/__qa/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json(),body);
  const vnDay=offset=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh'}).format(new Date(Date.now()+offset*864e5));
  const treatmentOf=async mathe=>(await get('/api/admin/packages/treatments/'+mathe)).treatment;
  const popup=async box=>{const id=await box.getAttribute('aria-controls');return page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').filter({has:page.locator(`[id="${id}"]`)});};
  const pick=async(box,term,label)=>{await box.click();await box.fill(term);const option=(await popup(box)).locator('.ant-select-item-option').filter({hasText:label});await option.waitFor();await option.click();};
  // Admin session: cash sale of package 02 for a customer, paid -> new treatment id.
  const newTreatment=async phone=>{
    const makh=(await get('/api/admin/package-sales/customers?search='+phone)).customers[0].makh;
    const sale=await call('/api/admin/package-sales','POST',{makh,magoi:2,payment_method:'cash'});
    assert(sale.status===201,'create sale '+sale.status);
    const paid=await call(`/api/admin/packages/purchases/${sale.data.purchase.id}/confirm-payment`,'POST',{cash_received:sale.data.purchase.payable_amount});
    assert(paid.status===200&&paid.data.mathe,'confirm sale '+paid.status);
    return {makh,mathe:paid.data.mathe,purchaseId:sale.data.purchase.id};
  };
  const gift=(mathe,body)=>call(`/api/admin/packages/treatments/${mathe}/gifts`,'POST',body);
  // Customer session: book one session of an exact treatment item on the first free fixture slot (shift is today+3).
  const book=async(mathe,item)=>{
    const date=vnDay(3);
    const slots=(await get(`/api/appointments/available-slots?date=${date}&madv_list=${item.madv}`)).slots||[];
    const slot=slots.find(s=>s.available);assert(slot,'free slot on '+date);
    const ngaygio=`${date}T${slot.time}`;
    const staff=(await call('/api/appointments/available-staff','POST',{ngaygio,madv_list:[item.madv]})).data.staff.find(s=>s.available);
    return call('/api/appointments/create','POST',{madv_list:[item.madv],ngaygio,manv:staff?.manv,ghichu:'QA gift ledger',payment_option:'at_spa',
      package_usages:[{mathe,the_item_id:item.id,madv:item.madv,quantity:1}]});
  };
  const myItem=async(mathe,id)=>(await get('/api/packages/my-treatments/'+mathe)).treatment.items.find(i=>i.id===id);
  const modal=page.getByRole('dialog',{name:'Tặng dịch vụ',exact:true});
  const openGift=async mathe=>{await page.goto(base+`/admin/packages?tab=treatments&mathe=${mathe}&gift=1`);await modal.waitFor();};
  const submitGift=async()=>{const sent=page.waitForResponse(r=>/\/gifts$/.test(r.url())&&r.request().method()==='POST');
    await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click();return sent;};
  try {
    await login('admin');
    await page.setViewportSize({width:1440,height:900});
    const A=await newTreatment('0900000002');
    // G06: only the field of the selected validity mode is sent; Vietnam calendar date is kept.
    await openGift(A.mathe);
    await pick(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 05','Dịch vụ 05 massage trong tên');
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Số ngày'}).click();
    await modal.getByRole('spinbutton',{name:'Số ngày'}).fill('15');
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Vô thời hạn'}).click();
    await submitGift();await modal.waitFor({state:'hidden'});
    let b=bodies.at(-1);
    assert(!('validity_days' in b)&&!('expires_at' in b),'G06 unlimited sends no expiry field '+JSON.stringify(b));
    await openGift(A.mathe);
    await pick(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 06','Dịch vụ 06 massage trong tên');
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Đến ngày'}).click();
    await modal.getByLabel('Ngày hết hạn').fill(vnDay(1));
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Số ngày'}).click();
    await modal.getByRole('spinbutton',{name:'Số ngày'}).fill('15');
    await submitGift();await modal.waitFor({state:'hidden'});
    b=bodies.at(-1);
    assert(b.validity_days===15&&!('expires_at' in b),'G06 days mode sends only validity_days '+JSON.stringify(b));
    await openGift(A.mathe);
    await pick(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 07','Dịch vụ 07 massage trong tên');
    await modal.locator('label.ant-radio-button-wrapper').filter({hasText:'Đến ngày'}).click();
    const dateInput=modal.getByLabel('Ngày hết hạn');
    assert(await dateInput.getAttribute('min')===vnDay(0),'G06 date picker min is VN today');
    const before=bodies.length;
    await dateInput.fill(vnDay(-1));
    await modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click();
    await page.waitForTimeout(500);
    const pastBlocked=bodies.length===before;
    if(!pastBlocked){await modal.getByRole('alert').filter({hasText:'Ngày hết hạn phải từ hôm nay trở đi'}).waitFor();bodies.length=before;}
    notes.push(`G06 past date: ${pastBlocked?'blocked by browser min before POST':'server rejected with readable alert'}`);
    await dateInput.fill(vnDay(10));
    await submitGift();await modal.waitFor({state:'hidden'});
    b=bodies.at(-1);
    assert(b.expires_at===vnDay(10)&&!('validity_days' in b),'G06 date mode sends only expires_at '+JSON.stringify(b));
    let detail=await treatmentOf(A.mathe);
    const byName=n=>detail.items.find(i=>i.source_type==='gift'&&i.tendv.startsWith(n));
    assert(byName('Dịch vụ 05').effective_expires_at===null,'G06 unlimited stored without expiry');
    assert(byName('Dịch vụ 06').effective_expires_at.slice(0,10)===vnDay(15),'G06 15 days -> '+byName('Dịch vụ 06').effective_expires_at);
    assert(byName('Dịch vụ 07').effective_expires_at.slice(0,10)===vnDay(10),'G06 date kept as VN calendar day -> '+byName('Dịch vụ 07').effective_expires_at);
    checks.push('G06 unlimited/days/date send one field only; switching modes drops stale values; past date not stored');
    // G07 rejections (API + UI message).
    const svc8=(await treatmentOf(A.mathe));
    const wrongCustomer=await gift(A.mathe,{makh:A.makh+100000,madv:svc8.items[0].madv,quantity:1});
    assert(wrongCustomer.status===400&&/không khớp/.test(wrongCustomer.data.message),'G07 wrong makh rejected '+JSON.stringify(wrongCustomer));
    for(const q of [0,-1,1.5,'abc']){const r=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:q});assert(r.status===400,'G05 quantity '+q+' -> '+r.status);}
    const longNote=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:1,gift_note:'x'.repeat(2001)});
    assert(longNote.status===400,'G05 note >2000 rejected');
    const both=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:1,validity_days:3,expires_at:vnDay(5)});
    assert(both.status===400,'G06 both expiry fields rejected by API');
    // Inactive service while the form is open -> readable server message, nothing stored.
    const svc09=(await get('/api/admin/packages/treatments/'+A.mathe)).services.find(s=>s.tendv.startsWith('Dịch vụ 09'));
    await openGift(A.mathe);
    await pick(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 09','Dịch vụ 09 massage trong tên');
    await qa({service:svc09.madv,active:false});
    try {
      await submitGift();
      await modal.getByRole('alert').filter({hasText:'Dịch vụ không tồn tại hoặc đã ngừng hoạt động'}).waitFor();
      await page.screenshot({path:`${out}/g07-inactive-service-alert.png`});
      await modal.getByRole('button',{name:'Hủy',exact:true}).click();
    } finally { await qa({service:svc09.madv,active:true}); }
    detail=await treatmentOf(A.mathe);
    assert(!detail.items.some(i=>i.tendv.startsWith('Dịch vụ 09')),'G07 inactive service not stored');
    // Locked customer: same rule as creating a sale.
    await qa({customer:A.makh,trangthai:'blocked'});
    let locked;
    try { locked=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:1,gift_note:'locked probe'}); }
    finally { await qa({customer:A.makh,trangthai:'active'}); }
    assert(locked.status===400&&/ngừng hoạt động/.test(locked.data.message),'G07 locked customer rejected '+JSON.stringify(locked));
    // Cancelled treatment: no button in UI, API rejects.
    const C=await newTreatment('0900000002');
    await qa({treatment:C.mathe,status:'cancelled'});
    await page.goto(base+`/admin/packages?tab=treatments&mathe=${C.mathe}&gift=1`);
    await page.getByRole('dialog').filter({hasText:`Liệu trình #${C.mathe}`}).getByText('Dịch vụ trong gói').waitFor();
    assert(await modal.count()===0&&await page.getByRole('button',{name:'Tặng dịch vụ',exact:true}).count()===0,'G07 cancelled treatment shows no gift form/button');
    const cancelled=await gift(C.mathe,{makh:C.makh,madv:svc8.items[0].madv,quantity:1});
    assert(cancelled.status===400&&/hủy/.test(cancelled.data.message),'G07 cancelled treatment rejected '+JSON.stringify(cancelled));
    checks.push('G07 wrong/locked customer, inactive service (UI alert), cancelled treatment rejected; G05 API bounds');
    // G14 ledger: one-session gift -> book -> cancel (released) -> book -> complete (consumed) -> used up.
    const g14=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:1,gift_note:'G14 ledger'});
    assert(g14.status===201,'G14 gift created');
    const giftItem=g14.data.treatment.items.find(i=>i.id===g14.data.item_id);
    await login('customer');
    let booked=await book(A.mathe,giftItem);
    assert(booked.status===201||booked.status===200,'G14 first booking '+JSON.stringify(booked.data).slice(0,200));
    const malh1=booked.data.appointment.malh;
    let mine=await myItem(A.mathe,giftItem.id);
    assert(mine.reserved===1&&mine.available_sessions===0,'G14 booking reserves the single gift session');
    const extra=await book(A.mathe,giftItem);
    assert(extra.status>=400,'G14 cannot book beyond available gift sessions -> '+extra.status);
    const cancel=await call(`/api/appointments/${malh1}/cancel`,'POST',{reason:'QA đổi lịch'});
    assert(cancel.status===200,'G14 customer cancel '+cancel.status+' '+JSON.stringify(cancel.data));
    mine=await myItem(A.mathe,giftItem.id);
    assert(mine.reserved===0&&mine.available_sessions===1&&mine.consumed===0,'G14 cancel releases the gift session');
    booked=await book(A.mathe,giftItem);
    const malh2=booked.data.appointment.malh;
    await login('admin');
    const done=await call(`/api/admin/appointments/${malh2}/complete`,'POST',{});
    assert(done.status===200,'G14 complete '+done.status+' '+JSON.stringify(done.data));
    const again=await call(`/api/admin/appointments/${malh2}/complete`,'POST',{});
    detail=await treatmentOf(A.mathe);
    const usedUp=detail.items.find(i=>i.id===giftItem.id);
    assert(usedUp.consumed===1&&usedUp.reserved===0&&usedUp.available_sessions===0,'G14 completion consumes exactly once (repeat complete -> '+again.status+')');
    assert(detail.history.filter(h=>h.the_item_id===giftItem.id&&h.state==='consumed').length===1,'G14 one consumed ledger row');
    await login('customer');
    await page.setViewportSize({width:390,height:900});
    await page.goto(base+'/profile#treatments');
    const usedHref=`/appointments/create?treatment=${A.mathe}&service=${giftItem.madv}&item=${giftItem.id}`;
    await page.locator('a[href^="/appointments/create?treatment="]').first().waitFor();
    assert(await page.locator(`a[href="${usedHref}"]`).count()===0,'G14 used-up gift has no booking link');
    // Expired gift: not bookable in UI or API.
    await login('admin');
    const g14e=await gift(A.mathe,{makh:A.makh,madv:svc8.items[0].madv,quantity:2,validity_days:30,gift_note:'G14 expiry'});
    const expItem=g14e.data.treatment.items.find(i=>i.id===g14e.data.item_id);
    await qa({item:expItem.id});
    await login('customer');
    mine=await myItem(A.mathe,expItem.id);
    assert(mine.usable===false,'G14 expired gift marked unusable');
    const expBook=await book(A.mathe,expItem);
    assert(expBook.status>=400,'G14 expired gift booking rejected -> '+expBook.status);
    await page.goto(base+'/profile#treatments');
    await page.locator('a[href^="/appointments/create?treatment="]').first().waitFor();
    assert(await page.locator(`a[href*="item=${expItem.id}"]`).count()===0,'G14 expired gift has no booking link');
    checks.push('G14 reserve/cancel releases, complete consumes once, used-up and expired gifts not bookable (UI+API)');
    // G15: package expired, gift with its own later expiry still usable; package sessions are not.
    await login('admin');
    const B=await newTreatment('0900000002');
    const g15=await gift(B.mathe,{makh:B.makh,madv:svc8.items[0].madv,quantity:1,validity_days:30,gift_note:'G15'});
    await qa({treatment:B.mathe,status:'expired',expired:true});
    await login('customer');
    const tB=(await get('/api/packages/my-treatments/'+B.mathe)).treatment;
    const g15Item=tB.items.find(i=>i.id===g15.data.item_id), paidB=tB.items.find(i=>i.source_type!=='gift');
    assert(g15Item.usable===true&&paidB.usable===false,`G15 gift usable=${g15Item.usable}, package item usable=${paidB.usable}`);
    await page.goto(base+'/profile#treatments');
    await page.locator(`a[href*="item=${g15Item.id}"]`).waitFor();
    assert(await page.locator(`a[href*="item=${paidB.id}"]`).count()===0,'G15 expired package item has no booking link');
    const g15Book=await book(B.mathe,g15Item);
    assert(g15Book.status<300,'G15 gift booking still allowed '+g15Book.status);
    await page.screenshot({path:`${out}/g15-customer-expired-package-gift-ok.png`,fullPage:true});
    checks.push('G15 gift keeps its own expiry after package expiry; package sessions blocked');
    // G16: two tabs submit independently -> two gifts (UI guard is per form, not backend idempotency).
    await login('admin');
    await page.setViewportSize({width:1440,height:900});
    const tab2=await page.context().newPage();
    try {
      await openGift(A.mathe);
      await tab2.goto(base+`/admin/packages?tab=treatments&mathe=${A.mathe}&gift=1`);
      const modal2=tab2.getByRole('dialog',{name:'Tặng dịch vụ',exact:true});await modal2.waitFor();
      const before16=(await treatmentOf(A.mathe)).items.filter(i=>i.source_type==='gift').length;
      await pick(modal.getByRole('combobox',{name:'Dịch vụ tặng',exact:true}),'Dịch vụ 10','Dịch vụ 10 massage trong tên');
      const box2=modal2.getByRole('combobox',{name:'Dịch vụ tặng',exact:true});await box2.click();await box2.fill('Dịch vụ 10');
      const id2=await box2.getAttribute('aria-controls');
      await tab2.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').filter({has:tab2.locator(`[id="${id2}"]`)}).locator('.ant-select-item-option').filter({hasText:'Dịch vụ 10 massage trong tên'}).click();
      await Promise.all([modal.getByRole('button',{name:'Xác nhận tặng',exact:true}).click(),modal2.getByRole('button',{name:'Xác nhận tặng',exact:true}).click()]);
      await modal.waitFor({state:'hidden'});await modal2.waitFor({state:'hidden'});
      const after16=(await treatmentOf(A.mathe)).items.filter(i=>i.source_type==='gift').length;
      notes.push(`G16 two tabs, same gift submitted once each -> ${after16-before16} gift rows (no backend idempotency key)`);
    } finally { await tab2.close(); }
    // G17: VietQR sale confirmed by mocked bank -> gift button with same paid rule.
    await page.route('**/img.vietqr.io/**',r=>r.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')}));
    try {
      await page.goto(base+'/admin/package-sales');
      await pick(page.getByRole('combobox',{name:'Khách hàng',exact:true}),'0900000002','Khách hàng Test');
      await pick(page.getByRole('combobox',{name:'Gói dịch vụ',exact:true}),'Gói kiểm thử 03','Gói kiểm thử 03');
      await page.locator('label.ant-radio-button-wrapper').filter({hasText:'VietQR'}).click();
      const created=page.waitForResponse(r=>r.url().endsWith('/api/admin/package-sales')&&r.request().method()==='POST');
      await page.getByTestId('sale-create').click();
      const qrId=(await(await created).json()).purchase.id;
      await page.getByAltText('Mã VietQR thanh toán gói').waitFor();
      assert(await page.locator('.ant-modal').getByRole('button',{name:'Tặng thêm dịch vụ'}).count()===0,'G17 no gift while VietQR pending');
      await qa({vietqr_paid:qrId});
      await page.getByTestId('package-paid').waitFor({timeout:15000});
      await page.getByTestId('package-paid').getByRole('button',{name:'Tặng thêm dịch vụ'}).waitFor();
      await page.screenshot({path:`${out}/g17-vietqr-paid-gift.png`});
      const qrPaid=(await get(`/api/admin/package-sales/${qrId}`)).purchase;
      assert(qrPaid.status==='paid'&&qrPaid.payment_method==='vietqr'&&qrPaid.mathe,'G17 VietQR purchase activated');
      checks.push('G17 VietQR pending has no gift button; after mocked bank confirmation the paid dialog offers it');
    } finally { await page.unroute('**/img.vietqr.io/**'); }
    // G18: Escape, switching treatments, back/forward on mobile never shows the previous customer.
    await page.setViewportSize({width:390,height:844});
    const D=await newTreatment('0900000099');
    await openGift(A.mathe);
    assert((await modal.textContent()).includes(`(#${A.mathe})`),'G18 form for A');
    await page.keyboard.press('Escape'); // during the modal opening animation
    await page.waitForTimeout(400);
    assert(new URL(page.url()).searchParams.get('mathe')===String(A.mathe),'G18 early Escape never closes the treatment drawer');
    if(await modal.isVisible()){
      await page.waitForFunction(()=>document.querySelector('.ant-modal-wrap')?.contains(document.activeElement));
      await page.keyboard.press('Escape');
    }
    await modal.waitFor({state:'hidden'});
    assert(!new URL(page.url()).searchParams.has('gift'),'G18 Escape clears gift=1');
    const drawerA=page.getByRole('dialog').filter({hasText:`Liệu trình #${A.mathe}`});await drawerA.waitFor();
    assert(await page.evaluate(()=>document.activeElement.classList.contains('ant-drawer')),'G18 focus returns to the drawer after the form closes');
    await page.goto(base+`/admin/packages?tab=treatments&mathe=${D.mathe}&gift=1`);
    await modal.waitFor();
    const textD=await modal.textContent();
    assert(textD.includes('Khách lịch hôm nay')&&textD.includes(`(#${D.mathe})`)&&!textD.includes(`(#${A.mathe})`),'G18 switched treatment shows D customer only: '+textD.slice(0,120));
    await modal.getByRole('button',{name:'Hủy',exact:true}).click();
    await page.goBack();
    await page.getByRole('dialog').filter({hasText:`Liệu trình #${A.mathe}`}).waitFor();
    assert(await modal.count()===0,'G18 back does not reopen a gift form');
    assert(!(await page.getByRole('dialog').filter({hasText:`Liệu trình #${A.mathe}`}).textContent()).includes('Khách lịch hôm nay'),'G18 back shows A data, not D');
    await page.screenshot({path:`${out}/g18-back-mobile.png`});
    await page.keyboard.press('Escape');
    await page.getByRole('dialog').first().waitFor({state:'hidden'});
    assert(!new URL(page.url()).searchParams.has('mathe'),'G18 Escape without the form closes the drawer');
    checks.push('G18 Escape closes one layer (early Escape safe, focus returns to drawer); switch/back at 390px keep the right customer');
    assert(!errors.length,errors.join('\n'));
    return {checks,notes,treatments:{A:A.mathe,B:B.mathe,C:C.mathe,D:D.mathe},errors};
  } finally {
    page.off('pageerror',onError);page.off('request',onRequest);
  }
}
