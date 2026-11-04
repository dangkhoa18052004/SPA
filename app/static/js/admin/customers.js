// ====== BIẾN GLOBAL ======
let allCustomers = [];
let currentPage = 1;
const itemsPerPage = 10;
let customerModal = null;
let quickAddModal = null;
let confirmModal = null; // Modal xác nhận
let confirmCallback = null; // Callback khi người dùng xác nhận

// ====== UTILITY FUNCTIONS (Thông báo Toast) ======
/**
 * Hiển thị thông báo trượt (toast)
 * @param {string} message - Nội dung thông báo
 * @param {string} type - Loại thông báo ('success' hoặc 'error')
 */
function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        alert((type === 'success' ? '✅ ' : '❌ ') + message); // Fallback
        console.error('Không tìm thấy #toast-container!');
        return;
    }

    const toast = document.createElement('div');
    // Dùng class trong file admin.css của bạn (.toast-success, .toast-error)
    toast.className = `toast toast-${type}`; 

    const iconClass = type === 'success' ? 'fas fa-check-circle' : 'fas fa-times-circle';
    toast.innerHTML = `<i class="${iconClass}"></i> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    
    // Tự động xóa sau 3 giây (dùng animation 'fade-out' từ CSS)
    setTimeout(() => {
        toast.classList.add('fade-out');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, 3000);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}

// ====== MODAL XÁC NHẬN ======
/**
 * Hiển thị modal xác nhận với callback
 * @param {string} message - Thông báo xác nhận
 * @param {function} callback - Hàm callback khi người dùng xác nhận
 */
function showConfirmModal(message, callback) {
    if (!confirmModal) {
        console.error('Modal xác nhận chưa được khởi tạo!');
        // Fallback về confirm() cũ
        if (confirm(message)) {
            callback();
        }
        return;
    }
    
    document.getElementById('confirmMessage').textContent = message;
    confirmCallback = callback;
    confirmModal.show();
}

// (Các hàm utility khác: escapeHtml, getAuthHeaders, getStatusText, getStatusBadgeClass)
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return 'N/A';
    return unsafe.toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'})[m]);
}
function getAuthHeaders(isJson = true) {
    const headers = {};
    if (isJson) headers['Content-Type'] = 'application/json';
    const token = localStorage.getItem('admin_token');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    } else {
        console.error('Không tìm thấy admin_token!');
    }
    return headers;
}
function getStatusText(status) {
    const map = {'active':'Hoạt động', 'pending':'Chờ xác thực', 'blocked':'Đã khóa'};
    return map[status] || status;
}
function getStatusBadgeClass(status) {
    const map = {'active':'success', 'pending':'secondary', 'blocked':'danger'};
    return map[status] || 'secondary';
}


// ====== HÀM PHÂN QUYỀN GIAO DIỆN ======
function setupRoleBasedUI() {
    const userRole = localStorage.getItem('admin_role');
    const fullAddButton = document.getElementById('add-customer-btn');
    const quickAddButton = document.getElementById('quick-add-btn');

    if (!userRole) {
        console.error('Không tìm thấy role, các nút thêm sẽ bị ẩn.');
        return; 
    }

    if (fullAddButton && userRole === 'admin') {
        fullAddButton.style.display = 'inline-flex'; 
    }
    const quickAddRoles = ['admin', 'manager', 'letan'];
    if (quickAddButton && quickAddRoles.includes(userRole)) {
        quickAddButton.style.display = 'inline-flex';
    }
}

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Khởi tạo customers page...');
    setupRoleBasedUI();

    // Khởi tạo Modal (Đầy đủ)
    const modalElement = document.getElementById('customerModal');
    if (modalElement) {
        try {
            customerModal = new bootstrap.Modal(modalElement);
            modalElement.addEventListener('hidden.bs.modal', resetModalForm);
            modalElement.querySelectorAll('.close, [data-dismiss="modal"]')
                .forEach(btn => btn.addEventListener('click', () => closeModal()));
        } catch (e) { console.error('❌ Lỗi khởi tạo modal (Đầy đủ):', e); }
    } else { console.error('❌ Không tìm thấy #customerModal'); }

    // Khởi tạo Modal (Thêm nhanh)
    const quickModalElement = document.getElementById('quickAddModal');
    if (quickModalElement) {
        try {
            quickAddModal = new bootstrap.Modal(quickModalElement);
            quickModalElement.addEventListener('hidden.bs.modal', () => {
                document.getElementById('quick-customer-form').reset();
            });
            quickModalElement.querySelectorAll('.close, [data-dismiss="modal"]')
                .forEach(btn => btn.addEventListener('click', () => quickAddModal.hide()));
        } catch (e) { console.error('❌ Lỗi khởi tạo modal (Thêm nhanh):', e); }
    } else { console.error('❌ Không tìm thấy #quickAddModal'); }

    // Khởi tạo Modal Xác nhận
    const confirmModalElement = document.getElementById('confirmModal');
    if (confirmModalElement) {
        try {
            confirmModal = new bootstrap.Modal(confirmModalElement);
            
            // Xử lý nút xác nhận
            document.getElementById('confirmActionBtn')?.addEventListener('click', () => {
                if (confirmCallback) {
                    confirmCallback();
                    confirmCallback = null;
                }
                confirmModal.hide();
            });
            
            // Xử lý nút hủy và nút đóng
            confirmModalElement.querySelectorAll('.close, [data-dismiss="modal"]')
                .forEach(btn => btn.addEventListener('click', () => {
                    confirmCallback = null;
                    confirmModal.hide();
                }));
                
        } catch (e) { console.error('❌ Lỗi khởi tạo modal xác nhận:', e); }
    } else { console.error('❌ Không tìm thấy #confirmModal'); }

    // Gán sự kiện cho các nút Thêm
    document.getElementById('add-customer-btn')?.addEventListener('click', openAddModal);
    document.getElementById('quick-add-btn')?.addEventListener('click', openQuickAddModal);
    document.getElementById('save-button')?.addEventListener('click', handleSaveCustomer);
    document.getElementById('save-quick-customer-btn')?.addEventListener('click', handleSaveQuickCustomer);
    
    // Gán sự kiện cho Filter và Search
    const searchInput = document.getElementById('customer-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    const statusFilter = document.getElementById('status-filter');

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
            currentPage = 1; 
            renderCustomersTable();
            renderPagination();
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearSearchBtn.style.display = 'none';
            currentPage = 1;
            renderCustomersTable();
            renderPagination();
        });
    }

    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            currentPage = 1;
            renderCustomersTable();
            renderPagination();
        });
    }

    // Tải dữ liệu ban đầu
    loadCustomers();
});

// ====== XỬ LÝ ESC KEY (Đóng cả 2 modal) ======
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        if (quickAddModal) quickAddModal.hide();
        if (customerModal) closeModal();
    }
});

// ====== TẢI DANH SÁCH KHÁCH HÀNG ======
async function loadCustomers() {
    try {
        showLoading(true);
        const response = await fetch('/api/admin/customers/list', { headers: getAuthHeaders(false) });
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        
        allCustomers = await response.json();
        
        // Debug: Kiểm tra dữ liệu ảnh đại diện
        console.log('📸 Kiểm tra ảnh đại diện của khách hàng:');
        allCustomers.forEach(customer => {
            if (customer.anhdaidien) {
                console.log(`KH #${customer.makh} - ${customer.hoten}: anhdaidien = "${customer.anhdaidien}"`);
            }
        });
        
        document.getElementById('total-customers-stat').textContent = allCustomers.length;
        
        renderCustomersTable();
        renderPagination();
    } catch (error) {
        console.error('❌ Lỗi tải khách hàng:', error);
        showError('Không thể tải danh sách khách hàng: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// ====== HÀM LỌC DỮ LIỆU (TỐI ƯU HÓA) ======
function getFilteredData() {
    const searchTerm = document.getElementById('customer-search-input').value.trim().toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;

    let filtered = allCustomers;

    // 1. Lọc theo Status
    if (statusFilter !== 'all') {
        filtered = filtered.filter(customer => customer.trangthai === statusFilter);
    }

    // 2. Lọc theo Search Term
    if (searchTerm) {
        filtered = filtered.filter(customer => 
            (customer.hoten || '').toLowerCase().includes(searchTerm) ||
            (customer.sdt || '').toLowerCase().includes(searchTerm) ||
            (customer.email || '').toLowerCase().includes(searchTerm)
        );
    }

    return filtered;
}

// ====== RENDER BẢNG DỮ LIỆU ======
function renderCustomersTable() {
    const tbody = document.querySelector('#customers-table tbody');
    if (!tbody) return;
    
    const filteredData = getFilteredData();
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageData = filteredData.slice(start, end);

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center">Không tìm thấy khách hàng nào</td></tr>`;
        return;
    }
    
    tbody.innerHTML = pageData.map(customer => {
        const isBlocked = customer.trangthai === 'blocked';
        let avatarHtml = '';
        
        if (customer.anhdaidien) {
            const imageSrc = `/api/profile/avatar/${customer.anhdaidien}`;
            
            avatarHtml = `<img src="${imageSrc}" alt="Avatar" class="table-avatar" onerror="this.onerror=null;this.src='/static/img/user-default.png';">`;
        } else {
            avatarHtml = `<div class="table-avatar-icon"><i class="fas fa-user"></i></div>`;
        }
        
        const userRole = localStorage.getItem('admin_role');
        const canDelete = userRole === 'admin'; 
        
        return `
        <tr>
            <td>#${customer.makh}</td>
            <td > 
                ${avatarHtml}
            </td>
            <td>${escapeHtml(customer.hoten || 'N/A')}</td>
            <td>${escapeHtml(customer.sdt || 'N/A')}</td>
            <td>${escapeHtml(customer.email || 'N/A')}</td>
            <td><span class="badge badge-${getStatusBadgeClass(customer.trangthai)}">${getStatusText(customer.trangthai)}</span></td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-info btn-sm" data-action="view" data-id="${customer.makh}" title="Xem chi tiết"><i class="fas fa-eye"></i></button>
                    ${['admin', 'manager', 'letan'].includes(userRole) ? `<button class="btn btn-primary btn-sm" data-action="gift" data-id="${customer.makh}" ${customer.trangthai === 'active' ? '' : 'disabled'} title="${customer.trangthai === 'active' ? 'Tặng voucher cho khách' : 'Chỉ tặng voucher cho khách đang hoạt động'}"><i class="fas fa-gift" aria-hidden="true"></i> Tặng voucher</button>` : ''}
                    <button class="btn btn-warning btn-sm" data-action="edit" data-id="${customer.makh}" title="Chỉnh sửa"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-primary btn-sm" data-action="appointments" data-id="${customer.makh}" title="Xem lịch hẹn"><i class="fas fa-calendar-alt"></i></button>
                    <button class="btn btn-danger btn-sm" data-action="block" data-id="${customer.makh}" data-state="${customer.trangthai}" title="${isBlocked ? 'Mở khóa' : 'Khóa'}">
                        <i class="fas ${isBlocked ? 'fa-lock-open' : 'fa-lock'}"></i>
                    </button>
                    ${canDelete ? `<button class="btn btn-danger btn-sm d-none" data-action="delete" data-id="${customer.makh}" title="Xóa"><i class="fas fa-trash"></i></button>` : ''}
                </div>
            </td>
        </tr>
    `;
    }).join('');
    
    attachActionButtonEvents();
}

// ====== EVENT DELEGATION ======
function attachActionButtonEvents() {
    const tbody = document.querySelector('#customers-table tbody');
    if (!tbody) return;
    tbody.removeEventListener('click', handleActionClick); // Xóa listener cũ
    tbody.addEventListener('click', handleActionClick); // Gắn listener mới
}

function handleActionClick(e) {
    const button = e.target.closest('button[data-action]');
    if (!button) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const action = button.dataset.action;
    const id = parseInt(button.dataset.id);
    const state = button.dataset.state;
    
    switch(action) {
        case 'view': viewCustomerDetail(id); break;
        case 'gift': viewCustomerDetail(id, true); break;
        case 'edit': openEditModal(id); break;
        case 'appointments': viewCustomerAppointments(id); break;
        case 'block': toggleBlockCustomer(id, state); break;
        // case 'delete': deleteCustomer(id); break; // Thêm case xóa
        default: console.warn('Hành động không xác định:', action);
    }
}

// ====== XÓA KHÁCH HÀNG (SỬ DỤNG MODAL XÁC NHẬN) ======
// async function deleteCustomer(makh) {
//     // Sử dụng modal xác nhận thay vì confirm()
//     showConfirmModal(`Bạn có chắc muốn xóa khách hàng #${makh} không?`, async () => {
//         try {
//             const response = await fetch(`/api/admin/customers/delete/${makh}`, {
//                 method: 'DELETE',
//                 headers: getAuthHeaders(false)
//             });
//             const result = await response.json();
//             if (!response.ok) throw new Error(result.msg || `Lỗi HTTP ${response.status}`);

//             showSuccess(result.msg || 'Xóa khách hàng thành công!');
//             loadCustomers();
//         } catch (error) {
//             console.error(`❌ Lỗi xóa khách hàng:`, error);
//             showError(error.message || 'Không thể xóa khách hàng');
//         }
//     });
// }

// ====== PHÂN TRANG ======
function renderPagination() {
    const paginationDiv = document.getElementById('pagination');
    if (!paginationDiv) return;
    
    const filteredData = getFilteredData();
    const totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    if (totalPages <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // Nút Previous
    html += `<button class="page-btn ${currentPage === 1 ? 'disabled' : ''}" 
             onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''} aria-label="Trang trước">
             <i class="fas fa-chevron-left"></i>
             </button>`;
    
    // Nút số trang (tối đa 5 nút)
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" 
                 onclick="changePage(${i})">${i}</button>`;
    }
    
    // Nút Next
    html += `<button class="page-btn ${currentPage === totalPages ? 'disabled' : ''}" 
             onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''} aria-label="Trang sau">
             <i class="fas fa-chevron-right"></i>
             </button>`;
    
    paginationDiv.innerHTML = html;
}

function changePage(page) {
    const filteredData = getFilteredData();
    const totalPages = Math.ceil(filteredData.length / itemsPerPage);
    
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    renderCustomersTable();
    renderPagination();
    
    // Scroll to top
    document.querySelector('.data-table-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ====== CÁC HÀM MODAL ======
function resetModalForm() {
    const voucherGifts = document.getElementById('customer-voucher-gifts');
    if (voucherGifts) { voucherGifts.hidden = true; voucherGifts.replaceChildren(); }
    document.getElementById('customer-form').reset();
    document.getElementById('customer-id').value = '';
    document.getElementById('detail-view-container').style.display = 'none';
    document.getElementById('form-edit-container').style.display = 'none';
}

function closeModal() {
    if (customerModal) {
        customerModal.hide();
    }
}

async function viewCustomerDetail(makh, openGift = false) {
    try {
        const customer = await loadCustomerDetails(makh);
        if (!customer) return showError('Không tìm thấy thông tin khách hàng');
        document.getElementById('customerModalLabel').innerText = 'Chi tiết khách hàng';
        
        let avatarHtml = '';
        if (customer.anhdaidien) {
            const imageSrc = `/api/profile/avatar/${customer.anhdaidien}`;
            avatarHtml = `<img src="${imageSrc}" alt="Avatar" class="detail-avatar" onerror="this.onerror=null;this.src='/static/img/user-default.png';">`;
        } else {
            avatarHtml = `<div class="detail-avatar-icon"><i class="fas fa-user"></i></div>`;
        }
        
        const content = `
            <div class="detail-avatar-container text-center">${avatarHtml}</div>
            <div class="detail-item"><label>Mã KH:</label> <span>#${customer.makh}</span></div>
            <div class="detail-item"><label>Họ tên:</label> <span>${escapeHtml(customer.hoten || 'N/A')}</span></div>
            <div class="detail-item"><label>SĐT:</label> <span>${escapeHtml(customer.sdt || 'N/A')}</span></div>
            <div class="detail-item"><label>Email:</label> <span>${escapeHtml(customer.email || 'N/A')}</span></div>
            <div class="detail-item"><label>Tài khoản:</label> <span>${escapeHtml(customer.taikhoan || 'N/A')}</span></div>
            <div class="detail-item"><label>Địa chỉ:</label> <span>${escapeHtml(customer.diachi || 'N/A')}</span></div>
            <div class="detail-item"><label>Ngày tạo:</label> <span>${customer.ngaytao ? new Date(customer.ngaytao).toLocaleDateString('vi-VN') : 'N/A'}</span></div>
            <div class="detail-item"><label>Trạng thái:</label> <span class="badge badge-${getStatusBadgeClass(customer.trangthai)}">${getStatusText(customer.trangthai)}</span></div>
        `;
        
        document.getElementById('detail-view-container').innerHTML = content;
        const voucherGifts = document.getElementById('customer-voucher-gifts');
        voucherGifts.hidden = false;
        const giftPanel = window.AdminVoucherGifts?.mount(voucherGifts, customer);
        document.getElementById('form-edit-container').style.display = 'none';
        document.getElementById('detail-view-container').style.display = 'grid';
        document.getElementById('save-button').style.display = 'none';
        
        if (openGift && customer.trangthai === 'active' && giftPanel) {
            document.getElementById('customerModal').addEventListener('shown.bs.modal', () => giftPanel.openGift(), { once: true });
        }
        customerModal.show();
    } catch (error) {
        console.error('❌ Lỗi xem chi tiết:', error);
        showError('Không thể tải chi tiết khách hàng: ' + error.message);
    }
}

function openAddModal() {
    document.getElementById('customerModalLabel').innerText = 'Thêm khách hàng mới';
    resetModalForm(); 
    
    const matkhauField = document.getElementById('matkhau');
    matkhauField.previousElementSibling.innerHTML = 'Mật khẩu <span class="text-danger">*</span>';
    matkhauField.nextElementSibling.style.display = 'none';
    matkhauField.required = true;

    document.getElementById('form-edit-container').style.display = 'grid';
    document.getElementById('detail-view-container').style.display = 'none';
    document.getElementById('save-button').style.display = 'block';
    
    customerModal.show();
}

async function openEditModal(makh) {
    try {
        const customer = await loadCustomerDetails(makh);
        if (!customer) return showError('Không tìm thấy thông tin khách hàng');

        document.getElementById('customerModalLabel').innerText = 'Chỉnh sửa khách hàng';
        resetModalForm();
        
        document.getElementById('customer-id').value = customer.makh;
        document.getElementById('hoten').value = customer.hoten || '';
        document.getElementById('sdt').value = customer.sdt || '';
        document.getElementById('email').value = customer.email || '';
        document.getElementById('taikhoan').value = customer.taikhoan || '';
        document.getElementById('diachi').value = customer.diachi || '';
        document.getElementById('trangthai').value = customer.trangthai || 'active';
        
        const matkhauField = document.getElementById('matkhau');
        matkhauField.previousElementSibling.innerText = 'Mật khẩu mới';
        matkhauField.nextElementSibling.style.display = 'block';
        matkhauField.required = false;

        document.getElementById('form-edit-container').style.display = 'grid';
        document.getElementById('detail-view-container').style.display = 'none';
        document.getElementById('save-button').style.display = 'block';

        customerModal.show();
    } catch (error) {
        console.error('❌ Lỗi mở modal sửa:', error);
        showError('Không thể tải thông tin khách hàng');
    }
}

async function handleSaveCustomer() {
    const makh = document.getElementById('customer-id').value;
    const isEditing = !!makh;
    
    const data = {
        hoten: document.getElementById('hoten').value.trim(),
        sdt: document.getElementById('sdt').value.trim(),
        email: document.getElementById('email').value.trim() || null, // Gửi null nếu rỗng
        taikhoan: document.getElementById('taikhoan').value.trim(),
        diachi: document.getElementById('diachi').value.trim(),
        trangthai: document.getElementById('trangthai').value,
        matkhau: document.getElementById('matkhau').value
    };

    if (!data.hoten || !data.sdt || !data.taikhoan) {
        return showError("Họ tên, SĐT, và Tên tài khoản là bắt buộc.");
    }
    if (!isEditing && !data.matkhau) {
        return showError("Mật khẩu là bắt buộc khi thêm mới.");
    }

    const url = isEditing ? `/api/admin/customers/edit/${makh}` : '/api/admin/customers/add';
    const method = isEditing ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method: method,
            headers: getAuthHeaders(true),
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.msg || `Lỗi HTTP ${response.status}`);
        
        showSuccess(result.msg);
        closeModal();
        loadCustomers();
    } catch (error) {
        console.error('❌ Lỗi lưu khách hàng:', error);
        showError(error.message);
    }
}

// ====== MODAL THÊM NHANH ======
function openQuickAddModal() {
    console.log('➕ Mở modal thêm nhanh khách vãng lai');
    document.getElementById('quick-customer-form').reset();
    if (quickAddModal) quickAddModal.show();
}

async function handleSaveQuickCustomer() {
    const hoten = document.getElementById('hoten-quick').value.trim();
    const sdt = document.getElementById('sdt-quick').value.trim();

    if (!hoten || !sdt) {
        return showError("Vui lòng nhập cả Họ tên và Số điện thoại.");
    }

    const data = { hoten, sdt };

    try {
        const response = await fetch('/api/admin/customers/add-quick', {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.msg || `Lỗi HTTP ${response.status}`);
        
        showSuccess(result.msg); 
        if (quickAddModal) quickAddModal.hide();
        loadCustomers(); 
    } catch (error) {
        console.error('❌ Lỗi thêm nhanh khách hàng:', error);
        showError(error.message);
    }
}

// ====== CÁC HÀNH ĐỘNG KHÁC ======
async function toggleBlockCustomer(makh, currentState) {
    const action = currentState === 'blocked' ? 'active' : 'blocked';
    const actionText = currentState === 'blocked' ? 'mở khóa' : 'khóa';
    
    // Sử dụng modal xác nhận thay vì confirm()
    showConfirmModal(`Bạn có chắc muốn ${actionText} khách hàng #${makh} không?`, async () => {
        try {
            const response = await fetch(`/api/admin/customers/update-status/${makh}`, {
                method: 'PATCH',
                headers: getAuthHeaders(true),
                body: JSON.stringify({ trangthai: action })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.msg || `Lỗi HTTP ${response.status}`);

            showSuccess(result.msg);
            loadCustomers();
        } catch (error) {
            console.error(`❌ Lỗi ${actionText} khách hàng:`, error);
            showError(error.message);
        }
    });
}

