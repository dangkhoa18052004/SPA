// ========================================
// HELPER FUNCTIONS
// ========================================

function formatCurrency(amount) {
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(amount);
}

function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getAuthHeaders(includeContentType = true) {
    const token = localStorage.getItem('admin_token');
    if (!token) {
        console.warn('⚠️ No token found in localStorage, redirecting to login...');
        window.location.href = '/admin/login';
    }
    const headers = {
        'Authorization': `Bearer ${token}`
    };
    
    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
    }
    
    return headers;
}

// ========================================
// MODAL HELPERS
// ========================================

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'grid';
        modal.style.placeItems = 'center';
        
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
        
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }, 300);
    }
}

// ========================================
// GLOBAL VARIABLES
// ========================================

let allInvoices = [];
let filteredInvoices = [];
const itemsPerPage = 10;
let currentPage = 1;
let currentUserRole = null;
let currentInvoiceId = null;

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    currentUserRole = localStorage.getItem('admin_role') || 'admin'; 
    loadInvoices(); // Sẽ gọi applyFilters()
    setupModalEventListeners();
    setupSearchInput(); 
});

// ========================================
// SETUP EVENT LISTENERS
// ========================================

function setupModalEventListeners() {
    document.querySelectorAll('.close, .close-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) closeModal(modal.id);
        });
    });
    
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal(this.id);
            }
        });
    });
}

function setupSearchInput() {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clear-search-btn');
    
    if (searchInput && clearBtn) {
        searchInput.addEventListener('input', function() {
            if (this.value.trim()) {
                clearBtn.style.display = 'flex';
            } else {
                clearBtn.style.display = 'none';
            }
            // Gọi applyFilters khi người dùng gõ
            applyFilters();
        });
    }
}

// ========================================
// DATE RANGE CALCULATION
// ========================================

function getDateRange(timeRange) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let startDate = null;
    let endDate = null;

    if (timeRange === 'today') {
        startDate = new Date(today);
        endDate = new Date(today);
    } else if (timeRange === 'this_month') {
        startDate = new Date(today.getFullYear(), today.getMonth(), 1);
        endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0); 
    }
    // 'all' (Tổng toàn bộ) thì startDate/endDate là null
    
    // Hàm format ngày thành chuỗi YYYY-MM-DD
    const formatDate = (d) => {
        if (!d) return null;
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };
    
    return {
        start: formatDate(startDate),
        end: formatDate(endDate)
    };
}


// ========================================
// LOAD INVOICES & FILTER (GỬI API)
// ========================================

async function loadInvoices() {
    // Khởi tạo tải dữ liệu với bộ lọc mặc định ('all' và 'all')
    applyFilters(); 
}

