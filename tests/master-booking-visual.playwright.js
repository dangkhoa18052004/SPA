// Replay the initial booking entry against the same disposable fixture, then current entry.
async page=>{
  const base='http://127.0.0.1:5088', assets={"entry": "booking-BtUkMYav.js", "css": ["assets/booking-DNv67d61.css"]}, checks=[];
  await page.setViewportSize({width:390,height:960});await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
  await page.route('**/static/portal/**',r=>r.fulfill({path:'.test-tmp/master-head-61b8a54/app/static/portal/'+new URL(r.request().url()).pathname.split('/static/portal/')[1]}));
  await page.route('**/appointments/create?service=1',async route=>{let html=await(await route.fetch()).text();html=html.replace(/<link\b[^>]*href="\/static\/portal\/[^>]*>/g,'').replace(/<script type="module" src="\/static\/portal\/[^\"]+"><\/script>/g,`<script type="module" src="/static/portal/${assets.entry}"></script>`);html=html.replace('</head>',assets.css.map(f=>`<link rel="stylesheet" href="/static/portal/${f}">`).join('')+'</head>');await route.fulfill({body:html,contentType:'text/html'});});
  for(const before of [true,false]){
    if(!before)await page.unrouteAll({behavior:'wait'});
    await page.goto(base+'/appointments/create?service=1');await page.getByTestId('booking-next').waitFor();
    await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/${before?'before-head':'after-matched'}-booking-top-390.png`});
    if(!before)await page.getByTestId('booking-summary-open').click();
    const select=page.locator('[data-treatment-service="1"]');await select.scrollIntoViewIfNeeded();await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/${before?'before-head':'after-matched'}-booking-source-390.png`});
    const value=await select.locator('option').nth(1).getAttribute('value');await select.selectOption(value);await select.selectOption('');
    if(!before)await page.keyboard.press('Escape');checks.push({before,selectors:await select.count()});
  }
  return {checks,sameFixture:true,noMutation:true};
}
