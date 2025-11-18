// ==================== AUTH HELPER ====================
function getAuthToken() {
    return localStorage.getItem('access_token');
}

function getAuthHeaders(includeContentType = true) {
    const token = getAuthToken();
    const headers = {};

    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
        headers['Accept'] = 'application/json';
    }
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', function() {
    checkLoginStatus();
    loadUserProfile();
    loadUserAppointments();
    initMenuLinks();
    initAvatarUpload();
    initForms();
    
    if (window.location.hash === '#appointments') {
        switchSection('appointments');
    }
});

// ==================== CHECK LOGIN ====================
function checkLoginStatus() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/auth/login?redirect=/profile';
    }
}

// ==================== LOAD USER PROFILE ====================
async function loadUserProfile() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/auth/login?redirect=/profile';
        return;
    }

    try {
        const response = await fetch('/api/profile', {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            localStorage.removeItem('access_token');
            window.location.href = '/auth/login?redirect=/profile';
            return;
        }
        
        const data = await response.json();
        
        if (data.success && data.user) {
            displayUserInfo(data.user);
        } else {
            localStorage.removeItem('access_token');
            window.location.href = '/auth/login?redirect=/profile';
        }
    } catch (error) {
        console.error('Error loading profile:', error);
        localStorage.removeItem('access_token');
        window.location.href = '/auth/login';
    }
}

// ==================== DISPLAY USER INFO ====================
function displayUserInfo(user) {
    document.getElementById('userName').textContent = user.hoten;
    document.getElementById('userEmail').textContent = user.email;
    
    // Avatar
    if (user.anhdaidien) {
        document.getElementById('avatarImg').src = `/api/profile/avatar/${user.anhdaidien}`;
    }
    
    // Info section
    document.getElementById('infoHoten').textContent = user.hoten;
    document.getElementById('infoEmail').textContent = user.email;
    document.getElementById('infoSdt').textContent = user.sdt || 'Chưa cập nhật';
    document.getElementById('infoDiachi').textContent = user.diachi || 'Chưa cập nhật';
    
    // Edit form
    document.getElementById('editHoten').value = user.hoten;
    document.getElementById('editSdt').value = user.sdt || '';
    document.getElementById('editDiachi').value = user.diachi || '';
}

// ==================== MENU NAVIGATION ====================
function initMenuLinks() {
    const menuLinks = document.querySelectorAll('.menu-link');
    
    menuLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            menuLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            const sectionName = this.getAttribute('data-section');
            switchSection(sectionName);
        });
    });
}

function switchSection(sectionName) {
    document.querySelectorAll('.profile-section').forEach(section => {
        section.classList.remove('active');
    });
    
    document.getElementById(`${sectionName}-section`).classList.add('active');
    
    document.querySelectorAll('.menu-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-section') === sectionName) {
            link.classList.add('active');
        }
    });
    
    // Load data khi chuyển section
    if (sectionName === 'appointments') {
        loadUserAppointments();
    } else if (sectionName === 'invoices') {
        loadUserInvoices();
    }
}

// ==================== AVATAR UPLOAD ====================
function initAvatarUpload() {
    const avatarInput = document.getElementById('avatarInput');
    
    avatarInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            showAlert('error', 'Vui lòng chọn file ảnh!');
            return;
        }
        
        if (file.size > 2 * 1024 * 1024) {
            showAlert('error', 'File ảnh không được vượt quá 2MB!');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('avatarImg').src = e.target.result;
        };
        reader.readAsDataURL(file);
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const token = getAuthToken();
            const response = await fetch('/api/profile/upload-avatar', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert('success', 'Cập nhật avatar thành công!');
            } else {
                showAlert('error', data.message || 'Upload avatar thất bại!');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showAlert('error', 'Có lỗi xảy ra khi upload!');
        }
    });
}

// ==================== FORM HANDLERS ====================
function initForms() {
    // Edit profile form
    const editForm = document.getElementById('editProfileForm');
    editForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            hoten: document.getElementById('editHoten').value,
            sdt: document.getElementById('editSdt').value,
            diachi: document.getElementById('editDiachi').value
        };
        
        try {
            const response = await fetch('/api/profile/update', {
                method: 'PUT',
                headers: getAuthHeaders(true),
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('success', 'Cập nhật thông tin thành công!');
                await loadUserProfile();
                setTimeout(() => switchSection('info'), 1500);
            } else {
                showAlert('error', result.message || 'Cập nhật thất bại!');
            }
        } catch (error) {
            console.error('Update error:', error);
            showAlert('error', 'Có lỗi xảy ra!');
        }
    });
    
    // Change password form
    const passwordForm = document.getElementById('changePasswordForm');
    passwordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const oldPassword = document.getElementById('oldPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (newPassword !== confirmPassword) {
            showAlert('error', 'Mật khẩu mới không khớp!');
            return;
        }
        
        try {
            const response = await fetch('/api/profile/change-password', {
                method: 'PUT',
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    matkhau_cu: oldPassword,
                    matkhau_moi: newPassword
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('success', 'Đổi mật khẩu thành công!');
                passwordForm.reset();
            } else {
                showAlert('error', result.message || 'Đổi mật khẩu thất bại!');
            }
        } catch (error) {
            console.error('Change password error:', error);
            showAlert('error', 'Có lỗi xảy ra!');
        }
    });
}

