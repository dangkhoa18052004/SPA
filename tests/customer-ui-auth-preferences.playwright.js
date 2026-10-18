async page => {
  const base='http://127.0.0.1:5079';const errors=[],checks=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__preview/session');
  await page.evaluate(()=>window.CustomerAuth.clearLocalSession());
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});
    for(const path of ['/auth/login','/auth/register','/auth/verify-otp','/auth/forgot-password','/auth/reset-password']){
      await page.goto(base+path,{waitUntil:'domcontentloaded'});
      await page.locator('body.customer-ui').waitFor();
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Auth overflow '+width+' '+path);
    }
  }
  await page.goto(base+'/auth/verify-otp');
  await page.locator('.otp-input').first().evaluate(input=>{const data=new DataTransfer();data.setData('text','123456');input.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true}));});
  if(await page.locator('.otp-input').evaluateAll(inputs=>inputs.map(i=>i.value).join(''))!=='123456')throw new Error('OTP paste failed');
  checks.push('Five auth pages at five viewports; OTP paste');
  await page.goto(base+'/auth/register');
  for(const [name,value] of Object.entries({hoten:'Khách test',email:'ui@example.com',sdt:'0900000088',diachi:'Local test',taikhoan:'ui_test',matkhau:'password123',confirm_password:'password123'}))await page.locator(`[name="${name}"]`).fill(value);
  await page.locator('[name=agree_terms]').check();
  let registrations=0;
  await page.route('**/api/auth/register',async route=>{registrations++;await new Promise(r=>setTimeout(r,250));await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({success:false,message:'Dữ liệu kiểm thử chưa hợp lệ'})});});
  await page.locator('#registerForm').evaluate(form=>{form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));});
  await page.getByRole('alert').filter({hasText:'Dữ liệu kiểm thử chưa hợp lệ'}).waitFor();
  if(registrations!==1)throw new Error('Duplicate registration request');
  await page.unroute('**/api/auth/register');
  checks.push('One registration request on repeated submit');
  await page.goto(base+'/__preview/session?customer=1');
  await page.goto(base+'/profile#communication');
  await page.locator('#communicationPreferences [type=submit]:enabled').waitFor();
  const lazy=await page.evaluate(()=>!performance.getEntriesByType('resource').some(r=>r.name.includes('account-panels')));
  if(!lazy)throw new Error('Heavy account controls loaded for preferences tab');
  let sentVersion;
  await page.route('**/api/me/communication-preferences',async route=>{
    if(route.request().method()==='PUT'){sentVersion=route.request().postDataJSON().version;await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({message:'Dữ liệu vừa thay đổi. Vui lòng tải lại.'})});}
    else await route.continue();
  });
  await page.locator('#communicationPreferences [type=submit]').click();
  await page.locator('#reloadCommunicationPreferences').waitFor({state:'visible'});
  if(!await page.locator('#communicationPreferences [type=submit]').isDisabled())throw new Error('Stale consent version can still be resubmitted');
  if(typeof sentVersion!=='number')throw new Error('Consent version omitted');
  await page.unroute('**/api/me/communication-preferences');
  checks.push('Preferences version and conflict reload; lazy account code');
  for(const width of [360,390,768,1024,1440]){
    await page.setViewportSize({width,height:960});
    for(const section of ['treatments','loyalty','reviews','info','communication']){
      await page.locator(`.menu-link[data-section=${section}]`).click();
      await page.locator(`#${section}-section.active`).waitFor();
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Account overflow '+width+' '+section);
    }
  }
  if(errors.length)throw new Error(JSON.stringify(errors));
  return {checks,registrations,consentVersion:sentVersion,remainingTabsResponsive:true,errors};
}
