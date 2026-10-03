const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const context = {window: {}, document: {addEventListener() {}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/static/js/admin/appointments.js', 'utf8'), context);
const row = (permissions, extra = {}) => ({malh: 56, permissions: {canView: true, ...permissions}, ...extra});
test('pending/confirmed/in-progress show separate authorized appointment actions', () => {
    assert.match(context.appointmentActions(row({canConfirm: true})), /Xác nhận/);
    assert.doesNotMatch(context.appointmentActions(row({canConfirm: true})), /Hoàn thành/);
    for (const state of ['confirmed', 'in_progress']) {
        const appointment = row({canComplete: true}, {trangthai: state});
        assert.match(context.appointmentActions(appointment), /Hoàn thành/);
        assert.equal(context.appointmentPaymentBadge(appointment), '—');
    }
});
test('completed actions progress from create to pay to receipt without changing appointment status', () => {
    const first = row({canCreateInvoice: true}, {trangthai: 'completed', payment_status: 'Chưa thanh toán'});
    assert.match(context.appointmentActions(first), /Tạo hóa đơn/);
    assert.doesNotMatch(context.appointmentActions(first), /Hoàn thành/);
    const invoice = {mahd: 31, trangthai: 'Chưa thanh toán'};
    const second = row({canPayInvoice: true}, {trangthai: 'completed', invoice, payment_status: 'Chưa thanh toán'});
    assert.match(context.appointmentActions(second), /Thanh toán hóa đơn/);
    assert.doesNotMatch(context.appointmentActions(second), /Tạo hóa đơn/);
    const paid = row({canViewInvoice: true}, {trangthai: 'completed', invoice: {...invoice, trangthai: 'Đã thanh toán'}, payment_status: 'Đã thanh toán'});
    assert.match(context.appointmentActions(paid), /Xem hóa đơn/);
    assert.doesNotMatch(context.appointmentActions(paid), /Thanh toán hóa đơn/);
    assert.match(context.appointmentPaymentBadge(paid), /Đã thanh toán/);
});
test('full package and cancelled appointments expose only view', () => {
    for (const state of ['completed', 'cancelled']) {
        const appointment = row({}, {trangthai: state, payment_status: state === 'completed' ? 'Đã thanh toán bằng gói' : null});
        assert.match(context.appointmentActions(appointment), />Xem</);
        assert.doesNotMatch(context.appointmentActions(appointment), /Tạo hóa đơn|Thanh toán hóa đơn|Hoàn thành/);
    }
});
test('staff completion is not gated by invoice/edit privileges', () => {
    vm.runInContext("currentUserRole = 'staff'", context);
    assert.match(context.appointmentActions(row({canComplete: true})), /Hoàn thành/);
    assert.doesNotMatch(context.appointmentActions(row({})), /Hoàn thành/);
});
