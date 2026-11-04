async page=>{
  const base='http://127.0.0.1:5088',checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const assert=(v,m)=>{if(!v)throw Error(m);};
  const login=async role=>{await page.goto(base+'/__qa/ping');await page.evaluate(async role=>{localStorage.clear();const account=['staff','admin'].includes(role)?role+'_test':'qa_'+role;const r=await fetch('/api/auth/login/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({taikhoan:account,matkhau:'password'})});const d=await r.json();if(!r.ok)throw Error('Fixture login failed');localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role',d.user.role);localStorage.setItem('admin_user',JSON.stringify(d.user));},role);};
  for(const role of ['staff','admin','manager','letan']){
    await login(role);
    for(const width of [360,390,768,1024,1440]){
      await page.setViewportSize({width,height:960});
      for(const route of ['attendance','appointments','schedule','history','income','account']){
        await page.goto(base+'/employee/'+route);await page.locator('.portal-header').waitFor();
        assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'Staff header overflow '+width);
        if(width<768){await page.getByRole('button',{name:'Tài khoản nhân viên'}).click();await page.getByRole('menuitem',{name:'Trang cá nhân'}).click();}
        else await page.locator('.portal-header').getByRole('link',{name:'Trang cá nhân',exact:true}).click();
        await page.locator('.page-heading h1').filter({hasText:'Trang cá nhân'}).waitFor();await page.locator('.profile-head').waitFor();
        assert(new URL(page.url()).pathname==='/admin/profile','Direct profile');
        assert((await page.locator('.profile-head').textContent()).includes(role==='staff'?'Nhân viên Test':role==='admin'?'Admin Test':'Kiểm thử '+role),'Own profile');
        if(route==='account')await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-profile-${role}-${width}.png`});
        await page.getByTestId('attendance-shortcut').click();await page.locator('.portal-header').waitFor();
        checks.push({role,width,route,profile:true});
      }
      await page.screenshot({path:`output/refactor-2026-10-19/visual-before-after/after-staff-navbar-${role}-${width}.png`});
    }
    // Use the existing logout helper and verify both server request and local cleanup.
    let logouts=0;const track=r=>{if(r.url().endsWith('/api/auth/logout')&&r.method()==='POST')logouts++;};page.on('request',track);
    await page.locator('.portal-header').getByRole('button',{name:'Đăng xuất',exact:true}).click();await page.waitForURL('**/admin/login');
    assert(logouts===1,'One server logout');assert(await page.evaluate(()=>!localStorage.getItem('admin_token')),'Local token cleared');page.off('request',track);
  }
  await login('staff');await page.setViewportSize({width:390,height:960});await page.goto(base+'/employee/account');await page.getByRole('button',{name:'Tài khoản nhân viên'}).click();await page.getByRole('menuitem',{name:'Đăng xuất',exact:true}).click();await page.waitForURL('**/admin/login');
  assert(!errors.length,errors.join());return {checks:checks.length,roles:['staff','admin','manager','letan'],routes:6,widths:5,actualLoginApi:true,desktopMobileLogout:true,errors};
}
