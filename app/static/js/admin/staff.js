// ====== BIẾN GLOBAL ======
let allStaff = [];
let positions = [];

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    loadStaffList();
    loadPositions();
    setupFormSubmit();
});

// ====== TẢI DANH SÁCH NHÂN VIÊN ======
async function loadStaffList() {
    try {
        const response = await fetch('/api/admin/staff/list-all', {
            headers: getAuthHeaders(false) // Lấy từ admin_layout.js
        });
        
        if (!response.ok) {
             const err = await response.json();
             throw new Error(err.msg || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        allStaff = data;
        renderStaffTable(allStaff);
        updateStaffStats(allStaff.length); // <--- Cập nhật stat ban đầu
    } catch (error) {
        console.error('Lỗi tải nhân viên:', error);
        showError(error.message || 'Không thể tải danh sách nhân viên');
    }
}

// ====== CẬP NHẬT STATS NHÂN VIÊN ======
function updateStaffStats(totalCount) {
    const statElement = document.getElementById('total-staff-stat');
    if (statElement) {
        statElement.textContent = totalCount;
    }
}

// ====== TẢI DANH SÁCH CHỨC VỤ ======
async function loadPositions() {
    try {
        const response = await fetch('/api/admin/roles', {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        positions = data;
        renderPositionOptions();
    } catch (error) {
        console.error('Lỗi tải chức vụ:', error);
    }
}

// ====== RENDER DROPDOWN CHỨC VỤ ======
function renderPositionOptions() {
    const select = document.getElementById('staff-position');
    if (!select) return;
    select.innerHTML = '<option value="">-- Chọn chức vụ --</option>' +
        positions.map(p => `<option value="${p.macv}">${p.tencv}</option>`).join('');
}

// ====== RENDER BẢNG NHÂN VIÊN ======
function renderStaffTable(staffList) {
    const tbody = document.querySelector('#staff-table tbody');
    
    if (staffList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center">Không có nhân viên nào</td></tr>';
        return;
    }
    
    tbody.innerHTML = staffList.map(staff => {
        
        let avatarHtml = '';
        if (staff.anhnhanvien) {
            const avatarUrl = `/api/profile/avatar/${staff.anhnhanvien}`;
            avatarHtml = `<img src="${avatarUrl}" alt="Avatar" class="table-avatar">`;
        } else {
            avatarHtml = `<div class="table-avatar-icon"><i class="fas fa-user"></i></div>`;
        }

        // Cập nhật: Thêm nút Kích hoạt (true) nếu trạng thái là Vô hiệu (false)
        const actionButton = staff.trangthai ? 
            `<button class="btn btn-danger btn-sm" onclick="deactivateStaff(${staff.manv})" title="Vô hiệu hóa">
                <i class="fas fa-ban"></i>
            </button>` : 
            `<button class="btn btn-success btn-sm" onclick="activateStaff(${staff.manv})" title="Kích hoạt">
                <i class="fas fa-check"></i>
            </button>`;

        return `
            <tr>
                <td>${avatarHtml}</td>
                <td class="d-none">#${staff.manv}</td>
                <td>${staff.hoten}</td>
                <td class="d-none">${staff.taikhoan}</td>
                <td>${staff.email || 'N/A'}</td>
                <td class="d-none">${staff.sdt || 'N/A'}</td>
                <td>${staff.chucvu || 'N/A'}</td>
                <td><span class="badge badge-${staff.role}">${getRoleText(staff.role)}</span></td>
                <td><span class="badge badge-${staff.trangthai ? 'active' : 'inactive'}">${staff.trangthai ? 'Hoạt động' : 'Vô hiệu'}</span></td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-info btn-sm" onclick="viewStaffDetail(${staff.manv})" title="Xem chi tiết">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-warning btn-sm" onclick="editStaff(${staff.manv})" title="Sửa">
                            <i class="fas fa-edit"></i>
                        </button>
                        ${actionButton}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// ====== LỌC NHÂN VIÊN (CẬP NHẬT STATS) ======
function filterStaff() {
    const roleFilter = document.getElementById('filter-role').value;
    const statusFilter = document.getElementById('filter-status').value;
    
    let filtered = allStaff;
    
    if (roleFilter) {
        filtered = filtered.filter(s => s.role === roleFilter);
    }
    
    if (statusFilter !== '') {
        const status = statusFilter === 'true';
        filtered = filtered.filter(s => s.trangthai === status);
    }
    
    renderStaffTable(filtered);
    updateStaffStats(filtered.length); // <--- CẬP NHẬT STATS SAU KHI LỌC
}

// ====== MODAL THÊM/SỬA ======
function openAddStaffModal() {
    document.getElementById('modal-title').textContent = 'Thêm nhân viên';
    document.getElementById('staffForm').reset();
    document.getElementById('staff-id').value = '';
    document.getElementById('password-group').style.display = 'block';
    document.getElementById('staff-password').required = true;
    
    document.getElementById('staff-status').value = 'true'; 
    
    document.getElementById('staff-username').disabled = false;
    document.getElementById('staff-avatar-file').value = null;
    document.getElementById('staffModal').style.display = 'flex';
}

function closeStaffModal() {
    document.getElementById('staffModal').style.display = 'none';
    document.getElementById('staff-username').disabled = false;
}

function editStaff(id) {
    const staff = allStaff.find(s => s.manv === id);
    if (!staff) return;
    
    document.getElementById('modal-title').textContent = 'Sửa thông tin nhân viên';
    document.getElementById('staff-id').value = staff.manv;
    document.getElementById('staff-name').value = staff.hoten;
    document.getElementById('staff-username').value = staff.taikhoan;
    document.getElementById('staff-username').disabled = false; 
    document.getElementById('staff-email').value = staff.email || '';
    document.getElementById('staff-phone').value = staff.sdt || '';
    document.getElementById('staff-role').value = staff.role;
    
    document.getElementById('staff-status').value = staff.trangthai.toString(); 
    
    document.getElementById('staff-avatar-file').value = null;
    
    const position = positions.find(p => p.tencv === staff.chucvu);
    if (position) {
        document.getElementById('staff-position').value = position.macv;
    }
    
    document.getElementById('password-group').style.display = 'none';
    document.getElementById('staff-password').required = false;
    
    document.getElementById('staffModal').style.display = 'flex';
}

// ====== XEM CHI TIẾT NHÂN VIÊN ======
function viewStaffDetail(id) {
    const staff = allStaff.find(s => s.manv === id);
    if (!staff) return;

    const statusText = staff.trangthai 
        ? '<span class="badge badge-active">Hoạt động</span>' 
        : '<span class="badge badge-inactive">Vô hiệu hóa</span>';
    
    let avatarHtml = '';
    if (staff.anhnhanvien) {
        const avatarUrl = `/api/profile/avatar/${staff.anhnhanvien}`;
        avatarHtml = `<img src="${avatarUrl}" alt="Avatar" class="detail-avatar">`;
    } else {
        avatarHtml = `<div class="detail-avatar-icon"><i class="fas fa-user"></i></div>`;
    }

    const modalHtml = `
        <div id="viewStaffDetailModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Chi tiết nhân viên: ${staff.hoten}</h3>
                    <span class="close" onclick="closeViewStaffDetailModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <div class="detail-avatar-container">
                        ${avatarHtml}
                    </div>
                    
                    <p><strong>Mã nhân viên:</strong> <span>#${staff.manv}</span></p>
                    <p><strong>Họ tên:</strong> <span>${staff.hoten}</span></p>
                    <p><strong>Tài khoản:</strong> <span>${staff.taikhoan}</span></p>
                    <p><strong>Email:</strong> <span>${staff.email || 'N/A'}</span></p>
                    <p><strong>Số điện thoại:</strong> <span>${staff.sdt || 'N/A'}</span></p>
                    <p><strong>Chức vụ:</strong> <span>${staff.chucvu || 'N/A'}</span></p>
                    <p><strong>Vai trò (Quyền):</strong> <span>${getRoleText(staff.role)}</span></p>
                    <p><strong>Trạng thái:</strong> <span>${statusText}</span></p>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeViewStaffDetailModal()">Đóng</button>
                </div>
            </div>
        </div>
    `;

    closeViewStaffDetailModal(); 
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function closeViewStaffDetailModal() {
    const modal = document.getElementById('viewStaffDetailModal');
    if (modal) {
        modal.remove();
    }
}

// ====== CÀI ĐẶT SUBMIT FORM ======
function setupFormSubmit() {
    document.getElementById('staffForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const id = document.getElementById('staff-id').value;
        const fileInput = document.getElementById('staff-avatar-file');
        
        if (!document.getElementById('staff-position').value) {
            showError('Vui lòng chọn chức vụ');
            return;
        }

        // 1. Tạo FormData
        const formData = new FormData();
        formData.append('hoten', document.getElementById('staff-name').value);
        formData.append('taikhoan', document.getElementById('staff-username').value);
        formData.append('email', document.getElementById('staff-email').value);
        formData.append('sdt', document.getElementById('staff-phone').value);
        formData.append('macv', document.getElementById('staff-position').value);
        formData.append('role', document.getElementById('staff-role').value);
        
        formData.append('trangthai', document.getElementById('staff-status').value);

        // 2. Thêm file nếu có
        if (fileInput.files.length > 0) {
            formData.append('anhnhanvien', fileInput.files[0]);
        }

        let url = '';
        let method = '';

        if (id) {
            // === Chế độ SỬA (PUT) ===
            url = `/api/admin/staff/${id}`;
            method = 'PUT';
            
        } else {
            // === Chế độ THÊM MỚI (POST) ===
            url = '/api/admin/staff/add';
            method = 'POST';
            const password = document.getElementById('staff-password').value;
            if (!password) {
                showError('Vui lòng nhập mật khẩu');
                return;
            }
            formData.append('matkhau', password);
        }
        
        try {
            // 3. Gửi request
            const response = await fetch(url, {
                method: method,
                headers: getAuthHeaders(false), // KHÔNG set Content-Type
                body: formData 
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showSuccess(data.msg || 'Lưu thành công');
                closeStaffModal();
                loadStaffList();
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
            
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra khi lưu');
        }
    });
}

// ====== VÔ HIỆU HÓA NHÂN VIÊN ======
async function deactivateStaff(id) {
    if (!confirm('Bạn có chắc muốn vô hiệu hóa nhân viên này?')) return;
    
    try {
        const response = await fetch(`/api/admin/staff/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Vô hiệu hóa thành công');
            loadStaffList();
        } else {
            showError(data.msg || 'Có lỗi xảy ra');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra');
    }
}

// ====== KÍCH HOẠT LẠI NHÂN VIÊN ======
async function activateStaff(id) {
    if (!confirm('Bạn có chắc muốn kích hoạt lại nhân viên này?')) return;
    
    try {
        // 1. Tạo FormData (Sử dụng PUT với FormData để gửi trạng thái mới)
        const formData = new FormData();
        formData.append('trangthai', 'true'); // Gửi 'true' để kích hoạt

        const response = await fetch(`/api/admin/staff/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(false), 
            body: formData 
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Kích hoạt thành công');
            loadStaffList();
        } else {
            showError(data.msg || 'Có lỗi xảy ra');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra');
    }
}

// ====== HELPER FUNCTIONS ======
function getRoleText(role) {
    const roleMap = {
        'admin': 'Admin',
        'manager': 'Manager',
        'letan': 'Lễ tân',
        'staff': 'Kỹ thuật viên'
    };
    return roleMap[role] || role;
}


// ====== HỆ THỐNG TOAST (Đã sửa lỗi tự tắt) ======
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
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast && toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 500);
    }, 3000);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}