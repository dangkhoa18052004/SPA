// ============== GLOBAL VARIABLES ==============
let allRoles = [];
let isSubmitting = false; // Ngăn chặn gửi form nhiều lần

// ============== INITIALIZATION ==============
document.addEventListener('DOMContentLoaded', function() {
    loadRoles();
    setupEventListeners();
});

/**
 * Gán các sự kiện lắng nghe chung cho trang
 */
function setupEventListeners() {
    // Ngăn chặn gửi form trùng lặp
    const form = document.getElementById('roleForm');
    if (form) {
        form.removeEventListener('submit', handleRoleFormSubmit);
        form.addEventListener('submit', handleRoleFormSubmit);
    }
    
    // Đóng modal khi click ra ngoài
    const modal = document.getElementById('roleModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeRoleModal();
            }
        });
    }

    // (Bổ sung) Đóng modal XÓA khi click ra ngoài
    const deleteModal = document.getElementById('deleteConfirmModal');
    if (deleteModal) {
        deleteModal.addEventListener('click', function(e) {
            if (e.target === deleteModal) {
                closeDeleteModal();
            }
        });
    }
    
    // Đóng modal bằng phím ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('roleModal');
            const deleteModal = document.getElementById('deleteConfirmModal');

            if (modal && modal.style.display === 'flex') {
                closeRoleModal();
            } 
            else if (deleteModal && deleteModal.style.display === 'flex') {
                closeDeleteModal();
            }
        }
        
        // Ctrl/Cmd + N để thêm mới
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            openAddRoleModal();
        }
        
        // Ctrl/Cmd + F để focus vào ô tìm kiếm
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            document.getElementById('searchInput')?.focus();
        }
    });
}

// ============== API FUNCTIONS ==============

/**
 * Tải danh sách chức vụ từ server
 */
