let allInvoices = [];
let currentPage = 1;
let currentUserRole = null;
let filterVersion = 0;
let detailVersion = 0;
const itemsPerPage = 10;
const byId = id => document.getElementById(id);

function getAuthHeaders(includeContentType = true) {
    const token = localStorage.getItem('admin_token') || localStorage.getItem('access_token');
    return {...(token ? {Authorization: `Bearer ${token}`} : {}), ...(includeContentType ? {'Content-Type': 'application/json'} : {})};
}
async function billingApi(url, body) {
    const response = await fetch(url, {headers: getAuthHeaders(Boolean(body)), cache: 'no-store',
        ...(body ? {method: 'POST', body: JSON.stringify(body)} : {})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.msg || data.message || 'Không thể tải dữ liệu');
    return data;
}
function showSuccess(message) { byId('billingMessage').textContent = message; }
function showError(message) { byId('billingMessage').textContent = message; }
function getDateRange(value) {
    const today = new Date();
    const format = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    if (value === 'today') return {start: format(today), end: format(today)};
    if (value === 'this_month') return {start: format(new Date(today.getFullYear(), today.getMonth(), 1)), end: format(new Date(today.getFullYear(), today.getMonth() + 1, 0))};
    return {};
}
async function applyFilters() {
    const version = ++filterVersion;
    const dates = getDateRange(byId('timeRangeFilter').value);
    const params = new URLSearchParams({type: byId('typeFilter').value, status: byId('statusFilter').value, search: byId('searchInput').value.trim()});
    if (dates.start) params.set('start_date', dates.start);
    if (dates.end) params.set('end_date', dates.end);
    try {
        const data = await billingApi(`/api/admin/billing/transactions?${params}`);
        if (version !== filterVersion) return;
        allInvoices = data.transactions;
        for (const key of ['total', 'paid', 'unpaid']) byId('stat-' + key).textContent = data.stats[key];
        byId('stat-revenue').textContent = BillingReceipt.money(data.stats.revenue);
        currentPage = 1;
        renderInvoicesTable();
    } catch (error) { if (version === filterVersion) showError(error.message); }
}
function loadInvoices() { return applyFilters(); }
function clearFilters() {
    for (const id of ['timeRangeFilter', 'statusFilter', 'typeFilter']) byId(id).value = 'all';
    byId('searchInput').value = '';
    byId('clear-search-btn').style.display = 'none';
    applyFilters();
}
function renderInvoicesTable() {
    const {esc, money, date} = BillingReceipt;
    const canPay = ['admin', 'manager', 'letan'].includes(currentUserRole);
    const rows = allInvoices.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);
    document.querySelector('#invoices-table tbody').innerHTML = rows.map(row => `<tr>
        <td><strong>${esc(row.code)}</strong></td><td>${esc(row.display_type_label)}</td>
        <td>${esc(row.customer_name)}<br><small>${esc(row.customer_phone)}</small></td>
        <td>${esc(row.transaction_type === 'package' ? row.package_name : row.appointment_id ? 'Lịch hẹn #' + row.appointment_id : 'Dịch vụ riêng')}</td>
        <td><strong>${money(row.payable_amount ?? row.total_amount)}</strong></td>
        <td><span class="badge badge-${row.status === 'Đã thanh toán' ? 'success' : 'danger'}">${esc(row.status)}</span></td>
        <td>${date(row.created_at)}</td>
        <td><button class="btn btn-info btn-sm" onclick="viewInvoiceDetail(${row.id}, '${row.transaction_type}')">Xem</button>
        ${row.can_pay && canPay ? `<button class="btn btn-success btn-sm" onclick="payBillingTransaction('${row.transaction_type}', ${row.id})">Thanh toán</button>` : ''}</td>
    </tr>`).join('') || '<tr><td colspan="8" class="text-center">Không tìm thấy giao dịch nào</td></tr>';
    const pages = Math.ceil(allInvoices.length / itemsPerPage);
    byId('pagination').innerHTML = pages > 1 ? `<button class="btn btn-secondary" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>Trước</button> <span>${currentPage} / ${pages}</span> <button class="btn btn-secondary" onclick="changePage(${currentPage + 1})" ${currentPage === pages ? 'disabled' : ''}>Sau</button>` : '';
}
function changePage(page) {
    if (page < 1 || page > Math.ceil(allInvoices.length / itemsPerPage)) return;
    currentPage = page;
    renderInvoicesTable();
}
async function viewInvoiceDetail(id, kind = 'service') {
    const version = ++detailVersion;
    const dialog = byId('invoiceDetailModal');
    byId('invoice-detail-content').textContent = 'Đang tải phiếu...';
    byId('receiptPay').hidden = true;
    byId('receiptPrint').disabled = true;
    if (!dialog.open) dialog.showModal();
    try {
        const {transaction} = await billingApi(`/api/admin/billing/transactions/${kind}/${id}`);
        if (version !== detailVersion || !dialog.open) return;
        byId('invoice-detail-content').innerHTML = BillingReceipt.render(transaction);
        byId('receiptPrint').disabled = false;
        byId('receiptPrint').onclick = () => BillingReceipt.print(transaction);
        byId('receiptPay').hidden = !transaction.can_pay || !['admin', 'manager', 'letan'].includes(currentUserRole);
        byId('receiptPay').onclick = () => { dialog.close(); payBillingTransaction(kind, id); };
    } catch (error) { if (version === detailVersion) byId('invoice-detail-content').textContent = error.message; }
}
async function payBillingTransaction(kind, id) {
    if (kind === 'service') { await openInvoicePayment(id); return; }
    try {
        const {purchase} = await billingApi(`/api/admin/package-sales/${id}`);
        if (purchase.status === 'paid') { showSuccess('Phiếu đã được thanh toán.'); await loadInvoices(); return; }
        if (purchase.status !== 'pending') throw new Error('Phiếu này không còn chờ thanh toán');
        if (purchase.payment_method !== 'cash' || Number(purchase.payable_amount ?? purchase.amount)===0) { await PackageCare.showPayment(purchase); return; }
        const dialog = byId('billingCashDialog');
        const payable = purchase.payable_amount ?? purchase.amount;
        byId('billingCashSummary').textContent = `${purchase.receipt_code} · ${purchase.customer_name} · ${BillingReceipt.money(payable)}`;
        const input = byId('billingCashReceived');
        input.min = payable;
        input.value = payable;
        const change = () => { byId('billingCashChange').textContent = 'Tiền thối: ' + BillingReceipt.money(Math.max(0, Number(input.value) - Number(payable))); };
        input.oninput = change;
        change();
        byId('billingCashForm').onsubmit = async event => {
            event.preventDefault();
            const button = byId('billingCashConfirm');
            button.disabled = true;
            try {
                await billingApi(`/api/admin/packages/purchases/${id}/confirm-payment`, {cash_received: input.value});
                dialog.close();
                showSuccess('Đã thanh toán gói dịch vụ.');
                await loadInvoices();
                await viewInvoiceDetail(id, 'package');
            } catch (error) { showError(error.message); }
            finally { button.disabled = false; }
        };
        dialog.querySelector('.loyalty-payment')?.remove();
        dialog.showModal();
        if(window.LoyaltyPayment) await LoyaltyPayment.mount(dialog,`/api/admin/packages/purchases/${id}`,purchase.makh,async()=>{dialog.close();await payBillingTransaction(kind,id);});
    } catch (error) { showError(error.message); }
}
document.addEventListener('DOMContentLoaded', () => {
    currentUserRole = localStorage.getItem('admin_role');
    let timer;
    byId('searchInput').oninput = () => {
        byId('clear-search-btn').style.display = byId('searchInput').value ? 'flex' : 'none';
        clearTimeout(timer);
        timer = setTimeout(applyFilters, 250);
    };
    loadInvoices();
});
document.addEventListener('invoice-payment-updated', loadInvoices);
document.addEventListener('package:paid', loadInvoices);
