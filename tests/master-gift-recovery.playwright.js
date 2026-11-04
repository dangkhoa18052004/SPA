async page=>{
  const base='http://127.0.0.1:5088';let posts=0,failedRead=false,committed=false;
  const assert=(v,m)=>{if(!v)throw Error(m);};
  await page.goto(base+'/__qa/ping');await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/admin')).json();localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role','admin');});
  const gift=await page.evaluate(async()=>{const d=await(await fetch('/api/admin/loyalty/redemptions',{headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}})).json();return d.items.find(r=>r.reward.reward_type==='physical_gift'&&r.status==='available');});assert(!!gift,'Available isolated fixture gift');
  await page.route('**/api/admin/loyalty/redemptions?**',async route=>{if(committed&&!failedRead){failedRead=true;await route.fulfill({status:503,json:{message:'QA reconciliation temporarily unavailable'}});}else await route.continue();});
  await page.route(`**/api/admin/loyalty/redemptions/${gift.id}/fulfill`,async route=>{posts++;const r=await route.fetch();assert(r.ok(),'Server committed fulfillment');committed=true;await route.fulfill({status:503,json:{message:'QA lost committed response'}});});
  await page.goto(base+'/admin/loyalty?tab=redemptions');await page.getByTestId('redemption-'+gift.id).getByRole('button',{name:'Trao quà',exact:true}).click();await page.getByRole('button',{name:'Đã trao quà cho khách',exact:true}).evaluate(b=>{b.click();b.click();});
  await page.getByText('QA reconciliation temporarily unavailable',{exact:true}).waitFor();assert(posts===1,'One POST despite double click');assert(await page.getByRole('button',{name:'Đã trao quà cho khách',exact:true}).count()===0,'Stale confirmation removed');assert(await page.getByRole('button',{name:'Trao quà',exact:true}).count()===0,'Cannot retry without server state');
  await page.getByRole('button',{name:'Thử lại',exact:true}).click();await page.getByTestId('redemption-'+gift.id).getByText(/Đã trao lúc/).waitFor();assert(posts===1,'GET recovered without another POST');await page.unrouteAll({behavior:'wait'});return {posts,failedRead,recoveredThroughGet:true};
}
