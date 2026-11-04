async (page, ctx) => {
  // P1-03 auth states. Isolated fixture only (tests/master_ui_preview.py --port 5091 --all-ui); email sending is stubbed there.
  const base='http://127.0.0.1:5091', out=ctx?.out||'output/ui-review-2026-10-22', checks=[], notes={}, errors=[];
  const assert=(v,m)=>{if(!v)throw Error(m);};
  const onError=e=>errors.push(e.message);
  page.on('pageerror',onError);
  const posts={};const onRequest=r=>{if(r.method()==='POST'){const p=new URL(r.url()).pathname;posts[p]=(posts[p]||0)+1;}};
  page.on('request',onRequest);
  const reset=()=>{for(const k in posts)delete posts[k];};
  const signOutAll=()=>page.evaluate(async()=>{localStorage.clear();sessionStorage.clear();await fetch('/__qa/login/guest');await fetch('/api/auth/logout',{method:'POST'});});
  try {
    await page.setViewportSize({width:390,height:900});
    await page.goto(base+'/__qa/ping');await signOutAll();
    // Guest pages ask the server for a session at most once and do not keep asking while idle.
    notes.restore={};
    for(const path of ['/','/services','/packages','/auth/login','/auth/register']){
      reset();await page.goto(base+path);await page.waitForTimeout(4000);
      notes.restore[path]=posts['/api/auth/restore-session']||0;
      assert(notes.restore[path]<=1,`Guest ${path} restore calls: ${notes.restore[path]}`);
    }
    checks.push('Guest pages: at most one session-restore call each '+JSON.stringify(notes.restore));
    // Server session without a local token (cleared storage) still signs the customer back in.
    await page.evaluate(async()=>{await fetch('/__qa/login/customer');localStorage.clear();});
    await page.goto(base+'/profile#info');
    await page.getByText('Khách hàng Test').first().waitFor();
    assert(await page.evaluate(()=>!!localStorage.getItem('access_token')),'Token restored from server session');
    checks.push('Customer with a server session but no local token is restored on /profile');
    // Register: client validation blocks before POST; server error keeps every field; double click sends once.
    await signOutAll();await page.goto(base+'/auth/register');
    const fields={hoten:'Khách Đăng Ký QA',taikhoan:'qa_dangky',sdt:'0900000002',email:'qa-register@example.test',matkhau:'Matkhau@123',confirm_password:'Matkhau@124'};
    for(const [name,value] of Object.entries(fields))await page.locator(`[name="${name}"]`).fill(value);
    const agree=page.locator('#registerForm input[type=checkbox]');if(await agree.count())await agree.first().check();
    reset();await page.locator('#registerForm [type=submit]').click();
    await page.getByRole('alert').filter({hasText:'Mật khẩu xác nhận không khớp!'}).waitFor();
    assert(!posts['/api/auth/register'],'Mismatched password is not sent');
    await page.locator('[name="confirm_password"]').fill(fields.matkhau);fields.confirm_password=fields.matkhau;
    reset();await page.locator('#registerForm [type=submit]').dblclick();
    await page.getByRole('alert').filter({hasText:'SĐT này đã được đăng ký'}).waitFor();
    assert(posts['/api/auth/register']===1,'Double click registers once: '+posts['/api/auth/register']);
    for(const [name,value] of Object.entries(fields))assert(await page.locator(`[name="${name}"]`).inputValue()===value,'Register keeps '+name);
    assert(new URL(page.url()).pathname==='/auth/register','Stays on register after error');
    await page.screenshot({path:`${out}/p103-register-error-390.png`,fullPage:true});
    checks.push('Register: mismatch blocked client-side, duplicate phone message, one POST on double click, all fields kept');
    // Login: wrong password keeps input and sends once.
    await page.goto(base+'/auth/login');
    const user=page.locator('#loginForm input:not([type=password]):not([type=checkbox]):not([type=hidden])').first();
    await user.fill('0900000002');await page.locator('#loginForm input[type=password]').fill('sai-mat-khau');
    reset();await page.locator('#loginForm [type=submit]').dblclick();
    await page.getByRole('alert').filter({hasText:'Mật khẩu không đúng'}).waitFor();
    assert(posts['/api/auth/login/customer']===1&&await user.inputValue()==='0900000002','Wrong login: one POST, username kept');
    await page.screenshot({path:`${out}/p103-login-error-390.png`,fullPage:true});
    checks.push('Login: wrong password message, one POST on double click, username kept');
    // Logout then Back must not show the previous account (customer and staff).
    await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/customer')).json();localStorage.setItem('access_token',d.access_token);});
    await page.goto(base+'/profile#info');await page.getByText('Khách hàng Test').first().waitFor();
    await page.evaluate(()=>window.logout());
    await page.waitForURL(u=>new URL(u).pathname==='/');
    await page.goBack();await page.waitForURL(u=>new URL(u).pathname==='/auth/login');
    assert(!(await page.textContent('body')).includes('Khách hàng Test')&&!await page.evaluate(()=>localStorage.getItem('access_token')),'Customer Back after logout shows login, no account');
    await page.screenshot({path:`${out}/p103-customer-logout-back-390.png`,fullPage:true});
    await page.evaluate(async()=>{localStorage.clear();const d=await(await fetch('/__qa/login/admin')).json();localStorage.setItem('admin_token',d.access_token);localStorage.setItem('admin_role',d.role);});
    await page.goto(base+'/admin/dashboard');await page.getByText('Admin Test').first().waitFor({state:'attached'});
    await page.evaluate(async()=>{await fetch('/api/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('admin_token')}});localStorage.removeItem('admin_token');localStorage.removeItem('admin_role');location.assign('/admin/login');});
    await page.waitForURL(u=>new URL(u).pathname==='/admin/login');
    await page.goBack();await page.waitForURL(u=>new URL(u).pathname==='/admin/login');
    assert(!(await page.textContent('body')).includes('Admin Test'),'Admin Back after logout shows login');
    checks.push('Logout then Back: customer and admin land on login, previous account not shown');
    assert(!errors.length,errors.join('\n'));
    return {checks,notes,errors};
  } finally { page.off('pageerror',onError);page.off('request',onRequest); }
}
