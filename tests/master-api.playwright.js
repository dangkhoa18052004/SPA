async page => {
  const base='http://127.0.0.1:5088';
  await page.goto(base+'/services');
  return await page.evaluate(async()=>{
    const get=async q=>{const r=await fetch('/api/services'+q);return {status:r.status,data:await r.json()};};
    const full=await get(''), categories=await get('/categories');
    if(full.data.services.length!==25) throw Error('Full-list compatibility');
    if(categories.data.categories.length!==2||categories.data.categories.some(c=>c.service_count!==12))throw Error('DB categories');
    const pages=await Promise.all([1,2,3].map(p=>get('?page='+p)));
    if(pages.map(p=>p.data.services.length).join()!=='9,9,7')throw Error('9/9/7 pagination');
    if((await get('?min_price=invalid')).status!==400)throw Error('Validation');
    if((await get('?category=acne')).data.total!==12)throw Error('Category exact matching');
    return {full:25,categories:2,pages:[9,9,7],validation:400,exactCategory:12};
  });
}
