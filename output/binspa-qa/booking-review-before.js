async page => {
  const errors=[],http=[];
  const err=e=>errors.push(e.message),res=r=>{if(r.status()>=400)http.push({url:r.url(),status:r.status()});};
  page.on('pageerror',err);page.on('response',res);
  await page.getByTestId('booking-next').click();
  await page.getByTestId('booking-date').waitFor();
  await page.getByRole('group',{name:'Giờ hẹn',exact:true}).waitFor({timeout:15000});
  const available=page.getByRole('group',{name:'Giờ hẹn',exact:true}).locator('button:not([disabled])');
  if(await available.count()) await available.first().click();
  await page.getByTestId('booking-next').click();
  await page.getByTestId('booking-recap').waitFor({timeout:15000});
  const checks=[];
  for(const width of [1920,1366,768,390]){
    await page.setViewportSize({width,height:width===390?844:width===768?1024:1080});
    await page.screenshot({path:'output/binspa-qa/booking-review-'+width+'-before.png',fullPage:true,animations:'disabled'});
    checks.push({width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),submitEnabled:await page.getByTestId('booking-submit').isEnabled()});
  }
  await page.goto('https://127.0.0.1:5000/services',{waitUntil:'domcontentloaded'});
  await page.locator('.service-card').first().waitFor();
  await page.locator('#mobileMenuBtn').click();
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('#navMenu')).opacity==='1');
  const menu=await page.locator('#navMenu').evaluate(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return{opacity:s.opacity,bg:s.backgroundColor,position:s.position,z:s.zIndex,rect:{x:r.x,y:r.y,width:r.width,height:r.height}}});
  await page.screenshot({path:'output/binspa-qa/mobile-menu-settled-before.png',animations:'disabled'});
  page.off('pageerror',err);page.off('response',res);
  return{checks,errors,http,menu};
}
