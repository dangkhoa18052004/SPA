async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/admin')).json();localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role',d.role);localStorage.setItem('admin_user',JSON.stringify({hoten:'Admin Test',role:'admin'}));});
  const items=await page.evaluate(async()=>{const r=await fetch('/api/admin/loyalty/redemptions',{headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}});return (await r.json()).items;});
  const gift=items.find(r=>r.reward.reward_type==='physical_gift'&&r.status==='available'),voucher=items.find(r=>r.reward.reward_type==='voucher_percent');assert(!!gift&&!!voucher,'Fixture gift and voucher');
  let posts=0;page.on('request',r=>{if(r.url().endsWith('/fulfill')&&r.method()==='POST')posts++;});
  for(const legacy of [false,true])for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/admin/loyalty?tab=redemptions'+(legacy?'&ui=legacy':''));
    const giftCard=page.locator(legacy?`[data-redemption="${gift.id}"]`:`[data-testid="redemption-${gift.id}"]`);await giftCard.waitFor();
    const voucherCard=page.locator(legacy?`[data-redemption="${voucher.id}"]`:`[data-testid="redemption-${voucher.id}"]`);
    assert((await voucherCard.textContent()).includes('Voucher dùng khi thanh toán'),'Voucher guidance');assert(await voucherCard.getByRole('button',{name:'Trao quà',exact:true}).count()===0,'No voucher fulfillment');
    await giftCard.getByRole('button',{name:'Trao quà',exact:true}).click();
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-gift-confirm-${legacy?'legacy':'new'}-${width}.png`});
    if(legacy)await page.locator('#giftHandover [data-close]').click();else await page.getByRole('button',{name:'Chưa giao',exact:true}).click();
    assert(posts===0,'Confirmation cancel is read-only');assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Gift desk overflow');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-gift-desk-${legacy?'legacy':'new'}-${width}.png`,fullPage:true});checks.push({legacy,width});
  }
  await page.goto(base+'/admin/loyalty?tab=redemptions');await page.getByTestId('redemption-'+gift.id).getByRole('button',{name:'Trao quà',exact:true}).click();
  await page.getByRole('button',{name:'Đã trao quà cho khách',exact:true}).evaluate(b=>{b.click();b.click();});
  await page.getByTestId('redemption-'+gift.id).getByText(/Đã trao lúc/).waitFor();assert(posts===1,'Single fulfillment POST');
  assert(await page.getByTestId('redemption-'+gift.id).getByRole('button',{name:'Trao quà',exact:true}).count()===0,'Fulfilled cannot repeat');
  const result=await page.evaluate(async id=>(await(await fetch(`/api/admin/loyalty/redemptions/${id}/fulfill`,{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('admin_token'),'Content-Type':'application/json'},body:'{}'})).json()),gift.id);
  assert(result.already_fulfilled===true,'Backend idempotent handover');
  assert(!errors.length,errors.join());return {checks,confirmationPosts:1,repeatIdempotent:true,errors};
}
