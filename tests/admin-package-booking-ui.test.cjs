const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
    const nodes = new Map(), errors = [], calls = [];
    const element = id => {
        if (!nodes.has(id)) nodes.set(id, {value: '', textContent: '', innerHTML: '', hidden: false,
            style: {}, classList: {add(){}, remove(){}}, reportValidity: () => true, querySelectorAll: () => []});
        return nodes.get(id);
    };
    const context = {window: {addEventListener(){}}, document: {addEventListener(){}, getElementById: element, querySelectorAll: () => [], querySelector: () => null},
        console, URLSearchParams, Map, Date, localStorage: {getItem: () => ''},
        fetch: async url => {calls.push(url); return {ok: true, json: async () => ({success: true, treatments: []})};}};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync('app/static/js/admin/appointments.js', 'utf8'), context);
    vm.runInContext(`loadAvailableStaff = () => {}; showError = message => __errors.push(message);
        allServices = [{madv: 3, tendv: 'Massage', thoiluong: 45}, {madv: 8, tendv: 'Gội đầu', thoiluong: 45}];`, context);
    context.__errors = errors;
    return {context, nodes, element, errors, calls, run: source => vm.runInContext(source, context)};
}

const treatments = [{mathe: 12, tengoi: '<script>package</script>', items: [
    {id: 41, madv: 3, tendv: 'Massage', source_type: 'package', usable: true, total_sessions: 10,
        consumed: 3, reserved: 1, available_sessions: 6, effective_expires_at: '2026-10-10T10:00'},
    {id: 42, madv: 3, tendv: 'Massage', source_type: 'gift', usable: true, total_sessions: 2,
        consumed: 0, reserved: 0, available_sessions: 2, effective_expires_at: null, gift_note: '<img onerror=bad>'},
    {id: 43, madv: 8, tendv: 'Gội đầu', source_type: 'package', usable: false, total_sessions: 2,
        consumed: 2, reserved: 0, available_sessions: 0}
]}];

function select(s) {
    s.run(`selectedCustomerId = 15; customerTreatments = ${JSON.stringify(treatments)};
        treatmentLoadState = 'ready'; setBookingServiceMethod('treatment'); togglePackageItem(12, 41);`);
}

test('exact sources are separate, remaining counts come from server and HTML is escaped', () => {
    const s = setup(); select(s);
    const html = s.element('booking-treatment-list').innerHTML;
    assert.match(html, /togglePackageItem\(12, 41\)/);
    assert.match(html, /togglePackageItem\(12, 42\)/);
    assert.match(html, /Còn 6\/10 buổi/);
    assert.match(html, /Trong gói/); assert.match(html, /Spa tặng/);
    assert.match(html, /Đã hết lượt/); assert.match(html, /disabled/);
    assert.ok(!html.includes('<script>') && !html.includes('<img onerror'));
    s.run('togglePackageItem(12, 42)');
    assert.equal(s.run('selectedPackageItems.get(3).item.id'), 42);
    assert.equal(s.run('selectedServiceIds.length'), 1);
    s.run('togglePackageItem(12, 43)');
    assert.equal(s.run('selectedPackageItems.size'), 1);
});

test('switching customer clears entitlements and covered services while keeping ordinary extras', () => {
    const s = setup(); select(s); s.run('selectedServiceIds.push(8); toggleCustomer(16, "B", "0900")');
    assert.equal(s.run('selectedPackageItems.size'), 0);
    assert.equal(s.run('customerTreatments.length'), 0);
    assert.equal(s.run('selectedServiceIds.join(",")'), '8');
    assert.equal(s.calls[0], '/api/admin/appointments/customers/16/treatments');
});

test('appointment date invalidates package, preserves independent unexpired gift and ordinary service', () => {
    const s = setup(); select(s); s.run('selectedServiceIds.push(8)');
    s.element('appointment-date').value = '2026-10-11'; s.run('bookingDateChanged()');
    assert.equal(s.run('selectedPackageItems.size'), 0);
    assert.equal(s.run('selectedServiceIds.join(",")'), '8');
    assert.match(s.errors[0], /không còn hiệu lực/);
    s.run('togglePackageItem(12, 42)');
    assert.equal(s.run('selectedPackageItems.get(3).item.id'), 42);
});

test('late customer response cannot overwrite newer customer entitlements', async () => {
    const s = setup(), pending = [];
    s.context.fetch = url => new Promise(resolve => pending.push({url, resolve}));
    s.run('selectedCustomerId = 15'); const first = s.context.loadCustomerTreatments();
    s.run('selectedCustomerId = 16; resetCustomerTreatments()'); const second = s.context.loadCustomerTreatments();
    pending[1].resolve({ok: true, json: async () => ({success: true, treatments: []})}); await second;
    pending[0].resolve({ok: true, json: async () => ({success: true, treatments})}); await first;
    assert.equal(s.run('customerTreatments.length'), 0);
});

test('submission sends mixed exact-item payload and refreshes server entitlements after sold-out error', async () => {
    const s = setup(); select(s);
    s.run('selectedServiceIds.push(8)');
    s.element('customer-id').value = '15'; s.element('appointment-date').value = '2026-10-10';
    s.element('appointment-time').value = '10:30'; s.element('staff-id').value = '5';
    const calls = [];
    s.context.fetch = async (url, options) => {
        calls.push({url, options});
        return url.endsWith('treatments')
            ? {ok: true, json: async () => ({success: true, treatments: [{...treatments[0], items: treatments[0].items.map(i => ({...i, available_sessions: 0}))}]})}
            : {ok: false, status: 400, json: async () => ({msg: 'Đã hết buổi khả dụng'})};
    };
    await s.context.handleAppointmentSubmit({preventDefault(){}});
    const body = JSON.parse(calls[0].options.body);
    assert.deepEqual(body.madv_list, [3, 8]);
    assert.deepEqual(body.package_usages, [{mathe: 12, the_item_id: 41, madv: 3, quantity: 1}]);
    assert.equal(calls[1].url, '/api/admin/appointments/customers/15/treatments');
    assert.equal(s.run('selectedPackageItems.size'), 0);
    assert.equal(s.run('selectedServiceIds.join(",")'), '8');
    assert.ok(s.errors.includes('Đã hết buổi khả dụng'));
    assert.equal(s.element('appointment-save').disabled, false);
});
