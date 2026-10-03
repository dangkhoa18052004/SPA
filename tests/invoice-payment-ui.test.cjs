const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(invoice, pendingQr = false) {
    const calls = [], notices = [], nodes = new Map();
    let resolveQr;
    class Element {
        constructor() { this.style = {}; this.children = []; this.parts = new Map(); this.isConnected = false; }
        appendChild(child) { child.isConnected = true; this.children.push(child); if (child.id) nodes.set(child.id, child); }
        append(child) { this.appendChild(child); }
        remove() { this.isConnected = false; nodes.delete(this.id); }
        querySelectorAll(selector) { return [this.querySelector(selector)]; }
        querySelector(selector) {
            if (!this.parts.has(selector)) this.parts.set(selector, new Element());
            return this.parts.get(selector);
        }
    }
    const document = {body: new Element(), createElement: () => new Element(),
        createTextNode: value => ({value}), getElementById: id => nodes.get(id),
        addEventListener() {}, dispatchEvent() {}};
    const context = {document, window: {}, CustomEvent: class {},
        getAuthHeaders: () => ({}), showError: m => notices.push(m), showSuccess: m => notices.push(m),
        setTimeout: () => 1, clearTimeout() {},
        fetch: async (url, options) => {
            calls.push({url, options});
            if (url.endsWith('/generate-qr')) {
                const result = {ok: true, json: async () => ({qrCodeUrl: 'https://example.test/qr.png', amount: 500000, description: 'HD12'})};
                if (pendingQr) return new Promise(resolve => {resolveQr = () => resolve(result);});
                return result;
            }
            if (url.endsWith('/record-payment')) { invoice.trangthai = 'Đã thanh toán'; return {ok: true, json: async () => ({})}; }
            return {ok: true, json: async () => ({...invoice})};
        }};
    vm.runInNewContext(fs.readFileSync('app/static/js/admin/invoice-payment.js', 'utf8'), context);
    return {context, calls, notices, nodes, resolveQr: () => resolveQr()};
}
const invoice = () => ({mahd: 12, tongtien: 500000, khachhang_hoten: 'Test', trangthai: 'Chưa thanh toán'});

test('closing and reloading preserves resume using the API invoice ID', async () => {
    const data = invoice();
    const first = setup(data);
    await first.context.window.openInvoicePayment(12);
    assert.match(first.nodes.get('sharedInvoicePayment').innerHTML, /Chuyển khoản VietQR/);
    first.nodes.get('sharedInvoicePayment').querySelector('[data-close]').onclick();
    assert.equal(first.nodes.size, 0);
    assert.equal(first.calls.filter(call => call.options.method === 'POST').length, 0);
    await first.context.window.openInvoicePayment(12);
    const reload = setup(data);
    await reload.context.window.openInvoicePayment(12);
    assert.ok(reload.nodes.has('sharedInvoicePayment'));
    assert.equal(reload.calls[0].url, '/api/admin/invoices/12');
});

test('a stale unpaid row cannot open payment choices for a paid invoice', async () => {
    const state = setup({...invoice(), trangthai: 'Đã thanh toán'});
    await state.context.window.openInvoicePayment(12);
    assert.equal(state.nodes.size, 0);
    assert.deepEqual(state.notices, ['Hóa đơn đã được thanh toán.']);
});

test('cash uses the existing invoice and closes after success', async () => {
    const state = setup(invoice());
    await state.context.window.openInvoicePayment(12);
    state.nodes.get('sharedInvoicePayment').querySelector('[data-cash]').onclick();
    const modal = state.nodes.get('sharedInvoicePayment');
    modal.querySelector('input').value = '600000';
    await modal.querySelector('form').onsubmit({preventDefault() {}});
    assert.equal(state.nodes.size, 0);
    assert.equal(state.calls[1].url, '/api/admin/invoices/12/record-payment');
    assert.equal(JSON.parse(state.calls[1].options.body).phuongthuc, 'Tiền mặt');
});

test('closing QR while the request is pending does not resurrect the modal', async () => {
    const state = setup(invoice(), true);
    await state.context.window.openInvoicePayment(12);
    const pending = state.nodes.get('sharedInvoicePayment').querySelector('[data-qr]').onclick();
    state.nodes.get('sharedInvoicePayment').querySelector('[data-close]').onclick();
    state.resolveQr();
    await pending;
    assert.equal(state.nodes.size, 0);
    assert.equal(state.calls[1].url, '/api/admin/invoices/12/generate-qr');
    assert.equal(state.calls.filter(call => call.url.includes('create-invoice')).length, 0);
});
