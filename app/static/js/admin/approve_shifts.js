// (File mới: static/js/admin/approve_shifts.js)

document.addEventListener('DOMContentLoaded', function() {
    loadPendingRegistrations();
});

// ====== TẢI DANH SÁCH CHỜ DUYỆT ======
async function loadPendingRegistrations() {
    try {
        showLoading(true);
        
        const response = await fetch('/api/admin/shifts/registrations/pending', {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            renderApproveTable(data || []);
        } else {
            showError(data.msg || 'Không thể tải danh sách chờ');
        }
    } catch (error) {
        console.error('Lỗi tải danh sách chờ:', error);
        showError('Không thể tải danh sách chờ');
    } finally {
        showLoading(false);
    }
}

// ====== RENDER BẢNG CHỜ DUYỆT ======
function renderApproveTable(pendingList) {
    const tbody = document.getElementById('approve-table-body');
    
    if (pendingList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Không có đơn đăng ký nào đang chờ</td></tr>';
        return;
    }
    
    tbody.innerHTML = pendingList.map(reg => `
        <tr>
            <td>${formatDateDisplay(reg.ngaydangky)}</td>
            <td>${reg.nhanvien.hoten} </td>
            <td>${formatDateDisplay(reg.calam.ngay)}</td>
            <td>${reg.calam.giobatdau} - ${reg.calam.gioketthuc}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-success btn-sm" onclick="handleRegistration(${reg.reg_id}, 'approve')" title="Duyệt">
                        <i class="fas fa-check"></i> Duyệt
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="handleRegistration(${reg.reg_id}, 'reject')" title="Từ chối">
                        <i class="fas fa-times"></i> Từ chối
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

// ====== XỬ LÝ DUYỆT/TỪ CHỐI ======
async function handleRegistration(regId, action) {
    const actionText = action === 'approve' ? 'Duyệt' : 'Từ chối';
    
    const doAction = async () => {
        try {
            const response = await fetch(`/api/admin/shifts/registrations/${regId}/${action}`, {
                method: 'PUT',
                headers: getAuthHeaders(false)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showSuccess(data.msg || `${actionText} thành công`);
                loadPendingRegistrations(); // Tải lại danh sách
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra');
        }
    };
    
    showConfirm(
        `Xác nhận ${actionText}`, 
        `Bạn có chắc muốn ${actionText.toLowerCase()} đơn đăng ký này?`,
        doAction
    );
}

// ====== HELPERS (Copy từ các file JS khác) ======
function formatDateDisplay(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}
function showLoading(show) {
    const tbody = document.getElementById('approve-table-body');
    if (show) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
}
function getAuthHeaders(includeContentType = true) {
    const token = localStorage.getItem('admin_token');
    if (!token) { window.location.href = '/admin/login'; return null; }
    const headers = { 'Authorization': `Bearer ${token}` };
    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
        headers['Accept'] = 'application/json';
    }
    return headers;
}
function showToast(message, type = 'success') {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`; 
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `<i class="fas ${iconClass}"></i> ${message}`;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.classList.add('show'); }, 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast && toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 500);
    }, 3000);
}
function showSuccess(message) { showToast(message, 'success'); }
function showError(message) { showToast(message, 'error'); }
function showConfirm(title, message, onConfirm) {
    const oldModal = document.getElementById('confirm-toast-modal');
    if (oldModal) oldModal.remove();
    const modalHtml = `
        <div id="confirm-toast-modal">
            <div class="confirm-toast-content">
                <div class="confirm-toast-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>${title}</h4>
                </div>
                <div class="confirm-toast-body">${message}</div>
                <div class="confirm-toast-actions">
                    <button type="button" class="btn btn-secondary" id="confirm-btn-cancel">Hủy</button>
                    <button type="button" class="btn btn-primary" id="confirm-btn-ok">OK</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = document.getElementById('confirm-toast-modal');
    const closeModal = () => {
        modal.classList.remove('show');
        setTimeout(() => { modal.remove(); }, 200);
    };
    document.getElementById('confirm-btn-ok').onclick = function() {
        onConfirm();
        closeModal();
    };
    document.getElementById('confirm-btn-cancel').onclick = closeModal;
    setTimeout(() => { modal.classList.add('show'); }, 10);
}