async function loadCustomerDetails(makh) {
    let customer = allCustomers.find(c => c.makh == makh);
    if (customer && customer.diachi !== undefined && customer.anhdaidien !== undefined) {
        console.log('✅ Tìm thấy trong cache (đầy đủ)');
        return customer;
    }

    try {
        console.log('🌐 Gọi API để lấy chi tiết');
        const response = await fetch(`/api/admin/customers/detail/${makh}`, {
            headers: getAuthHeaders(false)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const customerDetail = await response.json();
        
        const index = allCustomers.findIndex(c => c.makh == makh);
        if (index > -1) {
            allCustomers[index] = { ...allCustomers[index], ...customerDetail };
            return allCustomers[index];
        }
        return customerDetail;
    } catch (error) {
        console.error('❌ Lỗi tải chi tiết:', error);
        throw error;
    }
}

function viewCustomerAppointments(makh) {
    console.log('📅 Chuyển đến trang lịch hẹn của khách:', makh);
    window.location.href = `/admin/appointments?makh=${makh}`;
}

function showLoading(show) {
    const tbody = document.querySelector('#customers-table tbody');
    if (!tbody) return;
    if (show) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center">Đang tải dữ liệu...</td></tr>`;
    }
}

console.log('✅ customers.js đã load xong');