async function loadRoles() {
    try {
        showLoading();
        
        const response = await fetch('/api/admin/roles', {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        allRoles = data || [];
        renderRolesTable();
        updateStats();
    } catch (error) {
        console.error('Lỗi tải chức vụ:', error);
        showError('Không thể tải danh sách chức vụ');
        showEmptyState('Không thể tải dữ liệu');
    }
}

/**
 * Xử lý việc gửi form (Thêm mới hoặc Cập nhật)
 */
async function handleRoleFormSubmit(e) {
    e.preventDefault();
    
    if (isSubmitting) return; // Ngăn gửi trùng
    
    const roleId = document.getElementById('roleId').value;
    const roleName = document.getElementById('roleName').value.trim();
    const roleRate = document.getElementById('roleRate').value;
    
    // --- Validation ---
    if (!roleName || roleName.length < 2) {
        showError('Tên chức vụ phải có ít nhất 2 ký tự');
        document.getElementById('roleName').focus();
        return;
    }
    
    if (roleRate === '' || parseFloat(roleRate) < 0) {
        showError('Đơn giá phải lớn hơn hoặc bằng 0');
        document.getElementById('roleRate').focus();
        return;
    }
    
    // Kiểm tra tên trùng
    const isDuplicate = allRoles.some(r => 
        r.tencv.toLowerCase() === roleName.toLowerCase() && 
        r.macv !== parseInt(roleId)
    );
    
    if (isDuplicate) {
        showError('Tên chức vụ đã tồn tại');
        document.getElementById('roleName').focus();
        return;
    }
    
    const payload = {
        tencv: roleName,
        dongiagio: parseFloat(roleRate)
    };
    
    isSubmitting = true;
    
    // Vô hiệu hóa nút Lưu
    const submitBtn = document.querySelector('#roleForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    }
    
    try {
        let url, method, successMsg;
        
        if (roleId) {
            url = `/api/admin/roles/${roleId}`;
            method = 'PUT';
            successMsg = 'Cập nhật chức vụ thành công';
        } else {
            url = '/api/admin/roles';
            method = 'POST';
            successMsg = 'Thêm chức vụ mới thành công';
        }
        
        const response = await fetch(url, {
            method: method,
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.msg || successMsg);
            closeRoleModal();
            await loadRoles();
        } else {
            showError(data.msg || 'Có lỗi xảy ra');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra khi lưu chức vụ');
    } finally {
        // Reset cờ và nút
        isSubmitting = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-save"></i> Lưu lại';
        }
    }
}

/**
 * Mở modal xác nhận xóa
 */
function deleteRole(macv) {
    const role = allRoles.find(r => r.macv === macv);
    
    if (!role) {
        showError('Không tìm thấy chức vụ');
        return;
    }

    // Lấy các thành phần của modal
    const modal = document.getElementById('deleteConfirmModal');
    const nameEl = document.getElementById('deleteRoleName');
    const rateEl = document.getElementById('deleteRoleRate');
    const confirmBtn = document.getElementById('confirmDeleteBtn');

    if (!modal || !nameEl || !rateEl || !confirmBtn) {
        console.error('Không tìm thấy các thành phần của deleteConfirmModal');
        return;
    }

    // 1. Điền thông tin vào modal
    nameEl.textContent = role.tencv;
    rateEl.textContent = `${formatCurrency(role.dongiagio)}/giờ`;

    // 2. Gán sự kiện cho nút "Xóa"
    confirmBtn.onclick = () => {
        executeDelete(role.macv);
    };

    // 3. Hiển thị modal
    modal.style.display = 'flex';
}

/**
 * Thực thi API xóa (được gọi từ modal xác nhận)
 */
async function executeDelete(macv) {
    const btn = document.getElementById('confirmDeleteBtn');
    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xóa...';

    try {
        const response = await fetch(`/api/admin/roles/${macv}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.msg || 'Xóa chức vụ thành công');
            await loadRoles();
        } else {
            showError(data.msg || 'Không thể xóa chức vụ này');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra khi xóa chức vụ');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-trash-alt"></i> Xóa';
        closeDeleteModal();
    }
}

// ============== UI FUNCTIONS ==============

/**
 * Hiển thị trạng thái loading trong bảng
 */
function showLoading() {
    const tbody = document.getElementById('rolesTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = `
        <tr>
            <td colspan="4" class="loading-row">
                <div class="spinner"></div>
                <p style="margin-top: 15px; color: #666;">Đang tải dữ liệu...</p>
            </td>
        </tr>
    `;
}

/**
 * Hiển thị trạng thái rỗng trong bảng
 */
function showEmptyState(message = 'Chưa có chức vụ nào') {
    const tbody = document.getElementById('rolesTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = `
        <tr>
            <td colspan="4">
                <div class="empty-state" style="padding: 40px; text-align: center; color: #777;">
                    <i class="fas fa-inbox" style="font-size: 48px; margin-bottom: 15px;"></i>
                    <h3>Không có dữ liệu</h3>
                    <p>${message}</p>
                    ${message.includes('Chưa có') ? '<button class="btn btn-primary" onclick="openAddRoleModal()" style="margin-top: 10px;"><i class="fas fa-plus"></i> Thêm chức vụ đầu tiên</button>' : ''}
                </div>
            </td>
        </tr>
    `;
}

/**
 * Vẽ lại bảng chức vụ
 */
function renderRolesTable() {
    const tbody = document.getElementById('rolesTableBody');
    
    if (!tbody) {
        console.error('Không tìm thấy tbody');
        return;
    }
    
    if (!allRoles || allRoles.length === 0) {
        showEmptyState('Chưa có chức vụ nào. Click "Thêm chức vụ" để bắt đầu.');
        return;
    }
    
    tbody.innerHTML = allRoles.map(role => `
        <tr>
            <td><span class="role-id">#${role.macv}</span></td>
            <td><span class="role-name">${escapeHtml(role.tencv)}</span></td>
            <td><span class="role-rate">${formatCurrency(role.dongiagio)}/giờ</span></td>
            <td class="text-center"> <div class="action-buttons">
                    <button class="btn btn-sm btn-warning" onclick="editRole(${role.macv})" title="Sửa chức vụ">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRole(${role.macv})" title="Xóa chức vụ">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/**
 * Lọc và hiển thị bảng dựa trên từ khóa tìm kiếm
 */
function searchRoles(query) {
    const searchTerm = query.toLowerCase().trim();
    const tbody = document.getElementById('rolesTableBody');
    
    if (!tbody) return;
    
    if (!searchTerm) {
        renderRolesTable(); // Hiển thị lại toàn bộ nếu ô tìm kiếm trống
        return;
    }
    
    const filtered = allRoles.filter(role => {
        return role.tencv.toLowerCase().includes(searchTerm) ||
               role.dongiagio.toString().includes(searchTerm) ||
               formatCurrency(role.dongiagio).toLowerCase().includes(searchTerm);
    });
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4">
                    <div class="empty-state" style="padding: 40px; text-align: center; color: #777;">
                        <i class="fas fa-search" style="font-size: 48px; margin-bottom: 15px;"></i>
                        <h3>Không tìm thấy kết quả</h3>
                        <p>Không có chức vụ nào phù hợp với từ khóa "${escapeHtml(query)}"</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Hiển thị kết quả đã lọc
    tbody.innerHTML = filtered.map(role => `
        <tr>
            <td><span class="role-id">#${role.macv}</span></td>
            <td><span class="role-name">${escapeHtml(role.tencv)}</span></td>
            <td><span class="role-rate">${formatCurrency(role.dongiagio)}/giờ</span></td>
            <td class="text-center">
                <div class="action-buttons">
                    <button class="btn btn-sm btn-warning" onclick="editRole(${role.macv})" title="Sửa">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteRole(${role.macv})" title="Xóa">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/**
 * Xử lý sự kiện khi gõ vào ô tìm kiếm
 */
function handleSearch(value) {
    const clearBtn = document.getElementById('searchClear');
    if (value.trim()) {
        clearBtn.classList.add('active');
    } else {
        clearBtn.classList.remove('active');
    }
    searchRoles(value);
}

/**
 * Xóa nội dung ô tìm kiếm
 */
function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('searchClear').classList.remove('active');
    searchRoles('');
    document.getElementById('searchInput').focus();
}

/**
 * Cập nhật thẻ thống kê
 */
function updateStats() {
    const totalElement = document.getElementById('total-roles');
    if (totalElement) {
        totalElement.textContent = allRoles.length;
    }
}

/**
 * Xuất dữ liệu ra file Excel (CSV)
 */
async function exportRolesToExcel() {
    if (!allRoles || allRoles.length === 0) {
        showWarning('Không có dữ liệu để xuất');
        return;
    }
    
    try {
        const headers = ['Mã CV', 'Tên chức vụ', 'Đơn giá/giờ'];
        const rows = allRoles.map(role => [
            role.macv,
            role.tencv,
            role.dongiagio
        ]);
        
        let csvContent = '\ufeff'; // BOM for UTF-8
        csvContent += headers.join(',') + '\n';
        csvContent += rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', `danh_sach_chuc_vu_${new Date().toISOString().slice(0, 10)}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showSuccess('Xuất file thành công');
    } catch (error) {
        console.error('Lỗi xuất Excel:', error);
        showError('Có lỗi xảy ra khi xuất file');
    }
}

// ============== UTILITY FUNCTIONS ==============

/**
 * Định dạng tiền tệ VNĐ
 */
function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '0₫';
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(parseFloat(amount));
}

/**
 * Chống XSS
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}

/**
 * Hiển thị thông báo toast
 */
function showToast(message, type = 'success') {
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    
    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, type === 'success' ? 3000 : 5000);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}

function showWarning(message) {
    showToast(message, 'warning');
}

// ============== MODAL FUNCTIONS ==============

/**
 * Mở modal để thêm mới chức vụ
 */
function openAddRoleModal() {
    const modal = document.getElementById('roleModal');
    const form = document.getElementById('roleForm');
    const modalTitle = document.getElementById('modalTitle');
    
    if (!modal || !form) return;
    
    form.reset();
    document.getElementById('roleId').value = '';
    isSubmitting = false;
    
    if (modalTitle) {
        modalTitle.innerHTML = '<i class="fas fa-plus-circle"></i> Thêm chức vụ mới';
    }

    // Reset nút submit (nếu bị kẹt ở trạng thái loading)
    const submitBtn = document.querySelector('#roleForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-save"></i> Lưu lại';
    }
    
    modal.style.display = 'flex';
    
    setTimeout(() => {
        document.getElementById('roleName')?.focus();
    }, 100);
}

/**
 * Mở modal để chỉnh sửa chức vụ
 */
function editRole(macv) {
    const role = allRoles.find(r => r.macv === macv);
    
    if (!role) {
        showError('Không tìm thấy chức vụ');
        return;
    }
    
    const modal = document.getElementById('roleModal');
    const modalTitle = document.getElementById('modalTitle');
    
    if (!modal) return;
    
    isSubmitting = false;
    
    document.getElementById('roleId').value = role.macv;
    document.getElementById('roleName').value = role.tencv;
    document.getElementById('roleRate').value = role.dongiagio;
    
    if (modalTitle) {
        modalTitle.innerHTML = '<i class="fas fa-edit"></i> Chỉnh sửa chức vụ';
    }

    // Reset nút submit (nếu bị kẹt ở trạng thái loading)
    const submitBtn = document.querySelector('#roleForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-save"></i> Lưu lại';
    }
    
    modal.style.display = 'flex';
    
    setTimeout(() => {
        document.getElementById('roleName')?.focus();
    }, 100);
}

/**
 * Đóng modal Thêm/Sửa
 */
function closeRoleModal() {
    const modal = document.getElementById('roleModal');
    if (modal) {
        modal.style.display = 'none';
    }
    isSubmitting = false;
}

/**
 * Đóng modal Xác nhận Xóa
 */
function closeDeleteModal() {
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Làm mới dữ liệu
 */
function refreshRoles() {
    loadRoles();
    showSuccess('Đã làm mới danh sách');
}

/**
 * Lấy header xác thực
 */
function getAuthHeaders(includeContentType = true) {
    const headers = {
        'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`
    };
    
    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
    }
    
    return headers;
}