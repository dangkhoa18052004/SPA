async page=>{
  const base='http://127.0.0.1:5088',errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  const login=async role=>{await page.goto(base+'/__qa/ping');await page.evaluate(async role=>{localStorage.clear();const d=await(await fetch('/__qa/login/'+role)).json();localStorage.setItem(role==='customer'?'access_token':'admin_token',d.access_token);localStorage.setItem('admin_role',d.role);},role);};
  await login('admin');let messageReads=0;const track=r=>{if(/\/messages$/.test(r.url())&&r.method()==='GET')messageReads++;};page.on('request',track);
  await page.goto(base+'/admin/chat');await page.locator('.care-conversation').first().waitFor();assert(messageReads===0,'Inbox/badge never reads threads');
  const unread=()=>page.evaluate(async()=>{const d=await(await fetch('/api/chat/conversations',{headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}})).json();return d.conversations.reduce((n,c)=>n+c.unread_count,0);});
  assert(await unread()===116,'Initial server unread');await page.locator('.chat-inbox-link .ant-badge-count').filter({hasText:'99+'}).waitFor();
  await page.locator('.care-chat-sidebar .ant-pagination-next button').click();await page.locator('.care-conversation').filter({hasText:'Khách chat 17'}).waitFor();
  assert(await page.locator('.care-conversation').count()===2,'Page 2');
  await page.evaluate(async()=>{const d=await(await fetch('/__qa/customer-token/17')).json();await fetch('/api/chat/conversations/17/messages',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+d.access_token},body:JSON.stringify({noidung:'Tin mới nhất kiểm thử'})});});
  await page.waitForFunction(()=>document.querySelector('.care-conversation')?.textContent.includes('Tin mới nhất kiểm thử'),{},{timeout:20000});
  assert(!new URL(page.url()).searchParams.has('page')||new URL(page.url()).searchParams.get('page')==='1','New message returns page 1');assert(messageReads===0,'List poll still no mark-read');
  await page.locator('.care-conversation').first().click();await page.locator('#chat-message-input').waitFor();await page.waitForFunction(()=>document.querySelector('.chat-inbox-link .ant-badge-count')?.textContent==='16');assert(await unread()===16,'Only open thread read');
  await page.locator('#chat-message-input').fill('Bản nháp cần giữ');
  await page.evaluate(()=>{window.__hidden=true;Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>window.__hidden?'hidden':'visible'});document.dispatchEvent(new Event('visibilitychange'));});
  const beforeHidden=messageReads;await page.waitForTimeout(5500);assert(messageReads===beforeHidden,'Hidden tab no message GET');
  await page.evaluate(()=>{window.__hidden=false;document.dispatchEvent(new Event('visibilitychange'));});
  assert(await page.locator('#chat-message-input').inputValue()==='Bản nháp cần giữ','Draft survives updates');
  let sends=0;await page.route('**/api/chat/conversations/17/messages',async route=>{if(route.request().method()==='POST')sends++;await route.continue();});
  await page.getByTestId('chat-send').evaluate(b=>{b.click();b.click();});await page.waitForFunction(()=>document.querySelector('#chat-message-input')?.value==='');assert(sends===1,'No double message POST');await page.unroute('**/api/chat/conversations/17/messages');page.off('request',track);
  for(const width of [360,390,768,1024,1440]){await page.setViewportSize({width,height:960});assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Inbox overflow');await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-inbox-${width}.png`});checks.push({width,inbox:true});}
  await login('staff');await page.goto(base+'/admin/chat');await page.locator('.care-conversation').first().waitFor();assert(await page.locator('.care-conversation').filter({hasText:'Khách chat 17'}).count()===0,'Assigned-only visibility');
  await login('customer');
  for(const legacy of [false,true])for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});await page.goto(base+'/'+(legacy?'?ui=legacy':''));
    await page.evaluate(()=>openChat());await page.locator('#chatBox.show').waitFor();
    assert((await page.locator('.chat-title').textContent()).includes('Nhắn tin'),'Human label');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-live-chat-${legacy?'legacy':'new'}-${width}.png`});
    // AI provider disabled in fixtures; expose only the existing widget UI for visual checks.
    await page.route('**/api/ai/status',r=>r.fulfill({json:{configured:true,enabled:true,booking_enabled:false}}));
    await page.reload();await page.locator('.ai-fab').waitFor();await page.locator('.ai-fab').click();
    assert(!await page.locator('#chatBox').evaluate(e=>e.classList.contains('show')),'Panels exclusive');
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-ai-chat-${legacy?'legacy':'new'}-${width}.png`});
    assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Chat overflow');await page.locator('.ai-icon-btn[data-close]').click();await page.unroute('**/api/ai/status');
    checks.push({width,legacy,chat:true});
  }
  assert(!errors.length,errors.join());return {checks,initialUnread:116,afterReadingOne:16,sends,errors};
}
