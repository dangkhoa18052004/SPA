// P1-07 cross-screen journeys through the real UI on the isolated 5091 fixture.
// API calls are used only for setup (sale/gift) and to verify the data the UI produced.
// usage: node tests/ui-review-run.js tests/ui-review-journeys.playwright.js <out> [J01,J04,J10]
async (page, {base, out, args, context}) => {
  const only = (args[0] || 'J01,J04,J10').split(',');
  const assert = (v, m) => { if (!v) throw Error(m); };
  const checks = [], trace = [];
  const step = m => trace.push(m);
  const token = () => page.evaluate(() => localStorage.getItem('admin_token') || localStorage.getItem('access_token'));
  const call = async (path, method = 'GET', body) => {
    const r = await page.request.fetch(base + path, {method, headers: {Authorization: 'Bearer ' + await token(), 'Content-Type': 'application/json'}, data: body});
    return {status: r.status(), data: await r.json().catch(() => ({}))};
  };
  const signIn = async (role) => {
    await context.clearCookies();
    await page.goto(base + '/__qa/ping');
    await page.evaluate(async role => {
      localStorage.clear();
      const d = await (await fetch('/__qa/login/' + role)).json();
      if (d.access_token) { localStorage.setItem(role === 'customer' ? 'access_token' : 'admin_token', d.access_token); if (role !== 'customer') localStorage.setItem('admin_role', d.role); }
    }, role);
  };
  const vnDay = offset => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Ho_Chi_Minh'}).format(new Date(Date.now() + offset * 864e5));
  const myAppointments = async () => (await call('/api/appointments/my-appointments')).data;
  const list = d => Array.isArray(d) ? d : (d.appointments || d.data || []);
  // Booking wizard on /appointments/create (service already chosen by the URL): date +3 (fixture shift), first free slot.
  const bookThroughWizard = async () => {
    await page.getByTestId('booking-next').click();
    await page.getByTestId('booking-date').fill(vnDay(3));
    const slot = page.locator('[data-slot]:not([disabled])').first();
    await slot.waitFor({timeout: 10000});
    const time = await slot.getAttribute('data-slot');
    await slot.click();
    await page.getByTestId('booking-next').click();
    await page.getByTestId('booking-submit').click();
    await page.getByTestId('booking-success').waitFor({timeout: 10000});
    return time;
  };
  // Internal row actions on /admin/appointments (desktop table): confirm/check-in until "Hoàn thành" is done.
  const completeInAdmin = async malh => {
    await page.setViewportSize({width: 1440, height: 900});
    await page.goto(base + `/admin/appointments?q=${malh}`);
    const row = page.locator(`tr[data-row-key="${malh}"]`);
    await row.waitFor({timeout: 10000});
    for (const label of ['Xác nhận', 'Check-in', 'Hoàn thành']) {
      const button = row.getByRole('button', {name: new RegExp('^' + label)});
      if (!(await button.count())) continue;
      await button.first().click();
      const dialog = page.locator('.ant-modal-confirm');
      await dialog.waitFor();
      await dialog.getByRole('button', {name: label, exact: true}).click();
      await dialog.waitFor({state: 'detached'});
      step('admin ' + label);
      await page.waitForTimeout(500);
    }
  };
  try {
    if (only.includes('J01')) {
      // J01 guest browses a service -> logs in -> books -> sees it in the profile.
      await context.clearCookies();
      await page.goto(base + '/__qa/ping');
      await page.evaluate(() => localStorage.clear());
      await page.setViewportSize({width: 390, height: 844});
      await page.goto(base + '/services');
      const detail = page.locator('#servicesGrid a[href^="/services/"]').first();
      await detail.waitFor();
      const href = await detail.getAttribute('href');
      const madv = Number(href.split('/').pop());
      await detail.click();
      await page.waitForURL(u => u.pathname === href);
      const serviceName = (await page.locator('h1').first().innerText()).trim();
      await page.getByRole('link', {name: /Đặt lịch ngay/}).click();
      await page.waitForURL(u => u.pathname === '/appointments/create');
      await page.getByRole('link', {name: 'Đăng nhập / Đăng ký'}).click();
      await page.waitForURL(/\/auth\/login\?redirect=/);
      await page.locator('#taikhoan').fill('customer_test');
      await page.locator('#matkhau').fill('password');
      await page.locator('#loginForm button[type=submit]').click();
      await page.waitForURL(u => u.pathname === '/appointments/create' && u.search.includes('service=' + madv), {timeout: 10000});
      step('J01 login returned to booking for service ' + madv);
      const before = list(await myAppointments()).length;
      const time = await bookThroughWizard();
      const after = list(await myAppointments());
      assert(after.length === before + 1, `J01 exactly one appointment created (${before} -> ${after.length})`);
      const created = after.map(a => ({...a, text: JSON.stringify(a)})).find(a => a.text.includes(vnDay(3).split('-').reverse().join('/')) || a.text.includes(vnDay(3)));
      assert(created && created.text.includes(time) && created.text.includes(serviceName.slice(0, 12)), 'J01 appointment has the chosen service/day/time: ' + JSON.stringify(after.at(-1)).slice(0, 300));
      await page.goto(base + '/profile#appointments');
      await page.getByText(serviceName.slice(0, 12)).first().waitFor();
      await page.screenshot({path: `${out}/j01-profile-appointments-390.png`, fullPage: true});
      checks.push(`J01 /services -> ${href} -> login -> booked ${serviceName} ${vnDay(3)} ${time} -> visible in /profile#appointments (1 new row)`);
    }
    if (only.includes('J04')) {
      // J04 gift booking cancelled by the customer, rebooked, completed by the desk.
      await signIn('admin');
      const makh = (await call('/api/admin/package-sales/customers?search=0900000002')).data.customers[0].makh;
      const sale = await call('/api/admin/package-sales', 'POST', {makh, magoi: 3, payment_method: 'cash'});
      const paid = await call(`/api/admin/packages/purchases/${sale.data.purchase.id}/confirm-payment`, 'POST', {cash_received: sale.data.purchase.payable_amount});
      const mathe = paid.data.mathe;
      const service = (await call('/api/admin/packages/treatments/' + mathe)).data.services.find(s => s.tendv.startsWith('Dịch vụ 05'));
      const gift = await call(`/api/admin/packages/treatments/${mathe}/gifts`, 'POST', {makh, madv: service.madv, quantity: 1, gift_note: 'J04'});
      const item = gift.data.item_id;
      const itemState = async () => (await call('/api/packages/my-treatments/' + mathe)).data.treatment.items.find(i => i.id === item);
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      const bookGift = async () => {
        await page.goto(base + '/profile#treatments');
        const link = page.locator(`a[href*="treatment=${mathe}"][href*="item=${item}"]`);
        await link.waitFor({timeout: 10000});
        await link.click();
        await page.waitForURL(u => u.pathname === '/appointments/create');
        return bookThroughWizard();
      };
      const firstTime = await bookGift();
      let s = await itemState();
      assert(s.reserved === 1 && s.available_sessions === 0, 'J04 booking reserves the gift: ' + JSON.stringify(s));
      // Customer cancels from the profile (confirm dialog).
      await page.goto(base + '/profile#appointments');
      // The "Hủy lịch" button whose own card names the gift service.
      const cancelButtons = page.getByRole('button', {name: 'Hủy lịch'});
      await cancelButtons.first().waitFor({timeout: 10000});
      // Card = the largest ancestor that still holds only this cancel button; match service + booked time.
      const index = await cancelButtons.evaluateAll((bs, time) => bs.findIndex(b => {
        let card = b;
        while (card.parentElement && [...card.parentElement.querySelectorAll('button')].filter(x => x.textContent.trim() === 'Hủy lịch').length === 1) card = card.parentElement;
        return card.textContent.includes('Dịch vụ 05') && card.textContent.includes(time);
      }), firstTime);
      assert(index >= 0, 'J04 gift appointment has a cancel button in the profile');
      await cancelButtons.nth(index).click();
      const dialog = page.locator('.ant-modal-confirm');
      await dialog.waitFor();
      await page.screenshot({path: `${out}/j04-customer-cancel-confirm-390.png`});
      await dialog.getByRole('button', {name: 'Hủy lịch', exact: true}).click();
      await dialog.waitFor({state: 'detached'});
      await page.waitForTimeout(800);
      s = await itemState();
      assert(s.reserved === 0 && s.available_sessions === 1, 'J04 cancel in the profile releases the gift: ' + JSON.stringify(s));
      step('J04 customer cancelled the ' + firstTime + ' gift booking');
      const known = new Set(list(await myAppointments()).map(a => a.malh));
      await bookGift();
      const fresh = list(await myAppointments()).filter(a => !known.has(a.malh));
      assert(fresh.length === 1, 'J04 rebooking creates exactly one appointment, got ' + fresh.length);
      const rebooked = fresh[0];
      await signIn('admin');
      await completeInAdmin(rebooked.malh);
      await page.screenshot({path: `${out}/j04-admin-completed-1440.png`});
      await signIn('customer');
      s = await itemState();
      assert(s.consumed === 1 && s.reserved === 0 && s.available_sessions === 0, 'J04 desk completion consumes the gift once: ' + JSON.stringify(s));
      const history = (await call('/api/packages/my-treatments/' + mathe)).data.treatment.history || [];
      const consumed = history.filter(h => h.the_item_id === item && h.state === 'consumed').length;
      assert(consumed === 1, 'J04 one consumed ledger row, got ' + consumed);
      await page.goto(base + '/profile#treatments');
      await page.locator('a[href^="/appointments/create?treatment="]').first().waitFor({timeout: 10000}).catch(() => {});
      assert(await page.locator(`a[href*="item=${item}"]`).count() === 0, 'J04 used gift has no booking link');
      checks.push(`J04 gift item ${item}: UI book -> UI cancel (released) -> UI rebook -> admin UI complete (#${rebooked.malh}) -> consumed once, no link left`);
    }
    if (only.includes('J02')) {
      // J02 customer buys a package by VietQR (fake bank confirmation via fixture) -> treatment active once.
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      const treatments = async () => (await call('/api/packages/my-treatments')).data.treatments || [];
      const before = (await treatments()).map(t => t.mathe);
      await page.goto(base + '/packages/5');
      const buy = page.locator('[data-buy="5"]');
      await buy.waitFor({timeout: 10000});
      const packageName = (await page.locator('#packageList h2, #packageList h3').first().innerText()).trim();
      const created = page.waitForResponse(r => r.url().endsWith('/api/packages/5/purchase') && r.request().method() === 'POST');
      await buy.click();
      const purchase = (await (await created).json()).purchase;
      const dialog = page.locator('#packagePaymentDialog');
      await dialog.getByRole('button', {name: 'Tiếp tục thanh toán VietQR'}).click();
      await dialog.locator('[data-package-qr] img').waitFor();
      await page.screenshot({path: `${out}/j02-vietqr-pending-390.png`});
      const pendingNew = (await treatments()).filter(t => !before.includes(t.mathe));
      assert(pendingNew.every(t => t.status !== 'active'), 'J02 unpaid purchase has no active treatment: ' + JSON.stringify(pendingNew));
      // Fake bank webhook (same service as the real confirmation), then the dialog must update by itself.
      const confirm = await page.request.post(`${base}/__qa/state`, {data: {vietqr_paid: purchase.id}});
      assert(confirm.ok(), 'fixture bank confirmation');
      await dialog.getByRole('heading', {name: 'Thanh toán thành công'}).waitFor({timeout: 15000});
      await page.screenshot({path: `${out}/j02-vietqr-paid-390.png`});
      const second = await page.request.post(`${base}/__qa/state`, {data: {vietqr_paid: purchase.id}}).catch(e => e);
      step('second bank confirmation status ' + (second.status ? second.status() : 'error'));
      const fresh = (await treatments()).filter(t => !before.includes(t.mathe));
      assert(fresh.length === 1 && fresh[0].status === 'active', 'J02 exactly one active treatment after payment: ' + JSON.stringify(fresh.map(t => [t.mathe, t.status])));
      const t = fresh[0];
      const sessions = (t.items || []).filter(i => i.source_type !== 'gift').reduce((n, i) => n + i.total_sessions, 0);
      assert(sessions === 10 && t.expires_at, `J02 10 sessions and an expiry, got ${sessions} / ${t.expires_at}`);
      await dialog.getByRole('link', {name: 'Liệu trình của tôi'}).click();
      await page.waitForURL(u => u.pathname === '/profile');
      await page.getByText('#' + t.mathe).first().waitFor({timeout: 10000}).catch(() => {});
      await page.screenshot({path: `${out}/j02-profile-treatments-390.png`, fullPage: true});
      checks.push(`J02 ${packageName}: PKG${purchase.id} pending -> no active treatment; fake bank confirm -> dialog "Thanh toán thành công" -> one active treatment #${t.mathe}, 10 sessions, expires ${t.expires_at}`);
    }
    if (only.includes('J08')) {
      // J08 customer chat -> internal unread/reply -> customer sees reply -> another customer sees none of it.
      const text = 'QA J08 ' + Date.now().toString().slice(-6);
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      await page.goto(base + '/');
      await page.locator('#chatFloat').click();
      await page.locator('#chatBox.show').waitFor();
      await page.locator('#chatInput').fill(text);
      await page.getByRole('button', {name: 'Gửi tin nhắn'}).click();
      await page.locator('#chatMessages').getByText(text).waitFor();
      const conversation = (await call('/api/chat/conversations')).data;
      const maht = (conversation.conversations || conversation.data || [conversation.conversation || conversation]).flat()[0]?.maht ?? conversation.maht;
      step('customer conversation ' + maht);
      await signIn('admin');
      await page.setViewportSize({width: 1440, height: 900});
      const unread = async () => ((await call('/api/chat/conversations')).data.conversations.find(c => c.maht === maht) || {}).unread_count;
      const unreadBefore = await unread();
      assert(unreadBefore >= 1, 'J08 internal side sees the new message as unread, got ' + unreadBefore);
      // The header badge caps at 99+ with this fixture, so check the conversation row itself.
      await page.goto(base + '/admin/chat?q=' + encodeURIComponent('Khách hàng Test'));
      const item = page.locator('button.care-conversation').filter({hasText: text});
      await item.waitFor();
      assert(await item.evaluate(b => b.classList.contains('is-unread')), 'J08 conversation row is marked unread');
      await item.click();
      await page.locator('#chat-message-input').waitFor();
      await page.getByText(text).first().waitFor();
      await page.locator('#chat-message-input').fill('Phản hồi ' + text);
      await page.getByTestId('chat-send').click();
      await page.getByText('Phản hồi ' + text).first().waitFor();
      await page.screenshot({path: `${out}/j08-admin-reply-1440.png`});
      await page.waitForTimeout(800);
      const unreadAfter = await unread();
      await page.goto(base + '/admin/chat?q=' + encodeURIComponent('Khách hàng Test'));
      await item.waitFor();
      const stillMarked = await item.evaluate(b => b.classList.contains('is-unread'));
      step(`conversation unread ${unreadBefore} -> ${unreadAfter}, row unread=${stillMarked}`);
      assert(unreadAfter === 0 && !stillMarked, `J08 opening the conversation marks it read (${unreadBefore} -> ${unreadAfter}, row ${stillMarked})`);
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      await page.goto(base + '/');
      await page.locator('#chatFloat').click();
      await page.locator('#chatMessages').getByText('Phản hồi ' + text).waitFor({timeout: 15000});
      await page.screenshot({path: `${out}/j08-customer-sees-reply-390.png`});
      // Switch account in the same browser: another customer must not see this thread.
      await page.getByRole('button', {name: 'Tài khoản'}).first().click().catch(() => {});
      await context.clearCookies();
      const other = await (await page.request.get(base + '/__qa/customer-token/2')).json();
      await page.evaluate(t => { localStorage.clear(); localStorage.setItem('access_token', t); }, other.access_token);
      await page.goto(base + '/');
      await page.locator('#chatFloat').click();
      await page.locator('#chatBox.show').waitFor();
      await page.waitForTimeout(2500);
      assert(await page.locator('#chatMessages').getByText(text).count() === 0, 'J08 another customer does not see the previous thread');
      checks.push(`J08 conversation ${maht}: customer UI send -> admin UI opens (unread ${unreadBefore} -> ${unreadAfter}) and replies -> customer sees reply; second customer sees none of it`);
    }
    if (only.includes('J09')) {
      // J09 redeemed voucher applied in the package payment UI -> fake bank pays the discounted amount -> history.
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      const rewards = async () => (await call('/api/loyalty/my-rewards?per_page=100')).data.items || [];
      const before = await rewards();
      const gift = before.find(r => r.reward.reward_type === 'physical_gift');
      await page.goto(base + '/packages/6');
      const buy = page.locator('[data-buy="6"]');
      await buy.waitFor({timeout: 10000});
      const created = page.waitForResponse(r => r.url().endsWith('/api/packages/6/purchase') && r.request().method() === 'POST');
      await buy.click();
      const purchase = (await (await created).json()).purchase;
      const dialog = page.locator('#packagePaymentDialog');
      const option = dialog.locator('[data-voucher]:not([disabled])').first();
      await option.waitFor({timeout: 10000});
      const voucherId = Number(await option.getAttribute('value'));
      await option.check();
      await dialog.locator('[data-apply-voucher]').click();
      await dialog.locator('[data-applied-voucher]').waitFor();
      const payableText = await dialog.locator('.loyalty-payment').innerText();
      await page.screenshot({path: `${out}/j09-voucher-applied-390.png`});
      const price = Number(purchase.amount), expected = Math.round(price * 0.7);
      const state = (await call(`/api/packages/purchases/${purchase.id}`)).data.purchase;
      assert(Math.round(Number(state.payable_amount)) === expected && Number(state.amount) === price,
        `J09 30% voucher: amount ${state.amount}, payable ${state.payable_amount}, expected ${expected}`);
      await dialog.getByRole('button', {name: 'Tiếp tục thanh toán VietQR'}).click();
      const qrText = await dialog.locator('[data-package-qr]').innerText();
      assert(qrText.replace(/\D/g, '').includes(String(expected)), 'J09 QR asks for the discounted amount: ' + qrText);
      await page.request.post(`${base}/__qa/state`, {data: {vietqr_paid: purchase.id}});
      await dialog.getByRole('heading', {name: 'Thanh toán thành công'}).waitFor({timeout: 15000});
      await page.screenshot({path: `${out}/j09-paid-with-voucher-390.png`});
      const after = await rewards();
      const used = after.find(r => r.id === voucherId);
      assert(used && used.status === 'used', 'J09 voucher marked used: ' + JSON.stringify(used && used.status));
      const giftAfter = gift && after.find(r => r.id === gift.id);
      assert(!gift || giftAfter.status === gift.status, 'J09 physical gift untouched by the payment');
      await page.goto(base + '/profile#loyalty');
      await page.getByText(used.code).first().waitFor({timeout: 10000}).catch(() => {});
      await page.screenshot({path: `${out}/j09-profile-loyalty-390.png`, fullPage: true});
      checks.push(`J09 PKG${purchase.id}: price ${price}, voucher #${voucherId} applied in UI -> payable ${expected} (QR shows it) -> paid -> voucher used, physical gift ${gift ? gift.status : 'n/a'} unchanged`);
      step(payableText.replace(/\s+/g, ' ').slice(0, 160));
    }
    if (only.includes('J06')) {
      // J06 technician: dashboard -> own appointment -> that customer's treatment -> gift (staff may gift).
      await signIn('admin');
      const today = (await call('/api/admin/appointments?range=today')).data;
      const rowsToday = today.appointments || today.data || today;
      await signIn('staff');
      await page.setViewportSize({width: 390, height: 844});
      await page.goto(base + '/admin/dashboard');
      const open = page.getByRole('link', {name: 'Mở lịch hẹn'}).or(page.getByRole('button', {name: 'Mở lịch hẹn'})).first();
      await open.waitFor({timeout: 10000});
      const visibleCount = await page.getByRole('link', {name: 'Mở lịch hẹn'}).or(page.getByRole('button', {name: 'Mở lịch hẹn'})).count();
      await open.click();
      await page.waitForURL(u => u.pathname === '/employee/appointments' && u.searchParams.has('view'));
      const drawer = page.locator('.ant-drawer-open');
      await drawer.waitFor();
      const customer = (await drawer.locator('h2').innerText()).trim();
      const phone = (await drawer.locator('tr').filter({hasText: 'Số điện thoại'}).locator('.ant-descriptions-item-content').innerText()).trim();
      await page.screenshot({path: `${out}/j06-staff-own-appointment-390.png`});
      // Another technician's appointment is not opened (P1-02 rule, checked again here through the UI).
      const foreign = (Array.isArray(rowsToday) ? rowsToday : []).find(r => (r.nhanvien_hoten || '').includes('2') || r.manv && r.manv !== undefined && r.khachhang_hoten !== customer);
      if (foreign) {
        await page.goto(base + `/employee/appointments?view=${foreign.malh}`);
        await page.getByText(`Không tìm thấy lịch hẹn #${foreign.malh}`).waitFor();
        assert(await page.locator('.ant-drawer-open').count() === 0, 'J06 foreign appointment not shown');
      }
      // Treatments of that customer, then gift through the drawer.
      await page.goto(base + '/admin/packages?tab=treatments&tq=' + encodeURIComponent(phone));
      const giftButton = page.getByRole('button', {name: 'Tặng thêm dịch vụ'}).first();
      await giftButton.waitFor({timeout: 10000});
      await giftButton.click();
      await page.waitForURL(u => u.searchParams.get('gift') === '1');
      const mathe = Number(new URL(page.url()).searchParams.get('mathe'));
      const modal = page.locator('.ant-modal').filter({hasText: 'Tặng dịch vụ'});
      await modal.waitFor();
      const box = modal.getByRole('combobox', {name: 'Dịch vụ tặng', exact: true});
      await box.click();
      await box.fill('Dịch vụ 06');
      const id = await box.getAttribute('aria-controls');
      await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').filter({has: page.locator(`[id="${id}"]`)})
        .locator('.ant-select-item-option').filter({hasText: 'Dịch vụ 06'}).click();
      await modal.getByRole('textbox', {name: 'Ghi chú'}).fill('J06 kỹ thuật viên tặng');
      const sent = page.waitForResponse(r => /\/gifts$/.test(r.url()) && r.request().method() === 'POST');
      await modal.getByRole('button', {name: 'Xác nhận tặng', exact: true}).click();
      const response = await sent;
      assert(response.status() === 201, 'J06 staff gift accepted, got ' + response.status());
      await modal.waitFor({state: 'hidden'});
      const detail = (await call('/api/admin/packages/treatments/' + mathe)).data.treatment;
      const given = detail.items.filter(i => i.source_type === 'gift' && i.gift_note === 'J06 kỹ thuật viên tặng');
      assert(given.length === 1 && detail.customer_name === customer, `J06 one gift on ${customer}'s treatment: ` + JSON.stringify(given.map(g => g.gifted_by_name)));
      await page.screenshot({path: `${out}/j06-staff-gift-done-390.png`, fullPage: true});
      checks.push(`J06 staff dashboard (${visibleCount} own rows) -> ${customer} (${phone}) -> treatment #${mathe} -> gift by ${given[0].gifted_by_name}${foreign ? `; foreign #${foreign.malh} not opened` : ''}`);
    }
    if (only.includes('J10')) {
      // J10 booking submit loses the response after the server committed: no duplicate, the page reconciles.
      await signIn('customer');
      await page.setViewportSize({width: 390, height: 844});
      await page.goto(base + '/appointments/create?service=7');
      const before = list(await myAppointments()).length;
      let creates = 0;
      await page.route('**/api/appointments/create', async route => { creates++; const r = await route.fetch(); await route.fulfill({status: 503, json: {message: 'QA lost response'}}); step('create status ' + r.status()); });
      try {
        await page.getByTestId('booking-next').click();
        await page.getByTestId('booking-date').fill(vnDay(3));
        await page.locator('[data-slot]:not([disabled])').first().click();
        await page.getByTestId('booking-next').click();
        await page.getByTestId('booking-submit').dblclick();
        await page.getByRole('heading', {name: 'Kiểm tra kết quả đặt lịch'}).waitFor();
        await page.screenshot({path: `${out}/j10-booking-lost-response-390.png`});
      } finally { await page.unroute('**/api/appointments/create'); }
      assert(creates === 1, 'J10 one create request despite double click, got ' + creates);
      await page.getByRole('button', {name: 'Kiểm tra lịch đã đặt', exact: true}).click();
      await page.getByTestId('booking-success').waitFor();
      const after = list(await myAppointments()).length;
      assert(after === before + 1, `J10 exactly one appointment stored (${before} -> ${after})`);
      checks.push('J10 booking: response dropped after commit -> one POST, recovery screen, "Kiểm tra lịch đã đặt" finds the booking, no duplicate');
    }
  } catch (e) { throw Error(e.message.split('\n')[0] + ' | trace: ' + trace.slice(-6).join(' ; ')); }
  return {checks, trace};
}
