async page => {
  const base='http://127.0.0.1:5079';const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__preview/session?customer=1');
  await page.goto(base+'/profile#info');
  await page.locator('#userName').filter({hasText:'Khách'}).waitFor();
  const uploaded=page.waitForResponse(r=>r.url().endsWith('/api/profile/upload-avatar')&&r.request().method()==='POST');
  await page.locator('#avatarInput').setInputFiles('E:/Project/Spa/SPA/app/static/images/logo.jpg');
  if(!(await (await uploaded).json()).success)throw new Error('Test avatar upload failed');
  await page.waitForFunction(()=>{const a=document.getElementById('avatarImg'),h=document.querySelector('#userBtn img');return a.src.includes('/api/profile/avatar/')&&a.src===h?.src;});
  const previous=await page.locator('#avatarImg').getAttribute('src');
  await page.route('**/api/profile/upload-avatar',route=>route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({success:false,message:'Ảnh kiểm thử bị từ chối'})}));
  await page.locator('#avatarInput').setInputFiles([]);
  await page.locator('#avatarInput').setInputFiles('E:/Project/Spa/SPA/app/static/images/logo.jpg');
  await page.getByText('Ảnh kiểm thử bị từ chối',{exact:true}).waitFor();
  if(await page.locator('#avatarImg').getAttribute('src')!==previous)throw new Error('Rejected avatar changed the UI');
  await page.unroute('**/api/profile/upload-avatar');
  if(errors.length)throw new Error(JSON.stringify(errors));
  return {avatarAndHeaderSyncedAfterSuccess:true,rejectedUploadKeepsPreviousAvatar:true,errors};
}