// ==================== LOAD APPOINTMENTS ====================
async function loadUserAppointments() {
    try {
        const response = await fetch('/api/appointments/my-appointments', {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load appointments');
        }
        
        const data = await response.json();
        
        if (data.success && data.appointments) {
            displayAppointments(data.appointments);
        } else {
            displayNoAppointments();
        }
    } catch (error) {
        console.error('Error loading appointments:', error);
        displayNoAppointments();
    }
}

function displayAppointments(appointments) {
    const list = document.getElementById('appointmentsList');
    
    if (appointments.length === 0) {
        displayNoAppointments();
        return;
    }
    
    list.innerHTML = appointments.map(apt => {
        // Xác định trạng thái hiển thị
        const statusMap = {
            'pending': { text: 'Chờ xác nhận', class: 'status-pending' },
            'confirmed': { text: 'Đã xác nhận', class: 'status-confirmed' },
            'completed': { text: 'Hoàn thành', class: 'status-completed' },
            'cancelled': { text: 'Đã hủy', class: 'status-cancelled' }
        };
        
        const status = statusMap[apt.trangthai] || { text: apt.trangthai, class: 'status-pending' };
        
        return `
            <li class="appointment-item">
                <div class="appointment-header">
                    <h3>${apt.dichvu || 'Dịch vụ'}</h3>
                    <span class="appointment-status ${status.class}">
                        ${status.text}
                    </span>
                </div>
                <div class="appointment-details">
                    <p><i class="fas fa-calendar"></i> ${formatDate(apt.ngaygio)}</p>
                    <p><i class="fas fa-user"></i> ${apt.nhanvien || 'Chưa phân công'}</p>
                    ${apt.ghichu ? `<p><i class="fas fa-sticky-note"></i> ${apt.ghichu}</p>` : ''}
                </div>
                <div class="appointment-actions" style="margin-top: 15px; display: flex; gap: 10px;">
                    ${apt.trangthai === 'confirmed' || apt.trangthai === 'pending' ? `
                        <button class="btn btn-outline" style="padding: 8px 15px; font-size: 14px;" onclick="cancelAppointment(${apt.malh})">
                            <i class="fas fa-times"></i> Hủy lịch
                        </button>
                    ` : ''}
                </div>
            </li>
        `;
    }).join('');
}

function displayNoAppointments() {
    const list = document.getElementById('appointmentsList');
    list.innerHTML = `
        <li style="text-align: center; padding: 40px; color: #999;">
            <i class="fas fa-calendar-times" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
            <p>Bạn chưa có lịch hẹn nào</p>
            <a href="/appointments/create" class="btn btn-primary" style="margin-top: 20px; display: inline-block;">
                <i class="fas fa-plus"></i> Đặt lịch ngay
            </a>
        </li>
    `;
}

async function cancelAppointment(id) {
    if (!confirm('Bạn có chắc muốn hủy lịch hẹn này?')) return;
    
    try {
        const response = await fetch(`/api/appointments/${id}/cancel`, {
            method: 'PUT',
            headers: getAuthHeaders(true)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('success', 'Hủy lịch hẹn thành công!');
            loadUserAppointments();
        } else {
            showAlert('error', data.msg || 'Không thể hủy lịch hẹn!');
        }
    } catch (error) {
        console.error('Cancel error:', error);
        showAlert('error', 'Có lỗi xảy ra!');
    }
}

// ==================== LOAD INVOICES ====================
async function loadUserInvoices() {
    try {
        const response = await fetch('/api/payment/invoices', {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load invoices');
        }
        
        const invoices = await response.json();
        displayInvoices(invoices);
    } catch (error) {
        console.error('Error loading invoices:', error);
        displayNoInvoices();
    }
}

function displayInvoices(invoices) {
    const list = document.getElementById('invoicesList');
    
    if (!invoices || invoices.length === 0) {
        displayNoInvoices();
        return;
    }
    
    list.innerHTML = invoices.map(invoice => `
        <li class="invoice-item">
            <div class="invoice-header">
                <div class="invoice-info">
                    <div class="invoice-detail">
                        <span class="invoice-label">Mã hóa đơn</span>
                        <span class="invoice-value">#${invoice.mahd}</span>
                    </div>
                    <div class="invoice-detail">
                        <span class="invoice-label">Ngày lập</span>
                        <span class="invoice-value">${formatDate(invoice.ngaylap)}</span>
                    </div>
                    <div class="invoice-detail">
                        <span class="invoice-label">Tổng tiền</span>
                        <span class="invoice-amount">${formatCurrency(invoice.tongtien)}</span>
                    </div>
                </div>
                <span class="invoice-status status-${getStatusClass(invoice.trangthai)}">
                    ${getStatusText(invoice.trangthai)}
                </span>
            </div>
            
            <div class="invoice-actions">
                <button class="btn btn-outline btn-sm" onclick="viewInvoiceDetails(${invoice.mahd})">
                    <i class="fas fa-eye"></i> Xem chi tiết
                </button>
                ${invoice.trangthai !== 'Đã thanh toán' ? `
                    <button class="btn btn-primary btn-sm" onclick="payInvoice(${invoice.mahd}, ${invoice.tongtien})">
                        <i class="fas fa-credit-card"></i> Thanh toán
                    </button>
                ` : ''}
            </div>
        </li>
    `).join('');
}

function displayNoInvoices() {
    const list = document.getElementById('invoicesList');
    list.innerHTML = `
        <li style="text-align: center; padding: 40px; color: #999;">
            <i class="fas fa-receipt" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
            <p>Bạn chưa có hóa đơn nào</p>
        </li>
    `;
}

// ==================== INVOICE DETAILS MODAL ====================
async function viewInvoiceDetails(invoiceId) {
    try {
        const response = await fetch(`/api/payment/invoices/${invoiceId}`, {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load invoice details');
        }
        
        const invoice = await response.json();
        showInvoiceModal(invoice);
    } catch (error) {
        console.error('Error loading invoice details:', error);
        showAlert('error', 'Không thể tải chi tiết hóa đơn!');
    }
}

function showInvoiceModal(invoice) {
    const modal = document.createElement('div');
    modal.className = 'invoice-details-modal active';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 style="margin: 0;">Chi tiết hóa đơn #${invoice.mahd}</h3>
                <button class="modal-close" onclick="this.closest('.invoice-details-modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="invoice-info" style="margin-bottom: 20px;">
                <div class="invoice-detail">
                    <span class="invoice-label">Ngày lập</span>
                    <span class="invoice-value">${formatDate(invoice.ngaylap)}</span>
                </div>
                <div class="invoice-detail">
                    <span class="invoice-label">Trạng thái</span>
                    <span class="invoice-status status-${getStatusClass(invoice.trangthai)}">
                        ${getStatusText(invoice.trangthai)}
                    </span>
                </div>
            </div>
            
            <h4>Chi tiết dịch vụ</h4>
            <ul class="details-list">
                ${invoice.chitiet ? invoice.chitiet.map(item => `
                    <li class="detail-item">
                        <span class="detail-name">${item.tendv}</span>
                        <span class="detail-quantity">${item.soluong} x</span>
                        <span class="detail-price">${formatCurrency(item.dongia)}</span>
                        <span class="detail-total">${formatCurrency(item.thanhtien)}</span>
                    </li>
                `).join('') : '<li>Không có chi tiết</li>'}
            </ul>
            
            <div class="total-section">
                Tổng cộng: ${formatCurrency(invoice.tongtien)}
            </div>
            
            ${invoice.trangthai !== 'Đã thanh toán' ? `
                <div class="invoice-actions" style="margin-top: 20px; justify-content: center;">
                    <button class="btn btn-primary" onclick="payInvoice(${invoice.mahd}, ${invoice.tongtien})">
                        <i class="fas fa-credit-card"></i> Thanh toán ngay
                    </button>
                </div>
            ` : ''}
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// ==================== PAYMENT HANDLING (ĐÃ SỬA: TẠO QR MOMO) ====================
async function payInvoice(invoiceId, amount) {
    if (!confirm(`Bạn có chắc muốn thanh toán hóa đơn #${invoiceId} với số tiền ${formatCurrency(amount)}? Hệ thống sẽ tạo mã QR Momo.`)) {
        return;
    }
    
    try {
        showQRModal(invoiceId); // Hiện modal QR
        
        const response = await fetch(`/api/payment/invoices/${invoiceId}/generate-qr`, { 
            method: 'POST',
            headers: getAuthHeaders(true),
        });
        
        const data = await response.json();
        
        if (response.ok && data.qrCodeUrl) {
            
            const qrContainer = document.getElementById('qr-code-container-cust');
            qrContainer.innerHTML = '';
            
            const qrDiv = document.createElement('div');
            qrDiv.id = `qrcode-canvas-${invoiceId}`;
            qrDiv.style.margin = '20px auto';
            qrContainer.appendChild(qrDiv);
            
            if (typeof QRCode !== 'undefined') {
                 new QRCode(qrDiv, {
                    text: data.qrCodeUrl,
                    width: 200,
                    height: 200,
                    colorDark: "#000000",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
            } else {
                 qrContainer.innerHTML = `<p style="color:red;">Lỗi: Thư viện QRCode không tải được.</p>`;
                 throw new Error('Thư viện QRCode chưa được load');
            }
            
            startCustomerPaymentPolling(invoiceId);
            
        } else {
            closeQRModal();
            showAlert('error', data.msg || 'Không thể tạo mã QR Momo!');
        }
    } catch (error) {
        closeQRModal();
        console.error('Payment error:', error);
        showAlert('error', 'Có lỗi xảy ra khi tạo mã QR!');
    }
}

// ==================== HÀM HIỂN THỊ QR (MỚI) ====================
function showQRModal(invoiceId) {
    const modal = document.createElement('div');
    modal.className = 'qr-payment-modal active';
    modal.id = 'qrPaymentModal';
    
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.7); display: flex; justify-content: center; 
        align-items: center; z-index: 10000;
    `;
    
    modal.innerHTML = `
        <div class="modal-content" style="width: 350px; padding: 20px; text-align: center;">
            <div class="modal-header" style="justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px;">
                <h3 style="margin: 0; font-size: 18px;"><i class="fas fa-qrcode"></i> Thanh toán Momo #${invoiceId}</h3>
                <button class="modal-close" onclick="closeQRModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div id="qr-code-container-cust" style="display: flex; justify-content: center; align-items: center; min-height: 250px;">
                <div class="text-center" style="padding: 30px;">
                    <i class="fas fa-spinner fa-spin" style="font-size: 24px;"></i>
                    <p style="margin-top: 10px;">Đang tạo mã QR...</p>
                </div>
            </div>
            <p id="customer-payment-status" style="margin-top: 15px; font-weight: 600; color: #007bff;">
                Vui lòng quét mã để thanh toán.
            </p>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeQRModal();
        }
    });
}

function closeQRModal() {
    const modal = document.getElementById('qrPaymentModal');
    if (modal) {
        modal.remove();
        document.body.style.overflow = 'auto';
    }
    
    if (window.customerPollingInterval) {
        clearInterval(window.customerPollingInterval);
        window.customerPollingInterval = null;
    }
}

// ==================== POLLING (MỚI) ====================
let customerPollingAttempts = 0;
const MAX_CUSTOMER_POLLING_ATTEMPTS = 60;

async function startCustomerPaymentPolling(invoiceId) {
    customerPollingAttempts = 0;
    
    window.customerPollingInterval = setInterval(async () => {
        customerPollingAttempts++;
        
        try {
            const response = await fetch(`/api/payment/invoices/${invoiceId}`, {
                headers: getAuthHeaders(false)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.trangthai === 'Đã thanh toán') {
                    clearInterval(window.customerPollingInterval);
                    
                    const statusDiv = document.getElementById('customer-payment-status');
                    if (statusDiv) {
                        statusDiv.textContent = 'Thanh toán thành công!';
                        statusDiv.style.color = '#155724';
                    }
                    
                    showAlert('success', 'Thanh toán Momo thành công!');
                    
                    setTimeout(() => {
                        closeQRModal();
                        loadUserInvoices(); 
                    }, 2000);
                }
            }
            
            if (customerPollingAttempts >= MAX_CUSTOMER_POLLING_ATTEMPTS) {
                clearInterval(window.customerPollingInterval);
                const statusDiv = document.getElementById('customer-payment-status');
                if (statusDiv) {
                    statusDiv.textContent = 'Quá thời gian chờ thanh toán.';
                    statusDiv.style.color = '#721c24';
                }
            }
            
        } catch (error) {
            console.error('Lỗi polling:', error);
        }
        
    }, 3000);
}

// ==================== UTILITY FUNCTIONS ====================
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(amount);
}

function getStatusClass(status) {
    const statusMap = {
        'Đã thanh toán': 'paid',
        'Chờ thanh toán': 'pending',
        'Đã hủy': 'cancelled'
    };
    return statusMap[status] || 'pending';
}

function getStatusText(status) {
    const statusMap = {
        'Đã thanh toán': 'Đã thanh toán',
        'Chờ thanh toán': 'Chờ thanh toán',
        'Đã hủy': 'Đã hủy'
    };
    return statusMap[status] || status;
}

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#d4edda' : '#f8d7da'};
        color: ${type === 'success' ? '#155724' : '#721c24'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    alertDiv.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        ${message}
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}