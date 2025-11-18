// ====== BIẾN GLOBAL ======
let allServices = [];
let currentAction = null;
let currentServiceId = null;
let currentPage = 1; // Thêm biến phân trang
const itemsPerPage = 10; // Thêm biến phân trang

// ====== UTILITY FUNCTIONS (Giữ nguyên) ======
function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        alert((type === 'success' ? '✅ ' : '❌ ') + message);
        console.error('Không tìm thấy #toast-container!');
        return;
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const iconClass = type === 'success' ? 'fas fa-check-circle' : 'fas fa-times-circle';
    toast.innerHTML = `<i class="${iconClass}"></i> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.classList.add('fade-out'), 3000);
    toast.addEventListener('animationend', () => toast.remove());
}
function showSuccess(message) { showToast(message, 'success'); }
function showError(message) { showToast(message, 'error'); }
function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}
function formatCurrency(amount) {
    if (!amount) return '0₫';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(parseFloat(amount));
}
function getAdminAuthToken() { return localStorage.getItem('admin_token'); }
function getAuthHeaders(includeContentType = true) {
    const token = getAdminAuthToken();
    if (!token) {
        logout(); // Cân nhắc logout nếu không có token
        return null;
    }
    const headers = { 'Authorization': `Bearer ${token}` };
    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
    }
    return headers;
}
function logout() {
    localStorage.clear(); // Xóa hết
    window.location.href = '/admin/login';
}

// ====== KHỞI TẠO (CẬP NHẬT) ======
document.addEventListener('DOMContentLoaded', function() {
    loadServices();
    
    // Gán sự kiện cho modal Thêm/Sửa (ảnh preview, submit)
    document.getElementById('service-image').addEventListener('change', previewServiceImage);
    document.getElementById('serviceForm').addEventListener('submit', handleSaveService);

    // Gán sự kiện cho Filter và Search (MỚI)
    const searchInput = document.getElementById('service-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    const statusFilter = document.getElementById('status-filter');

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
            currentPage = 1; 
            renderServicesTable();
            renderPagination();
        });
    }

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearSearchBtn.style.display = 'none';
            currentPage = 1;
            renderServicesTable();
            renderPagination();
        });
    }

    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            currentPage = 1;
            renderServicesTable();
            renderPagination();
        });
    }
});

function previewServiceImage(e) {
    const file = e.target.files[0];
    const preview = document.getElementById('preview-img');
    const previewContainer = document.getElementById('image-preview');
    
    if (file) {
        if (file.size > 5 * 1024 * 1024) { // Max 5MB
            showError('Kích thước ảnh không được vượt quá 5MB');
            this.value = '';
            return;
        }
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            previewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        previewContainer.style.display = 'none';
    }
}

// ====== TẢI DANH SÁCH DỊCH VỤ (CẬP NHẬT) ======
async function loadServices() {
    try {
        showLoading(true);
        const response = await fetch('/api/admin/services', { headers: getAuthHeaders(false) });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        allServices = await response.json();
        
        // Cập nhật thẻ thống kê
        document.getElementById('total-services-stat').textContent = allServices.length;
        
        renderServicesTable();
        renderPagination(); // Gọi hàm phân trang
    } catch (error) {
        console.error('Lỗi tải dịch vụ:', error);
        showError('Không thể tải danh sách dịch vụ: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function showLoading(show) {
    const tbody = document.querySelector('#services-table tbody');
    if (show) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
}

// ====== HÀM LỌC DỮ LIỆU (MỚI) ======
function getFilteredData() {
    const searchTerm = document.getElementById('service-search-input').value.trim().toLowerCase();
    const statusFilter = document.getElementById('status-filter').value; // "all", "true", "false"

    let filtered = allServices;

    // 1. Lọc theo Status
    if (statusFilter !== 'all') {
        const isActive = (statusFilter === 'true');
        filtered = filtered.filter(service => service.active === isActive);
    }

    // 2. Lọc theo Search Term (Chỉ tìm theo Tên)
    if (searchTerm) {
        filtered = filtered.filter(service => 
            (service.tendv || '').toLowerCase().includes(searchTerm)
        );
    }
    return filtered;
}

// ====== RENDER BẢNG (CẬP NHẬT) ======
function renderServicesTable() {
    const tbody = document.querySelector('#services-table tbody');
    if (!tbody) return;

    const filteredData = getFilteredData();

    // Phân trang
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedData = filteredData.slice(startIndex, startIndex + itemsPerPage);
    
    const colspan = 8; // Cập nhật colspan
    
    if (paginatedData.length === 0) {
        const searchTerm = document.getElementById('service-search-input').value.trim();
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center">
            ${(searchTerm || document.getElementById('status-filter').value !== 'all') ? 'Không tìm thấy dịch vụ nào' : 'Không có dịch vụ nào'}
        </td></tr>`;
        return;
    }
    
    tbody.innerHTML = paginatedData.map(service => {
        const imageHtml = service.anhdichvu 
            ? `<img src="data:image/jpeg;base64,${service.anhdichvu}" alt="${service.tendv}" class="table-avatar" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;">` 
            : `<div class="table-avatar-placeholder" style="width: 60px; height: 60px; ..."><i class="fas fa-image text-muted"></i></div>`;
        
        return `
        <tr>
            <td class="d-none">#${service.madv}</td>
            <td>${imageHtml}</td>
            <td>${service.tendv}</td>
            <td class="d-none">${formatCurrency(service.gia)}</td>
            <td class="d-none">${service.thoiluong ? service.thoiluong + ' phút' : 'N/A'}</td>
            <td>${truncateText(service.mota, 50)}</td>
            <td>
                <span class="badge badge-${service.active ? 'active' : 'inactive'}">
                    ${service.active ? 'Hoạt động' : 'Ngừng hoạt động'}
                </span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-info btn-sm" onclick="viewServiceDetail(${service.madv})" title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-warning btn-sm" onclick="editService(${service.madv})" title="Sửa">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-danger btn-sm d-none" onclick="confirmDeleteService(${service.madv})" title="Xóa">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
    }).join('');
}

// ====== PHÂN TRANG (MỚI) ======
function renderPagination() {
    const pagination = document.getElementById('pagination');
    if (!pagination) return;
    
    const filteredData = getFilteredData();
    const totalItems = filteredData.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let html = '';
    if (currentPage > 1) html += `<button class="page-btn" data-page="${currentPage - 1}">‹</button>`;
    
    for (let i = 1; i <= totalPages; i++) {
        html += (i === currentPage)
            ? `<button class="page-btn active">${i}</button>`
            : `<button class="page-btn" data-page="${i}">${i}</button>`;
    }
    
    if (currentPage < totalPages) html += `<button class="page-btn" data-page="${currentPage + 1}">›</button>`;
    
    pagination.innerHTML = html;
    
    pagination.querySelectorAll('.page-btn[data-page]').forEach(btn => {
        btn.addEventListener('click', () => changePage(parseInt(btn.dataset.page)));
    });
}

function changePage(page) {
    currentPage = page;
    renderServicesTable();
    renderPagination();
    document.getElementById('services-table').scrollIntoView({ behavior: 'smooth' });
}

// ====== MODAL XEM CHI TIẾT (Giữ nguyên) ======
function closeViewServiceModal() {
    document.getElementById('viewServiceModal').style.display = 'none';
}

async function viewServiceDetail(id) {
    const service = allServices.find(s => s.madv === id);
    if (!service) return showError('Không tìm thấy dịch vụ');

    document.getElementById('view-modal-title').textContent = `Chi tiết: ${service.tendv}`;
    const contentContainer = document.getElementById('service-detail-content');
    
    let imageHtml = '<p><strong>Hình ảnh:</strong> Không có ảnh</p>';
    if (service.anhdichvu) {
        imageHtml = `<div style="text-align: center; margin-bottom: 15px;">
            <img src="data:image/jpeg;base64,${service.anhdichvu}" alt="${service.tendv}" style="max-width: 300px; max-height: 300px; border-radius: 8px; object-fit: cover;">
        </div>`;
    }

    contentContainer.innerHTML = `
        ${imageHtml}
        <p><strong>Mã DV:</strong> #${service.madv}</p>
        <p><strong>Giá:</strong> ${formatCurrency(service.gia)}</p>
        <p><strong>Thời lượng:</strong> ${service.thoiluong ? service.thoiluong + ' phút' : 'N/A'}</p>
        <p><strong>Trạng thái:</strong> ${service.active ? 'Hoạt động' : 'Ngừng hoạt động'}</p>
        <p><strong>Mô tả chi tiết:</strong></p>
        <div style="white-space: pre-wrap; word-wrap: break-word; background: #f9f9f9; padding: 10px; border-radius: 4px; max-height: 200px; overflow-y: auto;">
            ${service.mota || 'Không có mô tả.'}
        </div>
    `;
    
    document.getElementById('viewServiceModal').style.display = 'flex';
}

// ====== MODAL THÊM/SỬA (Giữ nguyên) ======
function openAddServiceModal() {
    document.getElementById('modal-title').textContent = 'Thêm dịch vụ';
    document.getElementById('serviceForm').reset();
    document.getElementById('service-id').value = '';
    document.getElementById('service-status').value = 'true';
    document.getElementById('image-preview').style.display = 'none';
    document.getElementById('serviceModal').style.display = 'flex';
}

function closeServiceModal() {
    document.getElementById('serviceModal').style.display = 'none';
    document.getElementById('service-image').value = '';
}

async function editService(id) {
    const service = allServices.find(s => s.madv === id);
    if (!service) return;
    
    document.getElementById('modal-title').textContent = 'Sửa dịch vụ';
    document.getElementById('service-id').value = service.madv;
    document.getElementById('service-name').value = service.tendv;
    document.getElementById('service-price').value = service.gia;
    document.getElementById('service-duration').value = service.thoiluong || '';
    document.getElementById('service-desc').value = service.mota || '';
    document.getElementById('service-status').value = service.active.toString();
    
    const imagePreview = document.getElementById('image-preview');
    const previewImg = document.getElementById('preview-img');
    if (service.anhdichvu) {
        previewImg.src = `data:image/jpeg;base64,${service.anhdichvu}`;
        imagePreview.style.display = 'block';
    } else {
        imagePreview.style.display = 'none';
    }
    
    document.getElementById('serviceModal').style.display = 'flex';
}

// ====== LƯU DỊCH VỤ (Giữ nguyên) ======
async function handleSaveService(e) {
    e.preventDefault();
    
    const id = document.getElementById('service-id').value;
    const name = document.getElementById('service-name').value;
    const price = document.getElementById('service-price').value;
    const duration = document.getElementById('service-duration').value;
    const desc = document.getElementById('service-desc').value;
    const active = document.getElementById('service-status').value;
    const imageFile = document.getElementById('service-image').files[0];
    
    if (!name || !price) {
        showError('Vui lòng điền tên dịch vụ và giá');
        return;
    }
    
    const formData = new FormData();
    formData.append('tendv', name);
    formData.append('gia', parseFloat(price));
    if (duration) formData.append('thoiluong', parseInt(duration));
    if (desc) formData.append('mota', desc);
    formData.append('active', active); // Gửi "true" hoặc "false"
    
    if (imageFile) {
        formData.append('anhdichvu', imageFile);
    }
    
    let url = '/api/admin/services';
    let method = 'POST';
    if (id) {
        url = `/api/admin/services/${id}`;
        method = 'PUT';
    }
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${getAdminAuthToken()}`
                // Không 'Content-Type' khi dùng FormData
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.msg || (id ? 'Cập nhật dịch vụ thành công' : 'Thêm dịch vụ thành công'));
            closeServiceModal();
            loadServices(); // Tải lại danh sách
        } else {
            showError(data.msg || 'Có lỗi xảy ra');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra khi lưu dịch vụ: ' + error.message);
    }
}

// ====== XÓA DỊCH VỤ (Giữ nguyên) ======
function confirmDeleteService(id) {
    const service = allServices.find(s => s.madv === id);
    if (!service) return;
    
    currentServiceId = id;
    document.getElementById('confirm-message').textContent = `Bạn có chắc muốn xóa dịch vụ "${service.tendv}"?`;
    document.getElementById('confirm-btn').onclick = deleteService;
    document.getElementById('confirmModal').style.display = 'flex';
}

async function deleteService() {
    if (!currentServiceId) return;
    
    try {
        const response = await fetch(`/api/admin/services/${currentServiceId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('Xóa dịch vụ thành công');
            closeConfirmModal();
            loadServices();
        } else {
            showError(data.msg || 'Có lỗi xảy ra khi xóa dịch vụ');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra khi xóa dịch vụ');
    }
}

function closeConfirmModal() {
    document.getElementById('confirmModal').style.display = 'none';
    currentServiceId = null;
}