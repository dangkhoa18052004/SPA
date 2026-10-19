// Run against the disposable preview on 5080. All reward/point data is mocked;
// the lost-response fixture models one server-side redemption per key.
async page => {
 const base='http://127.0.0.1:5080',results=[],errors=[],failed=[],typography=[];
 const assert=(condition,message)=>{if(!condition)throw new Error(message);};
 let available=1200,walletError=false,listError=false,loyaltyGets=0,redeemPosts=0,loseResponse=true;
 const keys=[],processed=new Map();let offers=[];
 const rewards=[
  {id:1,name:'Voucher chăm sóc da <an toàn>',description:'Giảm trực tiếp khi thanh toán',reward_type:'voucher_amount',points_cost:200,reward_value:50000,stock:5,validity_days:30,apply_to:'both',minimum_spend:200000},
  {id:2,name:'Khăn tắm Bin Spa',description:'Nhận quà tại quầy',reward_type:'physical_gift',points_cost:100,reward_value:0,stock:2,validity_days:null},
  {id:3,name:'Ưu đãi VIP',reward_type:'voucher_amount',points_cost:5000,reward_value:900000,stock:null},
  {id:4,name:'Quà đã hết',reward_type:'physical_gift',points_cost:300,reward_value:0,stock:0},
  {id:5,name:'Voucher giảm 15%',reward_type:'voucher_percent',points_cost:400,percentage_value:15,max_discount_amount:100000,stock:null,apply_to:'service_invoice',minimum_spend:500000},
 ];
 const offer=(id,status,reward,extra={})=>({id,status,reward,code:'BIN-TEST-'+id,points_spent:reward.points_cost,redeemed_at:'2026-10-19T03:00:00Z',expires_at:'2029-10-19T03:00:00Z',...extra});
 const reset=()=>{available=1200;walletError=false;listError=false;loyaltyGets=0;redeemPosts=0;loseResponse=true;keys.length=0;processed.clear();offers=[offer(11,'available',rewards[0]),offer(12,'available',rewards[1]),offer(13,'reserved',rewards[0],{target_type:'service_invoice',target_id:55}),offer(14,'used',rewards[0],{used_at:'2026-10-18'}),offer(15,'expired',rewards[0]),offer(16,'fulfilled',rewards[1],{fulfilled_at:'2026-10-18'}),offer(17,'cancelled',rewards[0]),offer(18,'reserved',rewards[0],{target_type:'package_purchase',target_id:401})];};
 page.on('pageerror',e=>errors.push(e.message));
 page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText});});
 await page.route('**/api/loyalty/**',async route=>{
  assert(new URL(route.request().url()).origin===base,'Rewards fixture must not access a live server');
  const url=new URL(route.request().url()),path=url.pathname;
  if(path.endsWith('/redeem')){
   redeemPosts++;const body=route.request().postDataJSON(),id=Number(path.split('/').at(-2));keys.push(body.idempotency_key);
   await new Promise(resolve=>setTimeout(resolve,200));
   if(!processed.has(body.idempotency_key)){const reward=rewards.find(r=>r.id===id);available-=reward.points_cost;const row=offer(9001,'available',reward);offers.unshift(row);processed.set(body.idempotency_key,row);}
   if(loseResponse){loseResponse=false;return route.fulfill({status:503,json:{message:'Fixture: response lost after redemption'}});}
   return route.fulfill({json:{redemption:processed.get(body.idempotency_key)}});
  }
  loyaltyGets++;await new Promise(resolve=>setTimeout(resolve,100));
  if(path==='/api/loyalty/me')return route.fulfill(walletError?{status:503,json:{message:'Wallet fixture unavailable'}}:{json:{wallet:{available_points:available,reserved_points:999999,lifetime_earned:4500,lifetime_redeemed:3300},tier:{tier:{name:'Hạng Bạc'},next_tier:{name:'Hạng Vàng'},qualifying_points:3600,points_to_next:1400,progress_percent:72}}});
  if(listError)return route.fulfill({status:503,json:{message:'Danh sách tạm thời không tải được'}});
  let rows=path.endsWith('/transactions')?[{id:1,points_delta:1000,description:'Điểm tích từ thanh toán',created_at:'2026-10-18'},{id:2,points_delta:-200,description:'Đổi voucher chăm sóc da',created_at:'2026-10-19'}]:path.endsWith('/my-rewards')?offers:rewards;
  const group=url.searchParams.get('status');
  if(path.endsWith('/my-rewards')&&group&&group!=='all')rows=rows.filter(o=>({usable:o.status==='available'&&o.reward.reward_type!=='physical_gift',pickup:o.status==='available'&&o.reward.reward_type==='physical_gift',applied:o.status==='reserved',done:['used','fulfilled'].includes(o.status),closed:['expired','cancelled'].includes(o.status)})[group]);
  const type=url.searchParams.get('reward_type'),search=url.searchParams.get('search');
  if(type)rows=rows.filter(r=>type==='voucher'?(r.reward||r).reward_type.startsWith('voucher'):(r.reward||r).reward_type===type);
  if(search)rows=rows.filter(r=>((r.reward||r).name+' '+(r.code||'')).toLowerCase().includes(search.toLowerCase()));
  if(url.searchParams.get('affordable_only'))rows=rows.filter(r=>r.points_cost<=available);
  const current=Number(url.searchParams.get('page')||1),total=rows.length,perPage=4;
  return route.fulfill({json:{items:rows.slice((current-1)*perPage,current*perPage),page:current,pages:Math.max(1,Math.ceil(total/perPage)),total,per_page:perPage}});
 });
 const measure=async(selector,mode,width,view)=>{
  const report=await page.locator(selector).evaluate(root=>{
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const rgb=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=c;ctx.fillRect(0,0,1,1);const d=ctx.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
   const mix=(a,b)=>a.slice(0,3).map((x,i)=>x*a[3]+b[i]*(1-a[3])).concat(1);
   const lum=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
   const issues=[];let minimum=21,checked=0;
   for(const e of root.querySelectorAll('*')){
    if(![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())||!e.getBoundingClientRect().width||e.closest('[hidden]'))continue;
    const s=getComputedStyle(e);if(s.visibility!=='visible')continue;
    const chain=[];for(let n=e;n;n=n.parentElement)chain.unshift(n);let bg=[255,255,255,1];for(const n of chain)bg=mix(rgb(getComputedStyle(n).backgroundColor),bg);
    const l=[lum(mix(rgb(s.color),bg)),lum(bg)].sort((a,b)=>b-a),ratio=(l[0]+.05)/(l[1]+.05);checked++;minimum=Math.min(minimum,ratio);
    if(ratio<4.5)issues.push({tag:e.tagName,color:s.color,ratio});
    if(/serif/i.test(s.fontFamily)&&!/sans-serif/i.test(s.fontFamily))issues.push({tag:e.tagName,font:s.fontFamily});
   }
   return {checked,minimum:+minimum.toFixed(2),issues,overflow:root.scrollWidth>root.clientWidth};
  });
  assert(!report.overflow&&report.issues.length===0,'Rewards typography '+JSON.stringify({mode,width,view,...report}));typography.push({mode,width,view,...report});
 };
 await page.request.get(base+'/__preview/session?customer=1');
 for(const mode of ['legacy','refactor']){
  reset();await page.goto(base+'/');
  await page.goto(base+'/profile'+(mode==='legacy'?'?ui=legacy':'')+'#info');
  await page.waitForFunction(()=>document.querySelector('#userName')?.textContent!=='Đang tải…');
  assert(loyaltyGets===0,'Rewards fetched while its section is hidden');
  await page.locator('.menu-link[data-section=loyalty]').click();
  await page.locator('#loyaltyBalance .loyalty-wallet-available').waitFor();
  assert(await page.locator('#loyaltyBalance .loyalty-card').count()===4,'Wallet/tier cards missing');
  const wallet=await page.locator('#loyaltyBalance').innerText();assert(wallet.includes('1.200')&&!wallet.includes('999999')&&!wallet.includes('Đang giữ'),'Wallet reveals held points or wrong balance');
  assert(await page.locator('#customerLoyaltyContent').getAttribute('aria-labelledby')==='loyaltyTab-history','Tab panel label missing');
  await page.locator('#loyaltyTab-history').focus();await page.keyboard.press('End');await page.locator('[data-offer="11"]').waitFor();
  await page.keyboard.press('Home');await page.locator('.loyalty-history').waitFor();
  await page.keyboard.press('ArrowRight');await page.locator('[data-redeem="1"]').waitFor();
  assert(await page.locator('[data-redeem="3"]').isDisabled(),'Insufficient points reward enabled');
  assert(await page.locator('[data-redeem="4"]').isDisabled(),'Out of stock reward enabled');
  assert(await page.locator('#customerLoyaltyContent an-toàn').count()===0,'Reward API name became HTML');
  await page.locator('[data-next]').click();await page.locator('[data-redeem="5"]').waitFor();
  assert((await page.locator('.loyalty-reward').innerText()).includes('15%'),'Percent voucher missing');
  await page.locator('[data-prev]').click();await page.locator('[data-redeem="1"]').waitFor();
  await page.locator('[name=reward_type]').selectOption('physical_gift');await page.locator('[data-redeem="2"]').waitFor();
  await page.waitForFunction(()=>!document.querySelector('[data-list]')?.hasAttribute('aria-busy'));
  assert(await page.locator('[data-redeem="1"]').count()===0,'Type filter ignored');
  await page.locator('[name=reward_type]').selectOption('');
  await page.locator('[name=search]').fill('không tìm thấy');await page.locator('[data-filter] button').click();
  await page.getByText('Không có quà phù hợp với bộ lọc.',{exact:true}).waitFor();
  await page.locator('[name=search]').fill('');await page.locator('[data-filter] button').click();await page.locator('[data-redeem="1"]').waitFor();
  walletError=true;await page.locator('#reloadCustomerLoyalty').click();await page.locator('[data-reload-wallet]').waitFor();
  await page.getByRole('button',{name:'Chưa tải được điểm',exact:true}).first().waitFor();
  assert(await page.locator('[data-redeem="1"]').isDisabled(),'Wallet failure left redemption enabled');
  assert(!(await page.locator('[data-list]').innerText()).includes('Cần thêm'),'Unknown wallet reported insufficient points');
  walletError=false;await page.locator('[data-reload-wallet]').click();await page.waitForFunction(()=>!document.querySelector('[data-redeem="1"]')?.disabled);
  listError=true;await page.locator('#reloadCustomerLoyalty').click();await page.locator('[data-list] [data-reload]').waitFor();
  assert(await page.locator('#loyaltyBalance .loyalty-card').count()===4,'List failure erased wallet');
  assert(await page.locator('[data-pager] button').count()===0,'List error kept stale pagination');
  listError=false;await page.locator('[data-list] [data-reload]').click();await page.locator('[data-redeem="1"]').waitFor();
  for(const width of [360,390,768,1024,1440]){
   await page.setViewportSize({width,height:960});
   for(const view of ['history','rewards','mine']){
    await page.locator('#loyaltyTab-'+view).click();
    await page.waitForFunction(()=>!document.querySelector('[data-list]')?.hasAttribute('aria-busy'));
    await measure('#loyalty-section',mode,width,view);
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Rewards page overflows');
    await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
    if([390,1440].includes(width))await page.screenshot({path:'.test-tmp/customer-ui-rewards/'+mode+'-'+view+'-'+width+'.png',fullPage:true});
   }
  }
  await page.locator('[data-detail="11"]').click();await page.locator('#loyaltyRewardDialog').waitFor();
  await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('Fixture denied clipboard');}}}));
  await page.locator('#loyaltyRewardDialog [data-copy]').click();await page.locator('[data-copy-feedback]').filter({hasText:'BIN-TEST-11'}).waitFor();
  await measure('#loyaltyRewardDialog',mode,1440,'offer-dialog');
  await page.keyboard.press('Escape');await page.locator('#loyaltyRewardDialog').waitFor({state:'hidden'});
  assert(await page.locator('[data-detail="11"]').evaluate(e=>e===document.activeElement),'Offer dialog did not restore focus');
  for(const group of ['pickup','applied','done','closed','all']){
   await page.locator('[data-group="'+group+'"]').click();await page.waitForFunction(()=>!document.querySelector('[data-list]')?.hasAttribute('aria-busy'));
   assert(new URL(page.url()).searchParams.get('loyalty_status')===group,'Offer state missing from URL');
   if(group==='pickup')assert((await page.locator('[data-list]').innerText()).includes('Chờ nhận quà'),'Gift pickup status unclear');
   if(group==='applied')assert(await page.locator('[data-resume-invoice="55"]').count()===1&&await page.locator('a[href="/packages?purchase=401"]').count()===1,'Reserved offer resume target changed');
   if(group==='closed')assert(await page.locator('[data-list] [data-copy]').count()===0,'Closed offer still offers copy/use');
  }
  await page.locator('#loyaltyTab-rewards').click();await page.locator('[data-redeem="1"]').waitFor();
  await page.locator('[data-redeem="1"]').click();assert(await page.locator('[data-cancel]').evaluate(e=>e===document.activeElement),'Redemption should initially focus cancel');
  await page.locator('[data-confirm]').evaluate(e=>{e.click();e.click();});
  await page.getByText('Chưa xác nhận được kết quả đổi quà. Bấm “Thử lại” để kiểm tra; điểm sẽ không bị trừ hai lần.',{exact:true}).first().waitFor();
  assert(redeemPosts===1&&available===1000,'Double click charged twice');
  await page.keyboard.press('Escape');await page.reload();await page.locator('[data-pending-retry]').waitFor();
  await page.locator('[data-pending-retry]').click();await page.locator('[data-confirm]').click();
  await page.getByText('Đổi thưởng thành công',{exact:true}).waitFor();
  assert(redeemPosts===2&&processed.size===1&&keys[0]===keys[1]&&available===1000,'Lost response retry changed idempotency key or charged twice');
  assert(!await page.evaluate(()=>sessionStorage.getItem('binspa.loyalty.pendingRedeem')),'Resolved pending marker remains');
  await page.locator('[data-view-offers]').click();await page.locator('[data-offer="9001"]').waitFor();
  results.push({mode,lazy:true,keyboard:true,filters:true,walletAndListFailures:true,states:true,copyFeedback:true,focusRestored:true,lostResponseSameKey:true,singleRedemption:true,redeemPosts});
 }
 assert(errors.length===0&&failed.length===0,'Unexpected browser failures '+JSON.stringify({errors,failed}));
 return {results,typography,errors,failed};
}