async function applyFilters() {
    // 1. Lấy giá trị từ bộ lọc
    const timeRangeFilter = document.getElementById('timeRangeFilter').value;
    const statusFilter = document.getElementById('statusFilter').value;
    const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
    
    // 2. Tính toán ngày tháng
    const dateRange = getDateRange(timeRangeFilter);
    
    // 3. Xây dựng tham số query
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);
    
    if (statusFilter !== 'all') params.append('status', statusFilter);
    if (searchTerm) params.append('search', searchTerm);
    
    const url = `/api/admin/invoices?${params.toString()}`;
    
    try {
        const response = await fetch(url, {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        allInvoices = data.invoices || [];
        
        // Cập nhật thống kê từ data.stats
        const stats = data.stats;
        
        const statTotal = document.getElementById('stat-total');
        const statPaid = document.getElementById('stat-paid');
        const statUnpaid = document.getElementById('stat-unpaid');
        const statRevenue = document.getElementById('stat-revenue');
        
        if (statTotal) statTotal.textContent = stats.total || 0;
        if (statPaid) statPaid.textContent = stats.paid || 0;
        if (statUnpaid) statUnpaid.textContent = stats.unpaid || 0;
        if (statRevenue) statRevenue.textContent = formatCurrency(stats.revenue || 0);

        // Cập nhật bảng
        filteredInvoices = [...allInvoices]; 
        currentPage = 1;
        renderInvoicesTable();
        renderPagination();
        
    } catch (error) {
        console.error('❌ Lỗi tải hóa đơn:', error);
        showError('Không thể tải danh sách hóa đơn: ' + error.message);
        
        const tbody = document.querySelector('#invoices-table tbody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center" style="color: #ef4444;">
                        <i class="fas fa-exclamation-triangle"></i> ${error.message}
                    </td>
                </tr>
            `;
        }
    }
}


function clearFilters() {
    // Reset UI
    document.getElementById('timeRangeFilter').value = 'all'; 
    document.getElementById('statusFilter').value = 'all';
    document.getElementById('searchInput').value = '';
    
    // Hide clear button
    const clearBtn = document.getElementById('clear-search-btn');
    if (clearBtn) clearBtn.style.display = 'none';
    
    console.log('🔄 Filters cleared');
    
    // Gọi API để tải lại toàn bộ dữ liệu (tương đương với 'all')
    applyFilters();
}

// ========================================
// RENDER TABLE
// ========================================

function renderInvoicesTable() {
    const tbody = document.querySelector('#invoices-table tbody');
    
    if (!tbody) {
        console.error('❌ Không tìm thấy tbody');
        return;
    }
    
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedData = filteredInvoices.slice(startIndex, startIndex + itemsPerPage);

    if (paginatedData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center" style="padding: 40px; color: #999;">
                    <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
                    <p style="font-size: 16px;">Không tìm thấy hóa đơn nào</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = paginatedData.map(invoice => {
        const isPaid = invoice.trangthai === 'Đã thanh toán';
        const canPayment = ['admin', 'manager', 'letan'].includes(currentUserRole);
        
        return `
            <tr>
                <td><strong>#${invoice.mahd}</strong></td>
                <td>#${invoice.malh || 'N/A'}</td>
                <td>${invoice.khachhang_hoten || 'N/A'}</td>
                <td><strong>${formatCurrency(invoice.tongtien)}</strong></td>
                <td>
                    <span class="badge badge-${isPaid ? 'success' : 'danger'}">
                        ${invoice.trangthai}
                    </span>
                </td>
                <td>${formatDateTime(invoice.ngaytao)}</td>
                <td>
                    <button class="btn btn-info btn-sm" 
                            onclick="viewInvoiceDetail(${invoice.mahd})" 
                            title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${!isPaid && canPayment ? `
                        <button class="btn btn-success btn-sm" 
                                onclick="openPaymentModal(${invoice.mahd})" 
                                title="Thanh toán">
                            <i class="fas fa-money-bill-wave"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

// ========================================
// PAGINATION
// ========================================

function renderPagination() {
    const totalPages = Math.ceil(filteredInvoices.length / itemsPerPage);
    const paginationDiv = document.getElementById('pagination');
    
    if (!paginationDiv || totalPages <= 1) {
        if (paginationDiv) paginationDiv.innerHTML = '';
        return;
    }
    
    let html = '<div style="display: flex; gap: 8px; justify-content: center; margin-top: 20px;">';
    
    // Previous button
    html += `
        <button class="btn btn-sm btn-secondary" 
                onclick="changePage(${currentPage - 1})" 
                ${currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-chevron-left"></i>
        </button>
    `;
    
    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `
                <button class="btn btn-sm ${i === currentPage ? 'btn-primary' : 'btn-secondary'}" 
                        onclick="changePage(${i})">
                    ${i}
                </button>
            `;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span style="padding: 5px;">...</span>';
        }
    }
    
    // Next button
    html += `
        <button class="btn btn-sm btn-secondary" 
                onclick="changePage(${currentPage + 1})" 
                ${currentPage === totalPages ? 'disabled' : ''}>
            <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    html += '</div>';
    paginationDiv.innerHTML = html;
}

function changePage(page) {
    const totalPages = Math.ceil(filteredInvoices.length / itemsPerPage);
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    renderInvoicesTable();
    renderPagination();
}

// ========================================
// VIEW INVOICE DETAIL
// ========================================

async function viewInvoiceDetail(invoiceId) {
    try {
        openModal('invoiceDetailModal');
        
        const contentDiv = document.getElementById('invoice-detail-content');
        contentDiv.innerHTML = `
            <div class="text-center" style="padding: 40px;">
                <div class="spinner-border mb-3"></div>
                <p>Đang tải chi tiết hóa đơn...</p>
            </div>
        `;
        
        const response = await fetch(`/api/admin/invoices/${invoiceId}`, {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            throw new Error('Không thể tải chi tiết hóa đơn');
        }
        
        const invoice = await response.json();
        
        const detailHtml = `
            <div class="info-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h6>MÃ HÓA ĐƠN</h6>
                        <h3>#${invoice.mahd}</h3>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge badge-${invoice.trangthai === 'Đã thanh toán' ? 'success' : 'danger'}" 
                              style="font-size: 14px;">
                            ${invoice.trangthai}
                        </span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h4><i class="fas fa-user-circle"></i> Thông tin khách hàng</h4>
                <p><strong>Họ tên:</strong> <span>${invoice.khachhang_hoten || 'N/A'}</span></p>
                <p><strong>Mã lịch hẹn:</strong> <span>#${invoice.malh || 'N/A'}</span></p>
                <p><strong>Ngày lập:</strong> <span>${formatDateTime(invoice.ngaytao)}</span></p>
            </div>
            
            ${invoice.chitiet && invoice.chitiet.length > 0 ? `
                <div class="detail-section">
                    <h4><i class="fas fa-receipt"></i> Chi tiết dịch vụ</h4>
                    <table class="invoice-table">
                        <thead>
                            <tr>
                                <th>Dịch vụ</th>
                                <th style="text-align: center;">SL</th>
                                <th style="text-align: right;">Đơn giá</th>
                                <th style="text-align: right;">Thành tiền</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${invoice.chitiet.map(item => `
                                <tr>
                                    <td>${item.tendv || 'N/A'}</td>
                                    <td style="text-align: center;">${item.soluong || 1}</td>
                                    <td style="text-align: right;">${formatCurrency(item.dongia)}</td>
                                    <td style="text-align: right;">
                                        <strong>${formatCurrency(item.thanhtien)}</strong>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            ` : `
                <p style="text-align: center; color: #999; padding: 20px;">
                    <i class="fas fa-info-circle"></i> Không có chi tiết dịch vụ
                </p>
            `}
            
            <div class="invoice-total">
                <h5>
                    <i class="fas fa-coins"></i> 
                    Tổng cộng: <strong>${formatCurrency(invoice.tongtien)}</strong>
                </h5>
            </div>
        `;
        
        contentDiv.innerHTML = detailHtml;
        
    } catch (error) {
        console.error('❌ Lỗi:', error);
        document.getElementById('invoice-detail-content').innerHTML = `
            <div class="alert alert-danger" style="text-align: center;">
                <i class="fas fa-exclamation-triangle"></i>
                ${error.message}
            </div>
        `;
    }
}

// ========================================
// PAYMENT MODAL
// ========================================

function openPaymentModal(invoiceId) {
    currentInvoiceId = invoiceId;
    
    const invoice = allInvoices.find(inv => inv.mahd === invoiceId);
    if (!invoice) {
        showError('Không tìm thấy hóa đơn');
        return;
    }
    
    const modalHtml = `
        <div id="paymentModal" class="modal show" style="display: grid !important; place-items: center;">
            <div class="modal-content modal-sm">
                <div class="modal-header" style="padding: 15px 25px;">
                    <h3 style="margin:0; font-size: 18px;"><i class="fas fa-credit-card"></i> Thanh toán hóa đơn</h3>
                    <button class="close" onclick="closePaymentModal()">&times;</button>
                </div>
                <div class="modal-body" style="padding: 20px 25px;">
                    <div class="info-card" style="text-align: center; margin-bottom: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                        <h6 style="color: #666; margin-bottom: 5px;">TỔNG TIỀN CẦN THANH TOÁN</h6>
                        <h3 style="color: #10b981; font-size: 24px;">${formatCurrency(invoice.tongtien)}</h3>
                    </div>
                    
                    <h5 style="text-align: center; margin: 15px 0 20px 0; color: #333; font-weight: 600;">
                        Chọn phương thức thanh toán:
                    </h5>
                    
                    <div class="payment-options" style="display: flex; gap: 15px; justify-content: center;">
                        
                        <div class="payment-option cash" 
                             onclick="openCashPaymentModal(${invoiceId}, ${invoice.tongtien})">
                            <i class="fas fa-money-bill-wave"></i>
                            <h4>Tiền mặt</h4>
                            <p>Nhận tiền trực tiếp</p>
                        </div>
                        
                        <div class="payment-option qr" 
                             onclick="generateMomoQrCode(${invoiceId})">
                            <i class="fas fa-qrcode"></i>
                            <h4>QR Code</h4>
                            <p>Quét mã Momo</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const oldModal = document.getElementById('paymentModal');
    if (oldModal) oldModal.remove();
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    document.body.style.overflow = 'hidden';
    
    const modal = document.getElementById('paymentModal');
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            closePaymentModal();
        }
    });
}

function closePaymentModal() {
    const modal = document.getElementById('paymentModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
            document.body.style.overflow = 'auto';
        }, 300);
    }
}

// ========================================
// CASH PAYMENT
// ========================================

async function recordCashPayment(invoiceId) {
    closePaymentModal();
    
    const invoice = allInvoices.find(inv => inv.mahd === invoiceId);
    if (!invoice) {
        showError('Không tìm thấy hóa đơn');
        return;
    }
    
    const sotien = prompt(`Tổng tiền: ${formatCurrency(invoice.tongtien)}\n\nNhập số tiền khách trả:`);
    
    if (sotien === null) return;
    
    const amount = parseFloat(sotien);
    if (isNaN(amount) || amount < parseFloat(invoice.tongtien)) {
        showError('Số tiền không hợp lệ hoặc không đủ!');
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/invoices/${invoiceId}/record-payment`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                sotien: amount, 
                phuongthuc: 'Tiền mặt' 
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            const change = amount - parseFloat(invoice.tongtien);
            
            if (change > 0) {
                showSuccess(`Thanh toán thành công!\nTiền thừa: ${formatCurrency(change)}`);
            } else {
                showSuccess('Thanh toán thành công!');
            }
            
            setTimeout(() => {
                location.reload();
            }, 1500);
            
        } else {
            showError(data.msg || 'Ghi nhận thanh toán thất bại');
        }

    } catch (error) {
        console.error('❌ Lỗi:', error);
        showError('Có lỗi xảy ra khi ghi nhận tiền mặt');
    }
}

function openCashPaymentModal(invoiceId, totalAmount) {
    closePaymentModal(); 
    
    const totalAmountFloat = parseFloat(totalAmount);
    
    const cashModalHtml = `
        <div id="cashPaymentModal" class="modal show" style="display: grid !important; place-items: center;">
            <div class="modal-content modal-sm">
                <div class="modal-header" style="padding: 15px 25px;">
                    <h3><i class="fas fa-money-bill-wave"></i> Thanh toán tiền mặt</h3>
                    <button class="close" onclick="closeModal('cashPaymentModal')">&times;</button>
                </div>
                <div class="modal-body" style="padding: 20px 25px;">
                    <div style="text-align: center; margin-bottom: 20px; padding: 15px; background: #f0fdf4; border-radius: 8px;">
                        <h6 style="color: #10b981; margin-bottom: 5px;">TỔNG TIỀN PHẢI THU</h6>
                        <h3 id="cash-total-display" style="color: #10b981; font-size: 24px;">${formatCurrency(totalAmount)}</h3>
                    </div>
                    
                    <form id="cashPaymentForm" onsubmit="event.preventDefault(); handleCashPaymentSubmit(${invoiceId}, ${totalAmount});">
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label for="amountPaid" style="font-weight: 600;">Số tiền khách trả (*)</label>
                            <input type="number" id="amountPaid" class="form-control" 
                                   placeholder="Nhập số tiền..." required min="${totalAmountFloat}">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 25px;">
                            <label for="changeAmount" style="font-weight: 600;">Tiền thối lại</label>
                            <input type="text" id="changeAmount" class="form-control" readonly 
                                   value="${formatCurrency(0)}" style="background: #f3f4f6; color: #e11d48; font-weight: bold;">
                        </div>
                        
                        <div class="btn-group" style="display: flex; justify-content: flex-end; gap: 10px;">
                            <button type="button" class="btn btn-secondary" onclick="closeModal('cashPaymentModal')">Hủy</button>
                            <button type="submit" class="btn btn-primary" id="confirmCashBtn">
                                <i class="fas fa-check"></i> Xác nhận
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', cashModalHtml);
    openModal('cashPaymentModal');
    
    const inputPaid = document.getElementById('amountPaid');
    const inputChange = document.getElementById('changeAmount');
    
    inputPaid.addEventListener('input', function() {
        const paid = parseFloat(this.value);
        if (isNaN(paid) || paid < totalAmountFloat) {
            inputChange.value = formatCurrency(0);
            document.getElementById('confirmCashBtn').disabled = true;
            return;
        }
        const change = paid - totalAmountFloat;
        inputChange.value = formatCurrency(change);
        document.getElementById('confirmCashBtn').disabled = false;
    });
    
    document.getElementById('confirmCashBtn').disabled = true; 
}

// ========================================
// XỬ LÝ SUBMIT TIỀN MẶT
// ========================================

async function handleCashPaymentSubmit(invoiceId, totalAmount) {
    const amountPaid = document.getElementById('amountPaid').value;
    const amountPaidFloat = parseFloat(amountPaid);
    
    if (amountPaidFloat < parseFloat(totalAmount)) {
        showError('Số tiền khách trả không đủ!');
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/invoices/${invoiceId}/record-payment`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                sotien: amountPaidFloat, 
                phuongthuc: 'Tiền mặt' 
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            const change = amountPaidFloat - parseFloat(totalAmount);
            
            showSuccess(`Thanh toán thành công! Tiền thối: ${formatCurrency(change)}`);
            closeModal('cashPaymentModal');
            
            setTimeout(() => {
                location.reload();
            }, 1500);
            
        } else {
            showError(data.msg || 'Ghi nhận thanh toán thất bại');
        }

    } catch (error) {
        console.error('❌ Lỗi:', error);
        showError('Có lỗi xảy ra khi ghi nhận tiền mặt');
    }
}
// ========================================
// MOMO QR PAYMENT
// ========================================

async function ensureQRCodeLoaded() {
    if (typeof QRCode !== 'undefined') return true;
    return new Promise((resolve) => {
        const localScript = document.createElement('script');
        localScript.src = '/static/js/admin/qrcode.min.js';
        localScript.onload = () => resolve(typeof QRCode !== 'undefined');
        localScript.onerror = () => {
            const cdnScript = document.createElement('script');
            cdnScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
            cdnScript.onload = () => resolve(typeof QRCode !== 'undefined');
            cdnScript.onerror = () => resolve(false);
            document.head.appendChild(cdnScript);
        };
        document.head.appendChild(localScript);
    });
}

async function generateMomoQrCode(invoiceId) {
    closePaymentModal();
    
    const qrModalHtml = `
        <div id="qrCodeModal" class="modal show" style="display: grid !important; place-items: center;">
            <div class="modal-content modal-sm">
                <div class="modal-header" style="background: linear-gradient(135deg, #005baa, #0088ff); color: white; border-radius: 8px 8px 0 0;">
                    <h3 style="margin: 0; color: white;"><i class="fas fa-qrcode"></i> Thanh toán VietQR (Techcombank)</h3>
                    <button class="close" onclick="closeQRModal()" style="color: white; opacity: 0.9;">&times;</button>
                </div>
                <div class="modal-body" style="text-align: center;">
                    <div id="qr-code-container">
                        <div class="text-center">
                            <div class="spinner-border mb-3"></div>
                            <p>Đang tạo mã VietQR...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const oldQRModal = document.getElementById('qrCodeModal');
    if (oldQRModal) oldQRModal.remove();
    
    document.body.insertAdjacentHTML('beforeend', qrModalHtml);
    document.body.style.overflow = 'hidden';
    
    const modal = document.getElementById('qrCodeModal');
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            closeQRModal();
        }
    });
    
    try {
        const response = await fetch(`/api/admin/invoices/${invoiceId}/generate-qr`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (response.ok && data.qrCodeUrl) {
            const qrContainer = document.getElementById('qr-code-container');
            qrContainer.innerHTML = '';
            
            if (data.qrCodeUrl.startsWith('http://') || data.qrCodeUrl.startsWith('https://')) {
                const img = document.createElement('img');
                img.src = data.qrCodeUrl;
                img.alt = 'Mã QR VietQR';
                img.style.maxWidth = '260px';
                img.style.width = '100%';
                img.style.borderRadius = '8px';
                img.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                img.style.margin = '10px auto';
                qrContainer.appendChild(img);
            } else {
                const qrDiv = document.createElement('div');
                qrDiv.id = `qrcode-canvas-${invoiceId}`;
                qrDiv.style.margin = '20px auto';
                qrContainer.appendChild(qrDiv);
                
                const qrLoaded = await ensureQRCodeLoaded();
                if (qrLoaded && typeof QRCode !== 'undefined') {
                    new QRCode(qrDiv, {
                        text: data.qrCodeUrl,
                        width: 250,
                        height: 250,
                        colorDark: "#000000",
                        colorLight: "#ffffff",
                        correctLevel: QRCode.CorrectLevel.H
                    });
                }
            }
            
            qrContainer.insertAdjacentHTML('beforeend', `
                <div class="bank-info-box" style="background: #f8fafc; padding: 12px; border-radius: 8px; margin-top: 12px; text-align: left; font-size: 13px; border: 1px solid #e2e8f0;">
                    <p style="margin: 3px 0;"><strong>Chủ tài khoản:</strong> ${data.account_name || data.accountName || 'DANG VAN KHOA'}</p>
                    <p style="margin: 3px 0;"><strong>Số tài khoản:</strong> <span style="color: #005baa; font-weight: bold;">${data.account_no || data.accountNo || '0387829152'}</span> (${data.bank_id || data.bank || 'MB Bank'})</p>
                    <p style="margin: 3px 0;"><strong>Nội dung ck:</strong> <span style="color: #d97706; font-weight: bold;">${data.description || ('HD' + invoiceId)}</span></p>
                </div>
                <div class="qr-instructions" style="text-align: left; margin-top: 15px; border-top: 1px solid #eee; padding-top: 12px; font-size: 13px;">
                    <p style="margin-bottom: 5px; font-weight: 600;">
                        <i class="fas fa-mobile-alt" style="color: #005baa; width: 20px;"></i> 
                        <strong>Bước 1:</strong> Mở App Ngân hàng bất kỳ
                    </p>
                    <p style="margin-bottom: 5px; font-weight: 600;">
                        <i class="fas fa-qrcode" style="color: #005baa; width: 20px;"></i> 
                        <strong>Bước 2:</strong> Quét mã VietQR ở trên
                    </p>
                    <p style="margin-bottom: 5px; font-weight: 600;">
                        <i class="fas fa-check-circle" style="color: #005baa; width: 20px;"></i> 
                        <strong>Bước 3:</strong> Chờ SePay tự động khớp lệnh
                    </p>
                </div>
                <div id="payment-status" style="text-align: center; margin-top: 15px; font-weight: 600; color: #005baa;">
                    <i class="fas fa-spinner fa-spin"></i> Đang chờ tự động nhận tiền...
                </div>
            `);
            
            showSuccess("Mã QR đã được tạo thành công!");
            startPaymentPolling(invoiceId);
            
        } else {
            throw new Error(data.msg || 'Không thể tạo mã QR');
        }

    } catch (error) {
        console.error('❌ Lỗi:', error);
        document.getElementById('qr-code-container').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-times-circle"></i> ${error.message || 'Lỗi kết nối'}
            </div>
        `;
        showError(error.message || 'Không thể tạo mã QR');
    }
}

function closeQRModal() {
    const modal = document.getElementById('qrCodeModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
            document.body.style.overflow = 'auto';
        }, 300);
    }
    
    if (window.paymentPollingInterval) {
        clearInterval(window.paymentPollingInterval);
        window.paymentPollingInterval = null;
    }
}

// ========================================
// PAYMENT POLLING
// ========================================

let pollingAttempts = 0;
const MAX_POLLING_ATTEMPTS = 60;

async function startPaymentPolling(invoiceId) {
    pollingAttempts = 0;
    
    window.paymentPollingInterval = setInterval(async () => {
        pollingAttempts++;
        
        try {
            const response = await fetch(`/api/admin/invoices/${invoiceId}`, {
                headers: getAuthHeaders(false)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.trangthai === 'Đã thanh toán') {
                    clearInterval(window.paymentPollingInterval);
                    
                    const statusDiv = document.getElementById('payment-status');
                    if (statusDiv) {
                        statusDiv.innerHTML = `
                            <i class="fas fa-check-circle" style="color: #10b981; font-size: 28px;"></i> 
                            <p style="color: #10b981; font-weight: bold; margin-top: 10px; font-size: 16px;">
                                Thanh toán thành công!
                            </p>
                        `;
                    }
                    
                    showSuccess('Thanh toán thành công!');
                    
                    setTimeout(() => {
                        closeQRModal();
                        location.reload();
                    }, 2000);
                }
            }
            
            if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
                clearInterval(window.paymentPollingInterval);
                
                const statusDiv = document.getElementById('payment-status');
                if (statusDiv) {
                    statusDiv.innerHTML = `
                        <i class="fas fa-clock" style="color: #f59e0b; font-size: 24px;"></i> 
                        <p style="color: #f59e0b;">
                            Quá thời gian chờ. Vui lòng kiểm tra lại hoặc liên hệ hỗ trợ.
                        </p>
                    `;
                }
            }
            
        } catch (error) {
            console.error('❌ Lỗi polling:', error);
        }
        
    }, 3000);
}

// ========================================
// TOAST NOTIFICATIONS
// ========================================

function showToast(message, type = 'success') {
    let toastContainer = document.getElementById('toast-container');
    
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 99999;';
        document.body.appendChild(toastContainer);
    }
    
    const toast = document.createElement('div');
    const bgColor = type === 'success' ? '#10b981' : '#ef4444';
    
    toast.style.cssText = `
        background: ${bgColor};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 300px;
        animation: slideIn 0.3s ease;
        font-size: 14px;
    `;
    
    const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `
        <i class="fas ${icon}" style="font-size: 18px;"></i> 
        <span>${message}</span>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}

function exportInvoices() {
    showError('Chức năng xuất Excel đang được phát triển');
}