// Run with Playwright CLI against disposable preview 5080; review API data is mocked.
async page => {
 const base='http://127.0.0.1:5080',results=[],typography=[],errors=[],failed=[];
 const assert=(value,message)=>{if(!value)throw new Error(message);};
 const service={madv:1,tendv:'Chăm sóc da với tên dịch vụ dài để kiểm tra xuống dòng <an toàn>'};
 const sample=(id,malh)=>({madg:id,malh,rating:4,services:service.tendv,service_items:[service],comment:'Trải nghiệm tốt <script>không thực thi</script>\nNhân viên chu đáo.',created_at:'2026-10-18T03:00:00',updated_at:null,appointment_date:'2026-10-17T03:00:00',customer_name:'Khách T.',verified:true,reply:{content:'Spa cảm ơn bạn đã chia sẻ trải nghiệm.',created_at:'2026-10-19T03:00:00'}});
 let rows=[],listError=false,publicError=false,writeError=false,deleteError=false,contextError=false,gets=0,writes=0,deletes=0,contextGets=0,holdList=false,releaseList,held=false,holdContext=false,releaseContext;
 const reset=()=>{rows=[sample(101,77),{...sample(102,78),rating:5,comment:'',reply:null}];listError=publicError=writeError=deleteError=contextError=holdList=holdContext=held=false;gets=writes=deletes=contextGets=0;};
 page.on('pageerror',e=>errors.push(e.message));
 page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failed.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText});});
 await page.route('**/api/reviews**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  assert(url.origin===base,'Review fixture reached a live server');
  if(path==='/api/reviews/my'){
   gets++;const snapshot=JSON.parse(JSON.stringify(rows)),error=listError;
   if(holdList){holdList=false;held=true;await new Promise(resolve=>releaseList=resolve);}else await new Promise(resolve=>setTimeout(resolve,80));
   return route.fulfill(error?{status:503,json:{message:'Không tải được đánh giá. Vui lòng thử lại.'}}:{json:{success:true,reviews:snapshot}});
  }
  if(path.endsWith('/context')){
   contextGets++;const malh=Number(path.split('/').at(-2));
   if(holdContext){holdContext=false;await new Promise(resolve=>releaseContext=resolve);}else await new Promise(resolve=>setTimeout(resolve,100));
   if(contextError||malh===99)return route.fulfill({status:403,json:{message:'Chỉ có thể đánh giá lịch hẹn đã hoàn thành.'}});
   return route.fulfill({json:{success:true,malh,services:[service,{madv:2,tendv:'Massage thư giãn'}],review:rows.find(r=>r.malh===malh)||null}});
  }
  const id=Number(path.split('/').pop());
  if(request.method()==='DELETE'){
   deletes++;await new Promise(resolve=>setTimeout(resolve,180));
   if(deleteError){deleteError=false;return route.fulfill({status:503,json:{message:'Chưa xóa được. Vui lòng thử lại.'}});}
   rows=rows.filter(r=>r.madg!==id);return route.fulfill({json:{success:true}});
  }
  writes++;const payload=request.postDataJSON();await new Promise(resolve=>setTimeout(resolve,180));
  if(writeError){writeError=false;return route.fulfill({status:400,json:{message:'Không lưu được nhận xét. Vui lòng kiểm tra và thử lại.'}});}
  let r;
  if(request.method()==='PUT'){r=rows.find(r=>r.madg===id);Object.assign(r,payload,{updated_at:'2026-10-19T03:00:00'});}
  else {assert(payload.malh===88&&payload.service_ids.length===1&&payload.service_ids[0]===2,'Create payload changed appointment/service association');r={...sample(103,88),...payload,services:'Massage thư giãn',service_items:[{madv:2,tendv:'Massage thư giãn'}],reply:null};rows.unshift(r);}
  return route.fulfill({status:request.method()==='POST'?201:200,json:{success:true,review:r}});
 });
 await page.route('**/api/services/*/reviews**',async route=>{
  assert(new URL(route.request().url()).origin===base,'Public review fixture reached a live server');
  if(publicError)return route.fulfill({status:503,json:{message:'Đánh giá công khai chưa tải được.'}});
  const visible=rows.filter(r=>r.service_items.some(s=>s.madv===1));
  return route.fulfill({json:{success:true,stats:{average_rating:visible.length?+(visible.reduce((sum,r)=>sum+r.rating,0)/visible.length).toFixed(1):0,total_reviews:visible.length,distribution:Object.fromEntries([1,2,3,4,5].map(n=>[n,visible.filter(r=>r.rating===n).length]))},reviews:visible,page:1,total:visible.length,per_page:10}});
 });
 const measure=async(selector,mode,width,view)=>{
  const report=await page.locator(selector).evaluate(root=>{
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const rgb=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=c;ctx.fillRect(0,0,1,1);const d=ctx.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
   const mix=(a,b)=>a.slice(0,3).map((v,i)=>v*a[3]+b[i]*(1-a[3])).concat(1);
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
   const rect=root.getBoundingClientRect();
   return {checked,minimum:+minimum.toFixed(2),issues,overflow:root.scrollWidth>root.clientWidth,pageOverflow:document.documentElement.scrollWidth>innerWidth,centered:Math.abs(rect.x+rect.width/2-innerWidth/2)<2};
  });
  assert(!report.overflow&&!report.pageOverflow&&report.issues.length===0&&(!selector.includes('Dialog')||report.centered),'Review typography/layout '+JSON.stringify({mode,width,view,...report}));typography.push({mode,width,view,...report});
 };
 const settled=()=>page.waitForFunction(()=>!document.querySelector('#myReviews')?.hasAttribute('aria-busy'));
 const open=async id=>{await page.evaluate(id=>{void ReviewUI.openAppointmentReview(id);},id);await page.locator('#spaReviewDialog form').waitFor();};
 const closed=()=>page.locator('#spaReviewDialog').waitFor({state:'detached'});
 await page.request.get(base+'/__preview/session?customer=1');
 for(const mode of ['legacy','refactor']){
  reset();await page.goto(base+'/');await page.goto(base+'/profile'+(mode==='legacy'?'?ui=legacy':'')+'#info');
  await page.waitForFunction(()=>document.querySelector('#userName')?.textContent!=='Đang tải…');assert(gets===0,'Hidden reviews loaded eagerly');
  await page.locator('.menu-link[data-section=reviews]').click();await page.locator('#my-review-101').waitFor();await settled();
  assert(await page.locator('#customerReviewsCount').innerText()==='2 đánh giá','Review count missing');
  assert(await page.locator('#myReviews script').count()===0,'Review HTML was executed');
  assert((await page.locator('#my-review-101').innerText()).includes('<script>không thực thi</script>'),'Review text was lost');
  listError=true;await page.locator('#reloadCustomerReviews').click();await page.locator('[data-retry-reviews]').waitFor();
  assert(await page.locator('#myReviews [role=alert]').count()===1,'List failure not announced');listError=false;
  await page.locator('[data-retry-reviews]').click();await page.locator('#my-review-101').waitFor();await settled();
  holdList=true;await page.evaluate(()=>{void ReviewUI.loadMy();});await page.waitForTimeout(50);assert(held,'Stale response fixture did not start');
  rows=[...rows,{...sample(104,79),comment:'Phản hồi mới nhất'}];await page.evaluate(()=>ReviewUI.loadMy());releaseList();await page.waitForTimeout(150);
  assert(await page.locator('#my-review-104').count()===1,'Late list response overwrote newest data');rows=rows.filter(r=>r.madg!==104);
  await page.locator('#reloadCustomerReviews').click();await settled();
  for(const width of [360,390,768,1024,1440]){
   await page.setViewportSize({width,height:960});await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});
   await measure('#reviews-section',mode,width,'list');
   await page.screenshot({path:'.test-tmp/customer-ui-reviews/'+mode+'-list-'+width+'.png',fullPage:true});
   await page.locator('[data-edit-review="101"]').click();await page.locator('#spaReviewDialog form').waitFor();
   assert(await page.locator('[name=rating]:checked').inputValue()==='4','Existing rating not restored');
   assert(await page.locator('textarea[name=comment]').getAttribute('maxlength')==='5000','Comment limit changed');
   await measure('#spaReviewDialog',mode,width,'editor');
   await page.screenshot({path:'.test-tmp/customer-ui-reviews/'+mode+'-editor-'+width+'.png'});
   await page.keyboard.press('Escape');await closed();assert(await page.locator('[data-edit-review="101"]').evaluate(e=>e===document.activeElement),'Editor did not restore focus');
   await open(88);await measure('#spaReviewDialog',mode,width,'create-services');
   await page.screenshot({path:'.test-tmp/customer-ui-reviews/'+mode+'-create-'+width+'.png'});await page.keyboard.press('Escape');await closed();
   await page.locator('[data-delete-review="101"]').click();await page.locator('[data-confirm-delete]').waitFor();
   assert(await page.locator('[data-cancel-delete]').evaluate(e=>e===document.activeElement),'Delete should initially focus keep');
   await measure('#spaReviewDialog',mode,width,'delete');await page.locator('[data-cancel-delete]').click();await closed();
  }
  assert(deletes===0,'Cancel deleted a review');
  await page.locator('[data-edit-review="101"]').click();await page.locator('textarea[name=comment]').fill('Bản sửa được giữ lại khi lỗi <b>an toàn</b>');
  await page.locator('[name=rating][value="4"]').focus();await page.keyboard.press('ArrowLeft');assert(await page.locator('[name=rating]:checked').inputValue()==='3','Rating keyboard selection failed');
  writeError=true;await page.locator('#spaReviewDialog form').evaluate(f=>{f.requestSubmit();f.requestSubmit();});
  await page.keyboard.press('Escape');assert(await page.locator('#spaReviewDialog[aria-busy=true]').count()===1,'Busy editor closed before result');
  assert(await page.locator('#spaReviewDialog textarea').isDisabled(),'Busy editor allows a draft change after payload was sent');
  await page.getByText('Không lưu được nhận xét. Vui lòng kiểm tra và thử lại.',{exact:true}).waitFor();
  assert(writes===1&&(await page.locator('textarea[name=comment]').inputValue()).startsWith('Bản sửa'),'Repeated submit or lost error draft');
  await page.locator('#spaReviewDialog [type=submit]').click();await closed();await settled();
  assert(writes===2&&(await page.locator('#my-review-101').innerText()).includes('Bản sửa'),'Edit retry not reflected in list');
  assert((await page.locator('#customerReviewsMessage').innerText()).includes('Đã cập nhật'),'Edit success not announced');
  await open(88);await page.locator('textarea[name=comment]').fill('Đánh giá dịch vụ đã chọn');
  await page.locator('#spaReviewDialog [type=submit]').click();await page.getByText('Vui lòng chọn ít nhất một dịch vụ đã sử dụng.',{exact:true}).waitFor();
  assert(writes===2,'Invalid empty service selection was posted');await page.locator('[name=service][value="2"]').check();
  await page.locator('#spaReviewDialog form').evaluate(f=>{f.requestSubmit();f.requestSubmit();});await closed();await settled();
  assert(writes===3&&await page.locator('#my-review-103').count()===1,'Create posted twice or did not refresh');
  await page.evaluate(()=>{void ReviewUI.openAppointmentReview(99);});await page.getByText('Chỉ có thể đánh giá lịch hẹn đã hoàn thành.',{exact:true}).waitFor();
  assert(await page.locator('#spaReviewDialog form').count()===0,'Ineligible appointment opened editor');await page.keyboard.press('Escape');await closed();
  contextError=true;await page.evaluate(()=>{void ReviewUI.openAppointmentReview(88);});await page.locator('#spaReviewDialog [data-retry-reviews]').waitFor();contextError=false;
  await page.locator('#spaReviewDialog [data-retry-reviews]').click();await page.locator('#spaReviewDialog [data-edit]').waitFor();await page.keyboard.press('Escape');await closed();
  holdContext=true;await page.evaluate(()=>{void ReviewUI.openAppointmentReview(88);});await page.getByText('Đang kiểm tra lịch hẹn…',{exact:true}).waitFor();
  await page.keyboard.press('Escape');await closed();releaseContext();await page.waitForTimeout(150);assert(await page.locator('#spaReviewDialog').count()===0,'Cancelled context reopened itself');
  await page.locator('[data-delete-review="101"]').click();deleteError=true;
  await page.locator('[data-confirm-delete]').evaluate(e=>{e.click();e.click();});await page.getByText('Chưa xóa được. Vui lòng thử lại.',{exact:true}).waitFor();
  assert(deletes===1&&rows.some(r=>r.madg===101),'Failed delete changed list or duplicate delete');
  await page.locator('[data-confirm-delete]').click();await closed();await settled();assert(deletes===2&&await page.locator('#my-review-101').count()===0,'Delete retry did not refresh');
  assert((await page.locator('#customerReviewsMessage').innerText()).includes('Đã xóa'),'Delete success not announced');
  publicError=true;await page.goto(base+'/services/1'+(mode==='legacy'?'?ui=legacy':''));await page.locator('[data-service-reviews] [data-retry-reviews]').waitFor();
  publicError=false;await page.locator('[data-service-reviews] [data-retry-reviews]').click();await page.locator('[data-service-reviews] .review-card').waitFor();
  assert(await page.locator('[data-service-reviews] .review-card').count()===1,'Public list did not reflect deletion');
  assert((await page.locator('[data-stats]').innerText()).includes('5/5'),'Public statistics did not refresh');
  for(const width of [360,390,768,1024,1440]){await page.setViewportSize({width,height:960});await measure('[data-service-reviews]',mode,width,'public');}
  await page.evaluate(()=>{void ReviewUI.openAppointmentReview(78);});await page.locator('#spaReviewDialog [data-edit]').click();
  await page.locator('[name=rating][value="2"]').check();await page.locator('textarea[name=comment]').fill('Cập nhật ngay tại trang dịch vụ');
  await page.locator('#spaReviewDialog [type=submit]').click();await closed();
  await page.waitForFunction(()=>document.querySelector('[data-stats]')?.textContent.includes('2/5'));
  assert((await page.locator('[data-service-reviews] [data-list]').innerText()).includes('Cập nhật ngay tại trang dịch vụ'),'Public list did not refresh in place after edit');
  if(mode==='refactor'){
   // A stalled mutation must time out, preserve the draft and restore controls without resending.
   const stalled='**/api/reviews/102';let stalledWrites=0;await page.route(stalled,()=>{stalledWrites++;});
   await page.evaluate(()=>{void ReviewUI.openAppointmentReview(78);});await page.locator('#spaReviewDialog [data-edit]').click();
   await page.locator('textarea[name=comment]').fill('Bản nháp sau timeout');await page.locator('#spaReviewDialog [type=submit]').click();
   await page.getByText('Máy chủ phản hồi quá lâu. Vui lòng tải lại dữ liệu để kiểm tra kết quả trước khi thử lại.',{exact:true}).waitFor({timeout:25000});
   assert(stalledWrites===1&&await page.locator('#spaReviewDialog [type=submit]').isEnabled()&&await page.locator('textarea[name=comment]').inputValue()==='Bản nháp sau timeout','Timeout repeated a mutation, lost the draft or trapped the form');
   await page.keyboard.press('Escape');await closed();await page.unroute(stalled);
  }
  rows=[];await page.goto(base+'/profile'+(mode==='legacy'?'?ui=legacy':'')+'#reviews');await page.getByText('Bạn chưa có đánh giá nào. Bạn có thể đánh giá dịch vụ từ lịch hẹn đã hoàn thành.',{exact:true}).waitFor();
  assert(await page.locator('#myReviews a[href="#appointments"]').count()===1,'Empty reviews has no appointment action');
  await page.locator('#myReviews a').click();assert(new URL(page.url()).hash==='#appointments','Empty action lost appointment hash');
  results.push({mode,lazy:true,retry:true,staleResponse:true,cancel:true,editPreservesDraft:true,createServiceAssociation:true,duplicateSubmitBlocked:true,deleteRetry:true,publicRefresh:true,keyboardAndFocus:true,writes,deletes,contextGets});
 }
 assert(errors.length===0&&failed.length===0,'Unexpected browser failures '+JSON.stringify({errors,failed}));
 return {results,typography,errors,failed};
}
