/* One printable receipt renderer for both billing sources. */
(() => {
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const money = value => new Intl.NumberFormat('vi-VN', {style: 'currency', currency: 'VND'}).format(Number(value));
    const date = value => value ? new Date(value).toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh'}) : 'Chưa có thông tin';
    function render(transaction) {
        const packageSale = transaction.transaction_type === 'package';
        const line = (label, value) => `<p><span>${label}:</span> ${esc(value)}</p>`;
        return `<article class="billing-receipt">
            <header><h2>BIN SPA</h2><h3>PHIẾU THANH TOÁN ${packageSale ? 'GÓI DỊCH VỤ' : 'DỊCH VỤ'}</h3></header>
            ${line('Mã phiếu', transaction.code)}${line('Khách hàng', transaction.customer_name)}
            ${line('SĐT', transaction.customer_phone || 'Chưa có thông tin')}
            ${transaction.appointment_id ? line('Mã lịch hẹn', '#' + transaction.appointment_id) : ''}
            ${packageSale ? `<h4>${esc(transaction.package_name)}</h4>` : '<h4>Dịch vụ</h4>'}
            <ul class="receipt-items">${(transaction.items || []).map(item => `<li>${esc(item.name)} ${packageSale
                ? `· ${esc(item.sessions)} buổi` : `× ${esc(item.quantity)} <span>${money(item.total)}</span>`}</li>`).join('') || '<li>Chưa có chi tiết</li>'}</ul>
            ${packageSale ? line('Hiệu lực', transaction.validity_months == null ? 'Vô thời hạn' : `${transaction.validity_months} tháng từ khi kích hoạt`) : ''}
            <p class="receipt-total">Tổng tiền: <strong>${money(transaction.total_amount)}</strong></p>
            ${line('Phương thức', transaction.payment_method || (transaction.status === 'Đã thanh toán' ? 'Chưa có thông tin' : 'Chưa chọn phương thức'))}${line('Trạng thái', transaction.status)}
            ${transaction.payment_method === 'Tiền mặt' && transaction.cash_received != null
                ? line('Khách đưa', money(transaction.cash_received)) + line('Tiền thối', money(transaction.change)) : ''}
            ${line('Ngày tạo', date(transaction.created_at))}
            ${line('Thanh toán', transaction.paid_at ? date(transaction.paid_at) : 'Chưa thanh toán')}
            ${line('Nhân viên / nguồn mua', transaction.source_label)}
            ${transaction.payment_reference ? line('Mã chuyển khoản', transaction.payment_reference) : ''}
        </article>`;
    }
    function print(transaction) {
        let area = document.getElementById('billingPrintArea');
        if (!area) { area = document.createElement('div'); area.id = 'billingPrintArea'; document.body.appendChild(area); }
        area.innerHTML = render(transaction);
        window.print();
    }
    function open(transaction) {
        let dialog = document.getElementById('sharedBillingReceipt');
        if (!dialog) {
            dialog = document.createElement('dialog');
            dialog.id = 'sharedBillingReceipt';
            dialog.className = 'billing-receipt-dialog';
            dialog.setAttribute('aria-label', 'Phiếu thanh toán');
            document.body.appendChild(dialog);
        }
        dialog.innerHTML = `<button class="receipt-close" data-close aria-label="Đóng">×</button>${render(transaction)}<div class="receipt-actions"><button class="btn btn-primary" data-print>In phiếu</button><button class="btn btn-secondary" data-close>Đóng</button></div>`;
        dialog.querySelectorAll('[data-close]').forEach(button => button.onclick = () => dialog.close());
        dialog.querySelector('[data-print]').onclick = () => print(transaction);
        if (!dialog.open) dialog.showModal();
    }
    window.BillingReceipt = {render, print, open, esc, money, date};
})();
