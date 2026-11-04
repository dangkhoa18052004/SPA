// Entry/styles below are filled from the isolated git HEAD build, never production assets.
async page => {
  const base='http://127.0.0.1:5088', checks=[];
  const assets={"entry": "portal-DrKDRDYU.js", "css": ["assets/portal-X09hJp6_.css"]};
  const login=async role=>{await page.goto(base+'/__qa/ping');await page.evaluate(async role=>{localStorage.clear();const d=await(await fetch('/__qa/login/'+role)).json();localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role',role);},role);};
  const replay=async route=>{
    let html=await(await route.fetch()).text();
    html=html.replace(/<link\b[^>]*href="\/static\/portal\/[^>]*>/g,'').replace(/<script type="module" src="\/static\/portal\/[^\"]+"><\/script>/g,`<script type="module" src="/static/portal/${assets.entry}"></script>`);
    html=html.replace('</head>',assets.css.map(file=>`<link rel="stylesheet" href="/static/portal/${file}">`).join('')+'</head>');
    await route.fulfill({body:html,contentType:'text/html'});
  };
  for(const version of ['before-head-react','after-matched']){
    if(version.startsWith('before')){
      await page.route('**/static/portal/**',r=>r.fulfill({path:'.test-tmp/master-head-61b8a54/app/static/portal/'+new URL(r.request().url()).pathname.split('/static/portal/')[1]}));
      await page.route('**/admin/chat',replay);await page.route('**/admin/loyalty?tab=redemptions',replay);await page.route('**/employee/account',replay);
    }
    for(const width of [390,1440]){
      await page.setViewportSize({width,height:960});await login('admin');
      await page.goto(base+'/admin/chat');await page.locator('.care-chat-grid').waitFor();await page.locator('.care-conversations button').first().waitFor();
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/${version}-inbox-${width}.png`,fullPage:true});
      await page.goto(base+'/admin/loyalty?tab=redemptions');await page.locator('[data-testid^="redemption-"]').first().waitFor();
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/${version}-gifts-${width}.png`,fullPage:true});
      await login('staff');await page.goto(base+'/employee/account');await page.locator('.portal-header').waitFor();
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/${version}-staff-navbar-${width}.png`,fullPage:true});checks.push({version,width});
    }
    await page.unrouteAll({behavior:'wait'});
  }
  return {assetSource:'git HEAD 61b8a54 isolated Vite build',checks};
}
