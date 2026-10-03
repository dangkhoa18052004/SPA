/* Shared invoice payment UI; invoice identity and status always come from the API. */
(() => {
    let generation = 0;
    let timer = null;
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const money = value => Number(value).toLocaleString('vi-VN') + 'đ';
    async function request(id, suffix = '', body) {
        const response = await fetch(`/api/admin/invoices/${id}${suffix}`, {
            method: body ? 'POST' : 'GET', headers: getAuthHeaders(Boolean(body)),
            ...(body ? {body: JSON.stringify(body)} : {}), cache: 'no-store'
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.msg || 'Không thể tải hóa đơn');
        return data;
    }
    function refresh() {
        document.dispatchEvent(new CustomEvent('invoice-payment-updated'));
    }
    function close() {
        generation++;
        clearTimeout(timer);
        timer = null;
        document.getElementById('sharedInvoicePayment')?.remove();
        refresh();
    }
    function render(invoice, content) {
        document.getElementById('sharedInvoicePayment')?.remove();
        const modal = document.createElement('div');
        modal.id = 'sharedInvoicePayment';
        modal.className = 'modal show';
        modal.style.cssText = 'display:grid;place-items:center;z-index:10000';
        modal.innerHTML = `<div class="modal-content" style="max-width:560px;max-height:90vh;overflow:auto">
            <div class="modal-header"><h3>HÓA ĐƠN #HD${String(invoice.mahd).padStart(6, '0')}</h3><button class="close" data-close>&times;</button></div>
            <div class="modal-body"><p>Khách hàng: ${escape(invoice.khachhang_hoten)}</p><p>Tổng tiền: <strong>${money(invoice.tongtien)}</strong></p><p>Trạng thái: ${escape(invoice.trangthai)}</p>${content}</div>
            <div class="modal-footer"><button class="btn btn-secondary" data-close>Đóng</button></div></div>`;
        modal.querySelectorAll('[data-close]').forEach(button => button.onclick = close);
        modal.onclick = event => { if (event.target === modal) close(); };
        document.body.appendChild(modal);
        return modal;
    }
    async function openInvoicePayment(id) {
        close();
        const token = generation;
        try {
            const invoice = await request(id);
            if (token !== generation) return;
            if (invoice.trangthai === 'Đã thanh toán') {
                showSuccess('Hóa đơn đã được thanh toán.');
                refresh();
                return;
            }
            const modal = render(invoice, '<p>Chọn phương thức:</p><button class="btn btn-success" data-cash>Tiền mặt</button> <button class="btn btn-primary" data-qr>Chuyển khoản VietQR</button>');
            modal.querySelector('[data-cash]').onclick = () => openCashPayment(invoice);
            modal.querySelector('[data-qr]').onclick = () => generateVietQrCode(invoice);
        } catch (error) { if (token === generation) showError(error.message); }
    }
    function openCashPayment(invoice) {
        const modal = render(invoice, `<form><label>Số tiền khách trả</label><input class="form-control" type="number" min="${Number(invoice.tongtien)}" step="1" required value="${Number(invoice.tongtien)}"><p data-change></p><button class="btn btn-success" type="submit">Xác nhận thanh toán</button></form>`);
        const input = modal.querySelector('input');
        input.oninput = () => { modal.querySelector('[data-change]').textContent = 'Tiền thừa: ' + money(Math.max(0, Number(input.value) - Number(invoice.tongtien))); };
        modal.querySelector('form').onsubmit = async event => {
            event.preventDefault();
            const button = modal.querySelector('[type=submit]');
            button.disabled = true;
            try {
                await request(invoice.mahd, '/record-payment', {sotien: input.value, phuongthuc: 'Tiền mặt'});
                if (modal.isConnected) close();
                else refresh();
                showSuccess('Đã ghi nhận thanh toán tiền mặt.');
            } catch (error) { showError(error.message); refresh(); }
            finally { button.disabled = false; }
        };
    }
    async function generateVietQrCode(invoice) {
        const token = generation;
        const modal = render(invoice, '<p>Đang tạo mã VietQR...</p>');
        try {
            const data = await request(invoice.mahd, '/generate-qr', {});
            if (token !== generation || !modal.isConnected) return;
            const content = document.createElement('div');
            content.innerHTML = `<p>Quét mã bằng ứng dụng ngân hàng</p><img alt="Mã VietQR" style="max-width:100%" src="${escape(data.qrCodeUrl)}"><p>Ngân hàng: ${escape(data.bank)}</p><p>Tài khoản: ${escape(data.accountNo)} — ${escape(data.accountName)}</p><p>Số tiền: ${money(data.amount)}</p><p>Nội dung: <strong>${escape(data.description)}</strong></p><p data-status>Đang chờ ngân hàng xác nhận...</p>`;
            modal.querySelector('.modal-body > p:last-child')?.remove();
            modal.querySelector('.modal-body').appendChild(content);
            const deadline = Date.now() + 300000;
            const poll = async () => {
                if (token !== generation || !modal.isConnected) return;
                try {
                    const latest = await request(invoice.mahd);
                    if (token !== generation || !modal.isConnected) return;
                    if (latest.trangthai === 'Đã thanh toán') {
                        close();
                        showSuccess('Thanh toán VietQR thành công!');
                        return;
                    }
                } catch (error) { /* Retry transient failures while the modal is open. */ }
                if (Date.now() < deadline) timer = setTimeout(poll, 3000);
                else content.querySelector('[data-status]').textContent = 'Chưa nhận được xác nhận. Bạn có thể đóng và tiếp tục thanh toán sau.';
            };
            timer = setTimeout(poll, 3000);
        } catch (error) { if (token === generation && modal.isConnected) { modal.querySelector('.modal-body').append(document.createTextNode(error.message)); showError(error.message); } }
    }
    window.openInvoicePayment = openInvoicePayment;
    window.openPaymentModal = openInvoicePayment;
    window.openPaymentSelectionModal = openInvoicePayment;
    window.generateVietQrCode = async id => {
        try { await generateVietQrCode(await request(id)); } catch (error) { showError(error.message); }
    };
    window.viewAppointmentInvoice = async id => {
        close();
        const token = generation;
        try {
            const response = await fetch(`/api/admin/billing/transactions/service/${id}`, {headers: getAuthHeaders(false), cache: 'no-store'});
            const data = await response.json();
            if (!response.ok) throw new Error(data.msg || 'Không thể tải hóa đơn');
            if (token !== generation) return;
            BillingReceipt.open(data.transaction);
        } catch (error) { showError(error.message); }
    };
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && document.getElementById('sharedInvoicePayment')) close(); });
})();
