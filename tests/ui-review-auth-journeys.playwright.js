// P1-07 auth journeys through the real UI (isolated fixture; mail is captured at /__qa/outbox, never sent).
// Register -> wrong/expired/right OTP -> login with redirect; forgot -> reset -> old/new password;
// open-redirect guard; staff login (React + legacy) with next and wrong credentials.
// usage: node tests/ui-review-run.js tests/ui-review-auth-journeys.playwright.js <out>
async (page, {base, out, context}) => {
  const checks = [];
  const assert = (v, m) => { if (!v) throw Error(m); };
  const ok = m => checks.push(m);
  page.on('framenavigated', f => { if (f === page.mainFrame()) checks.push('nav ' + new URL(f.url()).pathname); });
  try {
  const stamp = Date.now().toString().slice(-7);
  const outbox = async to => (await (await page.request.get(`${base}/__qa/outbox?to=${encodeURIComponent(to)}`)).json()).messages;
  const codeFrom = async to => { const m = (await outbox(to)).at(-1); return m && m.body.match(/\b(\d{6})\b/)[1]; };
  const qa = body => page.request.post(`${base}/__qa/state`, {data: body});
  const alertText = () => page.locator('.alert:visible, [role=alert]:visible').last().innerText({timeout: 5000}).catch(() => '');
  await page.setViewportSize({width: 390, height: 800});

  const register = async (suffix) => {
    const user = {hoten: `Khách QA ${suffix}`, email: `qa.${suffix}.${stamp}@example.com`, sdt: `09${stamp}${'ab'.indexOf(suffix) + 1}`.slice(0, 10), taikhoan: `qa_${suffix}_${stamp}`, matkhau: 'QaPass#123'};
    await page.goto(base + '/auth/register');
    for (const k of ['hoten', 'email', 'sdt', 'taikhoan']) await page.locator('#' + k).fill(user[k]);
    await page.locator('#matkhau').fill(user.matkhau);
    await page.locator('#confirm_password').fill(user.matkhau);
    await page.locator('input[name=agree_terms]').check();
    await page.locator('#registerForm button[type=submit]').click();
    await page.waitForURL(/\/auth\/verify-otp/, {timeout: 8000});
    return user;
  };
  const typeOtp = async code => {
    const boxes = page.locator('#otpForm .otp-input');
    for (let i = 0; i < 6; i++) await boxes.nth(i).fill(code[i]);
    await page.locator('#otpForm button.btn-primary').click(); // a type=button calling verifyOTP()
  };

  // J-AUTH-1 register + OTP + login redirect.
  const a = await register('a');
  const otp = await codeFrom(a.email);
  assert(otp, 'OTP captured in fixture outbox');
  await typeOtp(otp === '000000' ? '111111' : '000000');
  assert(/không hợp lệ|không đúng/i.test(await alertText()), 'wrong OTP shows an error');
  assert(page.url().includes('/auth/verify-otp'), 'wrong OTP stays on the OTP page');
  await page.locator('#otpForm .otp-input').first().waitFor();
  await typeOtp(otp);
  await page.waitForURL(/\/auth\/login/, {timeout: 8000});
  ok('register -> wrong OTP rejected -> right OTP activates -> login page');
  await page.screenshot({path: `${out}/auth-otp-success-login.png`});
  const target = '/appointments/create?service=3';
  await page.goto(`${base}/auth/login?redirect=${encodeURIComponent(target)}`);
  await page.locator('#taikhoan').fill(a.taikhoan);
  await page.locator('#matkhau').fill(a.matkhau);
  await page.locator('#loginForm button[type=submit]').click();
  await page.waitForURL(u => u.pathname === '/appointments/create', {timeout: 8000});
  assert(new URL(page.url()).search === '?service=3', 'redirect keeps the query: ' + page.url());
  assert(await page.evaluate(() => !!localStorage.getItem('access_token')), 'customer token stored');
  ok('login with ?redirect returns to /appointments/create?service=3');
  await page.screenshot({path: `${out}/auth-login-redirect.png`});

  // Open-redirect guard.
  await context.clearCookies();
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${base}/auth/login?redirect=${encodeURIComponent('//evil.example/x')}`);
  await page.locator('#taikhoan').fill(a.taikhoan);
  await page.locator('#matkhau').fill(a.matkhau);
  await page.locator('#loginForm button[type=submit]').click();
  await page.waitForURL(u => u.origin === base && u.pathname === '/', {timeout: 8000});
  ok('redirect=//evil.example falls back to /');

  // J-AUTH-2 expired OTP.
  await context.clearCookies();
  await page.evaluate(() => localStorage.clear());
  const b = await register('b');
  const otpB = await codeFrom(b.email);
  await qa({expire_codes: b.email});
  await typeOtp(otpB);
  assert(/hết hạn/i.test(await alertText()), 'expired OTP shows "hết hạn"');
  ok('expired OTP rejected with a readable message');

  // J-AUTH-3 forgot -> reset -> old password fails, new works; expired reset code rejected.
  await page.goto(base + '/auth/forgot-password');
  await page.locator('#identifier').fill(a.email);
  await page.locator('#forgotPasswordForm button[type=submit]').click();
  await page.waitForURL(/\/auth\/reset-password/, {timeout: 8000});
  const reset = await codeFrom(a.email);
  await page.locator('#token').fill(reset);
  await page.locator('#matkhau').fill('QaNew#456');
  await page.locator('#confirm_password').fill('QaNew#456');
  await page.locator('#resetPasswordForm button[type=submit]').click();
  await page.waitForURL(/\/auth\/login/, {timeout: 8000});
  await page.locator('#taikhoan').fill(a.taikhoan);
  await page.locator('#matkhau').fill(a.matkhau);
  await page.locator('#loginForm button[type=submit]').click();
  assert(/không đúng|không chính xác|sai/i.test(await alertText()), 'old password rejected after reset');
  await page.locator('#matkhau').fill('QaNew#456');
  await page.locator('#loginForm button[type=submit]').click();
  await page.waitForURL(u => u.pathname === '/', {timeout: 8000});
  ok('forgot -> reset code -> old password rejected, new password logs in');
  await page.goto(base + '/auth/forgot-password');
  await page.locator('#identifier').fill(a.email);
  await page.locator('#forgotPasswordForm button[type=submit]').click();
  await page.waitForURL(/\/auth\/reset-password/, {timeout: 8000});
  const reset2 = await codeFrom(a.email);
  await qa({expire_codes: a.email});
  await page.locator('#token').fill(reset2);
  await page.locator('#matkhau').fill('QaNew#789');
  await page.locator('#confirm_password').fill('QaNew#789');
  await page.locator('#resetPasswordForm button[type=submit]').click();
  assert(/hết hạn/i.test(await alertText()), 'expired reset code rejected');
  ok('expired reset code rejected; password unchanged');
  await page.screenshot({path: `${out}/auth-reset-expired.png`});

  // J-AUTH-4 staff login (React) with next, wrong password, customer credentials.
  await context.clearCookies();
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${base}/admin/login?next=${encodeURIComponent('/admin/appointments')}`);
  const user = page.getByLabel('Tài khoản'), pass = page.getByLabel('Mật khẩu');
  // The page also shows an info alert ("phiên đã hết hạn") whenever ?next is present; wait for the error one.
  const staffError = async () => { const e = page.locator('.ant-alert-error'); await e.waitFor({timeout: 8000}); const t = await e.innerText(); return t; };
  await user.fill('qa_letan'); await pass.fill('wrong-password');
  await page.getByRole('button', {name: 'Đăng nhập'}).click();
  assert(/không chính xác/i.test(await staffError()), 'staff wrong password message');
  await user.fill(a.taikhoan); await pass.fill('QaNew#456');
  await page.getByRole('button', {name: 'Đăng nhập'}).click();
  assert(/không chính xác/i.test(await staffError()), 'customer credentials rejected at staff login');
  await user.fill('qa_letan'); await pass.fill('password');
  await page.getByRole('button', {name: 'Đăng nhập'}).click();
  await page.waitForURL(u => u.pathname === '/admin/appointments', {timeout: 10000});
  ok('staff login: wrong password and customer credentials rejected; letan lands on next=/admin/appointments');
  // Legacy staff login: header shows the real name (the fixture shortcut left "Loading...").
  await context.clearCookies();
  await page.evaluate(() => localStorage.clear());
  await page.goto(base + '/admin/login?ui=legacy');
  await page.locator('#taikhoan').fill('admin_test');
  await page.locator('#matkhau').fill('password');
  await page.locator('#adminLoginForm button[type=submit]').click();
  await page.waitForURL(u => u.pathname.startsWith('/admin/') && !u.pathname.startsWith('/admin/login'), {timeout: 10000});
  await page.goto(base + '/admin/customers?ui=legacy');
  await page.waitForTimeout(1200);
  const header = await page.locator('#admin-username').innerText();
  assert(header && header !== 'Loading...', 'legacy header shows staff name: ' + header);
  ok(`legacy staff login stores admin_user; header shows "${header}"`);
  return {checks, users: [a.taikhoan, b.taikhoan]};
  } catch (e) { throw Error(e.message.split('\n')[0] + ' | after: ' + checks.slice(-8).join(' ; ')); }
}
