async page => {
  await page.waitForURL('https://127.0.0.1:5000/',{timeout:10000});
  await page.goto('https://127.0.0.1:5000/appointments/create?service=3',{waitUntil:'domcontentloaded'});
  await page.locator('.booking-service-card').first().waitFor({timeout:15000});
  const results=[];
  for(const width of [1920,1366,768,390]){
    await page.setViewportSize({width,height:width===390?844:width===768?1024:1080});
    await page.screenshot({path:'output/binspa-qa/booking-auth-'+width+'-before.png',fullPage:true});
    results.push(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,buttons:[...document.querySelectorAll('button')].map(b=>b.textContent.trim()).filter(Boolean).slice(-12),selected:[...document.querySelectorAll('[data-service-id][aria-pressed=true]')].map(e=>e.dataset.serviceId)})));
  }
  return results;
}
