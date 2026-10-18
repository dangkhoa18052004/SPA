async page => {
  const checks=[],errors=[],http=[];
  const check=(name,passed,detail)=>checks.push({name,passed,detail});
  const err=e=>errors.push(e.message),response=r=>{if(r.status()>=400)http.push({url:r.url(),status:r.status()});};
  page.on('pageerror',err);page.on('response',response);
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('.booking-service-card').first().waitFor();
  check('preselected_service',await page.locator('[data-service-id="3"][aria-pressed="true"]').count()===1);
  await page.getByTestId('booking-next').click();
  await page.getByRole('group',{name:'Giờ hẹn',exact:true}).waitFor();
  await page.getByRole('group',{name:'Giờ hẹn',exact:true}).locator('button:not([disabled])').first().click();
  await page.getByTestId('booking-next').click();
  await page.getByTestId('booking-recap').waitFor();
  check('booking_review',await page.getByTestId('booking-submit').isEnabled());
  for(const width of [1920,1366,768,390]){
    await page.setViewportSize({width,height:width===390?844:width===768?1024:1080});
    await page.screenshot({path:'output/binspa-qa/booking-review-'+width+'-after.png',fullPage:true,animations:'disabled'});
    check('booking_no_overflow_'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
  }
  await page.goto('https://127.0.0.1:5000/services/3',{waitUntil:'domcontentloaded'});
  await page.locator('.service-detail-name').waitFor();
  await page.waitForFunction(()=>!document.querySelector('[data-list]').textContent.includes('Đang tải'));
  check('reviews_loaded',true,await page.locator('[data-list]').innerText());
  await page.getByRole('button',{name:'Liên hệ',exact:true}).click();
  check('contact_chat',await page.locator('#chatBox').evaluate(e=>e.classList.contains('show')));
  await page.locator('.chat-close').click();
  await page.locator('#userBtn').click();
  await page.locator('#userDropdown a[onclick="logout()"]').click();
  await page.waitForURL('https://127.0.0.1:5000/');
  page.off('pageerror',err);page.off('response',response);
  return{checks,errors,http};
}
