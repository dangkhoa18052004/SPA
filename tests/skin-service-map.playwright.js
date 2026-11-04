async page => {
    const errors = [], failedRequests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('requestfailed', r => failedRequests.push({url: r.url(), error: r.failure()?.errorText}));
    page.on('response', r => { if (r.status() >= 400) failedRequests.push({url: r.url(), status: r.status()}); });
    // Capture confirmation text and accept deterministically; CLI otherwise yields at a native modal.
    await page.addInitScript(() => {
        window.confirm = message => {
            const dialogs = JSON.parse(localStorage.getItem('skin_map_dialogs') || '[]');
            dialogs.push(message);
            localStorage.setItem('skin_map_dialogs', JSON.stringify(dialogs));
            return true;
        };
    });
    const assert = (value, message) => { if (!value) throw new Error(message); };
    try {
    await page.goto('http://127.0.0.1:5079/__preview/login');
    await page.evaluate(async () => {
        const login = await (await fetch('/__preview/login')).json();
        localStorage.setItem('admin_token', login.access_token);
        localStorage.setItem('admin_role', login.role);
        localStorage.setItem('admin_user', JSON.stringify({hoten: login.hoten}));
        localStorage.removeItem('skin_map_qa');
        localStorage.removeItem('skin_map_dialogs');
        const catalog = await (await fetch('/api/admin/skin-service-map', {headers: {Authorization: 'Bearer ' + login.access_token}})).json();
        await fetch('/api/admin/skin-service-map', {method: 'PUT',
            headers: {Authorization: 'Bearer ' + login.access_token, 'Content-Type': 'application/json'},
            body: JSON.stringify({map: {papule: [catalog.services[1].madv]}})});
    });
    await page.goto('http://127.0.0.1:5079/admin/skin-service-map');
    await page.locator('#skin-map-save').waitFor({state: 'visible'});
    await page.waitForFunction(() => !document.getElementById('skin-map-save').disabled);
    const getMap = () => page.evaluate(async () => (await fetch('/api/admin/skin-service-map', {headers: getAuthHeaders()})).json());
    const before = await getMap();
    assert(before.source === 'database', 'Initial source must be DB');
    await page.locator('#sidebar-menu a[href="/admin/skin-service-map"]').waitFor();
    assert(await page.locator('#sidebar-menu a[href="/admin/skin-service-map"]').count() === 1, 'Menu link missing');
    assert(await page.locator('#skin-map-groups fieldset').count() === 5, 'Need all five types');
    assert(await page.locator('#skin-map-groups img, #skin-map-groups script').count() === 0, 'DB HTML was injected');
    const proposalResponse = page.waitForResponse(r => r.url().endsWith('/skin-service-map/proposal') && r.request().method() === 'POST');
    await page.getByRole('button', {name: 'Nhờ Gemini đề xuất', exact: true}).click();
    assert((await proposalResponse).status() === 200, 'Proposal request failed');
    await page.waitForFunction(() => !document.getElementById('skin-map-draft').hidden);
    assert(JSON.stringify((await getMap()).map) === JSON.stringify(before.map), 'Proposal must not persist');
    const papule = page.locator('input[data-type="papule"]');
    assert(await papule.nth(0).isChecked(), 'Proposed service not checked');
    assert(!(await papule.nth(1).isChecked()), 'Removed service still checked');
    assert(await page.getByText('Thêm mới so với map đang dùng', {exact: true}).count() === 2, 'Missing additions');
    assert(await page.getByText('Bị bỏ so với map đang dùng', {exact: true}).count() === 1, 'Missing removal');
    assert(await page.getByText('Gemini đề xuất dựa trên tên và mô tả dịch vụ.', {exact: true}).count() === 1, 'Unsafe reason not replaced');
    await papule.nth(1).check();
    await page.getByRole('button', {name: 'Lưu và duyệt', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('skin-map-status').textContent === 'Đã lưu và duyệt map dịch vụ.');
    const firstDialog = await page.evaluate(() => JSON.parse(localStorage.skin_map_dialogs)[0]);
    assert(firstDialog.includes('Sẩn viêm: 2 dịch vụ') && firstDialog.includes('Mụn mủ: 0 dịch vụ'), 'Confirmation missing counts');
    await page.reload();
    await page.waitForFunction(() => !document.getElementById('skin-map-save').disabled);
    assert(await page.locator('input[data-type="papule"]:checked').count() === 2, 'Saved map did not survive reload');
    assert((await page.locator('#skin-map-approved').innerText()).includes('Admin Test'), 'Approver missing');
    await page.locator('#sidebar-menu a[href="/admin/skin-service-map"]').waitFor();
    await page.screenshot({path: '.playwright-cli/skin-map-desktop.png', fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(async () => {
        const elements = [document.querySelector('.admin-sidebar'), document.querySelector('.admin-main')];
        await Promise.all(elements.flatMap(el => el.getAnimations()).map(animation => animation.finished.catch(() => {})));
    });
    await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth);
    assert(await page.locator('.admin-main').evaluate(el => getComputedStyle(el).marginLeft === '0px'), 'Mobile content still offset');
    await page.screenshot({path: '.playwright-cli/skin-map-mobile.png', fullPage: true});
    while (await page.locator('#skin-map-groups input:checked').count()) {
        await page.locator('#skin-map-groups input:checked').first().uncheck();
    }
    await page.getByRole('button', {name: 'Lưu và duyệt', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('skin-map-source').textContent.includes('.env'));
    const dialogs = await page.evaluate(() => JSON.parse(localStorage.skin_map_dialogs));
    assert(dialogs[1].includes('sẽ quay về dùng SKIN_SERVICE_MAP trong .env'), 'Empty map confirmation missing');
    await page.reload();
    await page.waitForFunction(() => !document.getElementById('skin-map-save').disabled);
    assert(await page.locator('input[data-type="open_comedo"]:checked').count() === 1, 'Env fallback not rendered after reload');
    assert(errors.length === 0, 'Console/page errors: ' + JSON.stringify(errors));
    assert(failedRequests.length === 0, 'Failed requests: ' + JSON.stringify(failedRequests));
    const result = {passed: true, checks: ['DB source, approver, menu, five types', 'proposal stays draft', 'reasons and differences',
        'manual editing, confirmation counts, save and reload', 'empty save and env fallback', 'DB/Gemini HTML escaped',
        'desktop and mobile without overflow'], errors, failedRequests, dialogs};
    await page.evaluate(result => localStorage.setItem('skin_map_qa', JSON.stringify(result)), result);
    console.log(JSON.stringify(result));
    return result;
    } catch (error) {
        await page.evaluate(result => localStorage.setItem('skin_map_qa', JSON.stringify(result)),
            {passed: false, error: error.message, errors, failedRequests});
        throw error;
    }
}
