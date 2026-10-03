const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function renderer() {
    let area, prints = 0;
    const context = {window: {print: () => prints++}, document: {
        getElementById: () => area, createElement: () => ({}), body: {appendChild: node => {area = node;}}
    }};
    vm.runInNewContext(fs.readFileSync('app/static/js/admin/invoice-receipt.js', 'utf8'), context);
    return {receipt: context.window.BillingReceipt, area: () => area, prints: () => prints};
}
const service = {transaction_type: 'service', code: 'HD000031', customer_name: 'Test', customer_phone: '0900000002',
    appointment_id: 56, total_amount: '300000', status: 'Đã thanh toán', payment_method: 'Tiền mặt',
    cash_received: '350000', change: '50000', items: [{name: 'Massage', quantity: 1, total: '300000'}],
    created_at: '2026-10-03T07:16:00+07:00', paid_at: '2026-10-03T08:16:00+07:00', source_label: 'Admin Test', payment_reference: 'HD31'};
const packageSale = {...service, transaction_type: 'package', code: 'PG000004', appointment_id: null,
    package_name: 'Combo 10 lần', validity_months: null, source_label: 'Khách mua online', payment_reference: 'PKG4',
    items: [{name: 'Chăm sóc da', sessions: 10}]};

test('service receipt is a plain slip with cash, change, dates and appointment', () => {
    const html = renderer().receipt.render(service);
    for (const text of ['BIN SPA', 'PHIẾU THANH TOÁN DỊCH VỤ', 'HD000031', '#56', 'Massage', 'Khách đưa', 'Tiền thối', 'Thanh toán', 'Admin Test']) assert.ok(html.includes(text));
    assert.ok(!html.includes('info-card'));
    assert.ok(!html.includes('Hiệu lực'));
});
test('package receipt shares layout and displays purchase snapshot and validity', () => {
    const receipt = renderer().receipt;
    const html = receipt.render(packageSale);
    for (const text of ['PHIẾU THANH TOÁN GÓI DỊCH VỤ', 'PG000004', 'Combo 10 lần', '10 buổi', 'Vô thời hạn', 'Khách mua online', 'PKG4']) assert.ok(html.includes(text));
    assert.ok(receipt.render({...packageSale, validity_months: 8}).includes('8 tháng'));
    assert.ok(!html.includes('Mã lịch hẹn'));
});
test('legacy unpaid receipts omit unavailable cash metadata and escape user text', () => {
    const html = renderer().receipt.render({...service, status: 'Chưa thanh toán', paid_at: null,
        cash_received: null, customer_name: '<img src=x onerror=alert(1)>'});
    assert.ok(html.includes('Chưa thanh toán'));
    assert.ok(html.includes('&lt;img'));
    assert.ok(!html.includes('<img'));
    assert.ok(!html.includes('Khách đưa'));
});
test('printing either type uses a standalone receipt without buttons', () => {
    const state = renderer();
    for (const data of [service, packageSale]) {
        state.receipt.print(data);
        assert.equal(state.area().id, 'billingPrintArea');
        assert.ok(state.area().innerHTML.includes(data.code));
        assert.ok(!state.area().innerHTML.includes('<button'));
    }
    assert.equal(state.prints(), 2);
    const css = fs.readFileSync('app/static/css/admin/invoice-receipt.css', 'utf8');
    assert.ok(css.includes('body > *:not(#billingPrintArea)'));
    assert.ok(css.includes('@media print'));
});
