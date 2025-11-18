// ========================================
// 1. KHAI BÁO BIẾN GLOBAL
// ========================================
let allAppointments = [];
let allCustomers = [];
let allServices = [];
let allStaff = [];
let availableStaff = [];
let currentPage = 1;
const itemsPerPage = 10;
let currentUserRole = null;

let selectedServiceIds = []; 
let selectedCustomerId = null;
let selectedStaffId = null;
let currentInvoiceId = null;
let pollingAttempts = 0;
const MAX_POLLING_ATTEMPTS = 60; 
let paymentPollingInterval = null; 

// ========================================
// 2. KHỞI TẠO & LOAD DATA
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    const allModals = document.querySelectorAll('.modal');
    allModals.forEach(modal => {
        modal.style.display = 'none';
    });
    
    document.getElementById('serviceSearch')?.addEventListener('input', filterServices);
    document.getElementById('customerSearch')?.addEventListener('input', filterCustomers);
    document.getElementById('staffSearch')?.addEventListener('input', filterStaff);

    getCurrentUserRole().then(() => {
        loadAppointments();
        loadStatistics(); 
        
        if (currentUserRole !== 'staff') {
            loadCustomers();
            loadServices();
            loadStaff();
            
            // SỬA: Lắng nghe sự kiện từ ID mới
            document.getElementById('filter-status-select')?.addEventListener('change', filterAppointments);
            document.getElementById('filter-date-select')?.addEventListener('change', filterAppointments);
        }
    });
    
    document.getElementById('appointmentForm')?.addEventListener('submit', async function(e) {
        e.preventDefault();
        await handleAppointmentSubmit(e);
    });
});

async function getCurrentUserRole() {
    try {
        const response = await fetch('/api/auth/profile', {
            headers: getAuthHeaders(false)
        });
        if (response.ok) {
            const data = await response.json();
            currentUserRole = data.role;
            
            if (currentUserRole === 'staff') {
                const addBtn = document.querySelector('button[onclick="openAddAppointmentModal()"]');
                const exportBtn = document.querySelector('button[onclick="exportAppointments()"]');
                if (addBtn) addBtn.style.display = 'none';
                if (exportBtn) exportBtn.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Lỗi lấy thông tin user:', error);
    }
}

// ========== HÀM HỖ TRỢ: CHUYỂN FILTER VALUE THÀNH DATE RANGE ==========
function getDateRangeFromFilter(filterValue) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    let startDate = null;
    let endDate = null;
    
    const formatDate = (date) => date.toISOString().split('T')[0];
    
    switch (filterValue) {
        case 'today':
            startDate = formatDate(today);
            endDate = formatDate(today);
            break;
        case 'this_week':
            const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday
            const startOfWeek = new Date(today);
            startOfWeek.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1)); // Bắt đầu từ Thứ Hai
            
            startDate = formatDate(startOfWeek);
            endDate = formatDate(today); // Kết thúc là ngày hiện tại
            break;
        case 'this_month':
            const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
            
            startDate = formatDate(startOfMonth);
            endDate = formatDate(today);
            break;
        case 'custom':
            // Xử lý tùy chỉnh (nếu có)
            break;
        default:
            // Tổng toàn bộ
            break;
    }
    
    return { start_date: startDate, end_date: endDate };
}


// ========== THỐNG KÊ ==========
async function loadStatistics() {
    try {
        // Lấy giá trị từ dropdown mới
        const filterDateSelect = document.getElementById('filter-date-select');
        const filterValue = filterDateSelect?.value; 
        const dateRange = getDateRangeFromFilter(filterValue);
        
        let url = '/api/admin/appointments/statistics';
        const params = new URLSearchParams();
        
        if (dateRange.start_date) params.append('start_date', dateRange.start_date);
        if (dateRange.end_date) params.append('end_date', dateRange.end_date); 
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url, {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.statistics) {
            displayStatistics(data.statistics);
        }
        
    } catch (error) {
        console.error('Lỗi tải thống kê:', error);
        // Reset các giá trị khi có lỗi
        document.getElementById('stat-total').textContent = 'N/A';
        document.getElementById('stat-confirmed').textContent = 'N/A';
        document.getElementById('stat-pending-total').textContent = 'N/A';
        document.getElementById('stat-revenue').textContent = formatCurrency(0);
    }
}

function displayStatistics(stats) {
    const totalApts = stats.total || 0;
    
    const confirmedApts = stats.confirmed || 0;

    const completedApts = stats.completed || 0;
    const cancelledApts = stats.cancelled || 0;
    const pendingTotalApts = totalApts - completedApts - cancelledApts;
    
    const expectedRevenue = stats.expected_revenue || 0; 
    
    if (document.getElementById('stat-total')) document.getElementById('stat-total').textContent = totalApts;
    if (document.getElementById('stat-confirmed')) document.getElementById('stat-confirmed').textContent = confirmedApts;
    if (document.getElementById('stat-pending-total')) document.getElementById('stat-pending-total').textContent = pendingTotalApts;
    if (document.getElementById('stat-revenue')) document.getElementById('stat-revenue').textContent = formatCurrency(expectedRevenue);
}

async function loadAppointments(filters = {}) {
    try {
        let url;
        let params = new URLSearchParams();
        
        // SỬA: Lấy filter date từ UI mới
        const filterDateSelect = document.getElementById('filter-date-select');
        const filterValue = filterDateSelect?.value;
        const dateRange = getDateRangeFromFilter(filterValue);
        
        if (currentUserRole === 'staff') {
            url = '/api/admin/my-schedule-list';
            const today = new Date().toISOString().split('T')[0];
            
            // Ưu tiên filter từ dropdown, nếu không có thì dùng today
            const startDate = filters.startDate || dateRange.start_date || today;
            const endDate = filters.endDate || dateRange.end_date || startDate; 
            
            params.append('start_date', startDate);
            params.append('end_date', endDate);
            
        } else {
            url = '/api/admin/appointments';
            
            // SỬA: Sử dụng dateRange cho cả start và end
            if (dateRange.start_date) params.append('start_date', dateRange.start_date);
            if (dateRange.end_date) params.append('end_date', dateRange.end_date); 
            
            // SỬA: Lấy filter status từ UI mới
            const status = document.getElementById('filter-status-select')?.value;
            if (status) params.append('status', status);
            // Giữ lại logic lọc từ filters object (nếu có gọi từ bên ngoài)
            if (filters.status) params.append('status', filters.status); 
        }
        
        if (params.toString()) {
            url += '?' + params.toString();
        }
        
        const response = await fetch(url, {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (currentUserRole === 'staff') {
            allAppointments = (data.success && Array.isArray(data.appointments)) ? data.appointments : [];
        } else {
            allAppointments = Array.isArray(data) ? data : (data.success && data.appointments ? data.appointments : []);
        }
        
        renderAppointmentsTable();
        renderPagination();
    } catch (error) {
        console.error('Lỗi tải lịch hẹn:', error);
        showError('Không thể tải danh sách lịch hẹn');
    }
}

async function loadCustomers() {
    try {
        const response = await fetch('/api/admin/customers/list', { headers: getAuthHeaders(false) });
        if (response.ok) {
            allCustomers = await response.json();
            renderCustomerList();
        }
    } catch (error) {
        console.error('Lỗi tải khách hàng:', error);
    }
}

function renderCustomerList() {
    const customerList = document.getElementById('customerList');
    if (!customerList) return;

    if (allCustomers.length === 0) {
        customerList.innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Không có khách hàng nào</div>';
        return;
    }
    
    customerList.innerHTML = allCustomers.map(customer => `
        <div class="service-item customer-item ${selectedCustomerId === customer.makh ? 'selected' : ''}" 
             data-makh="${customer.makh}" 
             onclick="toggleCustomer(${customer.makh}, '${customer.hoten}', '${customer.sdt}')">
            <span>${customer.hoten}</span>
            <span class="customer-sdt">${customer.sdt || 'N/A'}</span>
        </div>
    `).join('');
    
    if (selectedCustomerId !== null) {
        const initialCustomer = allCustomers.find(c => c.makh === selectedCustomerId);
        if (initialCustomer) {
             updateSelectedCustomer(initialCustomer.makh, initialCustomer.hoten, initialCustomer.sdt);
        }
    }
}

async function loadServices() {
    try {
        const response = await fetch('/api/admin/services', { headers: getAuthHeaders(false) });
        const data = await response.json();
        if (Array.isArray(data)) {
            allServices = data;
        } else if (data.success && Array.isArray(data.services)) {
            allServices = data.services;
        } else {
            allServices = [];
        }
        renderServiceList(); 
    } catch (error) {
        console.error('Lỗi tải dịch vụ:', error);
    }
}

async function loadStaff() {
    try {
        const response = await fetch('/api/admin/staff/list-all', { headers: getAuthHeaders(false) });
        const data = await response.json(); 
        allStaff = Array.isArray(data) ? data.filter(s => s.role === 'staff') : []; 
    } catch (error) {
        console.error('Lỗi tải nhân viên:', error);
        allStaff = [];
    }
}

async function loadAvailableStaff() {
    const date = document.getElementById('appointment-date').value;
    const time = document.getElementById('appointment-time').value;
    
    const staffList = document.getElementById('staffList');
    
    if (!date || !time) {
        staffList.innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Vui lòng chọn ngày và giờ</div>';
        return;
    }
    
    if (selectedServiceIds.length === 0) {
        staffList.innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Vui lòng chọn dịch vụ trước</div>';
        return;
    }
    
    staffList.innerHTML = '<div style="padding: 12px; color: #667eea; text-align: center;"><i class="fas fa-spinner fa-spin"></i> Đang kiểm tra nhân viên rảnh...</div>';
    
    try {
        const datetime = `${date}T${time}`;
        const params = new URLSearchParams({
            ngaygio: datetime,
            madv_list: selectedServiceIds.join(',')
        });
        
        // GỌI API MỚI ĐÃ THÊM Ở BACKEND
        const response = await fetch(`/api/admin/staff/available?${params}`, { 
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ msg: 'Lỗi không xác định' }));
            // SỬA THÔNG BÁO LỖI để không báo "API chưa có" nữa
            throw new Error(`Không thể tải danh sách nhân viên: ${errorData.msg || response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success && Array.isArray(data.available_staff)) {
            availableStaff = data.available_staff;
        } else if (Array.isArray(data)) {
            availableStaff = data;
        } else {
            availableStaff = [];
        }
        
        renderStaffList();
        
    } catch (error) {
        console.error('Lỗi tải nhân viên rảnh:', error);
        staffList.innerHTML = `<div style="padding: 12px; color: #ef4444; text-align: center;"><i class="fas fa-exclamation-circle"></i> Lỗi: ${error.message}</div>`;
    }
}

function renderStaffList() {
    const staffList = document.getElementById('staffList');
    if (!staffList) return;
    
    if (availableStaff.length === 0) {
        staffList.innerHTML = '<div style="padding: 12px; color: #ef4444; text-align: center;"><i class="fas fa-exclamation-circle"></i> Không có nhân viên rảnh tại thời điểm này</div>';
        return;
    }
    
    staffList.innerHTML = availableStaff.map(staff => `
        <div class="service-item staff-item ${selectedStaffId === staff.manv ? 'selected' : ''}" 
             data-manv="${staff.manv}" 
             onclick="toggleStaff(${staff.manv}, '${staff.hoten}', '${staff.chuyenmon || 'Nhân viên'}')">
            <span>${staff.hoten}</span>
            <span class="service-duration">${staff.chuyenmon || 'Nhân viên'}</span>
        </div>
    `).join('');
    
    if (selectedStaffId !== null) {
        const selected = availableStaff.find(s => s.manv === selectedStaffId);
        if (selected) {
            updateSelectedStaff(selected.manv, selected.hoten, selected.chuyenmon);
        }
    }
}

function toggleStaff(manv, hoten, chuyenmon) {
    if (selectedStaffId === manv) {
        selectedStaffId = null;
    } else {
        selectedStaffId = manv;
    }

    document.querySelectorAll('.staff-item').forEach(item => {
        item.classList.remove('selected');
    });

    if (selectedStaffId !== null) {
        document.querySelector(`.staff-item[data-manv="${selectedStaffId}"]`)?.classList.add('selected');
    }

    updateSelectedStaff(manv, hoten, chuyenmon);
}

function updateSelectedStaff(manv, hoten, chuyenmon) {
    const container = document.getElementById('selectedStaff');
    const inputHidden = document.getElementById('staff-id');
    if (!container || !inputHidden) return;

    if (selectedStaffId === null) {
        container.innerHTML = '<span class="empty-selection">Chưa chọn nhân viên (Tự động sắp xếp)</span>';
        inputHidden.value = '';
    } else {
        container.innerHTML = `
            <div class="service-tag staff-tag">
                <span>${hoten} - ${chuyenmon || 'Nhân viên'}</span>
                <button type="button" onclick="removeSelectedStaff()">×</button>
            </div>
        `;
        inputHidden.value = manv;
    }
}

function removeSelectedStaff() {
    selectedStaffId = null;
    updateSelectedStaff(null, '', '');
    document.querySelectorAll('.staff-item').forEach(item => item.classList.remove('selected'));
}

function filterStaff() {
    const searchText = document.getElementById('staffSearch').value.toLowerCase();
    const staffList = document.getElementById('staffList');
    if (!staffList) return;
    
    const items = staffList.querySelectorAll('.staff-item');
    
    items.forEach(item => {
        const nameText = item.querySelector('span:first-child')?.textContent.toLowerCase() || '';
        const typeText = item.querySelector('.service-duration')?.textContent.toLowerCase() || '';
        
        if (nameText.includes(searchText) || typeText.includes(searchText)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}



function renderServiceList() {
    const serviceList = document.getElementById('serviceList');
    if (!serviceList) return;
    
    if (allServices.length === 0) {
        serviceList.innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Chưa có dịch vụ nào</div>';
        return;
    }
    
    serviceList.innerHTML = allServices.map(service => `
        <div class="service-item ${selectedServiceIds.includes(service.madv) ? 'selected' : ''}" 
             data-madv="${service.madv}" 
             onclick="toggleService(${service.madv})">
            <input type="checkbox" id="service-checkbox-${service.madv}" value="${service.madv}" ${selectedServiceIds.includes(service.madv) ? 'checked' : ''}>
            <label for="service-checkbox-${service.madv}">
                <span>${service.tendv}</span>
                <span class="service-duration">${service.thoiluong || 60} phút</span>
            </label>
        </div>
    `).join('');
}

function toggleService(serviceId) {
    const checkbox = document.getElementById(`service-checkbox-${serviceId}`);
    if (checkbox) checkbox.checked = !checkbox.checked; 

    if (checkbox.checked) {
        if (!selectedServiceIds.includes(serviceId)) {
            selectedServiceIds.push(serviceId);
        }
    } else {
        selectedServiceIds = selectedServiceIds.filter(id => id !== serviceId);
    }
    
    updateSelectedServices();
    updateServiceItemStyles();
    loadAvailableStaff();
}

function updateSelectedServices() {
    const container = document.getElementById('selectedServices');
    if (!container) return;
    
    if (selectedServiceIds.length === 0) {
        container.innerHTML = '<span class="empty-selection">Chưa chọn dịch vụ nào</span>';
        return;
    }
    
    container.innerHTML = selectedServiceIds.map(id => {
        const service = allServices.find(s => s.madv === id);
        if (!service) return '';
        return `
            <div class="service-tag">
                <span>${service.tendv}</span>
                <button type="button" onclick="removeService(${id})">×</button>
            </div>
        `;
    }).join('');
}

function removeService(serviceId) {
    selectedServiceIds = selectedServiceIds.filter(id => id !== serviceId);
    const checkbox = document.getElementById(`service-checkbox-${serviceId}`);
    if (checkbox) checkbox.checked = false;
    updateSelectedServices();
    updateServiceItemStyles();
    loadAvailableStaff();
}

function updateServiceItemStyles() {
    allServices.forEach(service => {
        const item = document.querySelector(`.service-item[data-madv="${service.madv}"]`);
        if (item) {
            if (selectedServiceIds.includes(service.madv)) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        }
    });
}

function filterServices() {
    const searchText = document.getElementById('serviceSearch').value.toLowerCase();
    const serviceList = document.getElementById('serviceList');
    if (!serviceList) return;
    
    const items = serviceList.querySelectorAll('.service-item');
    
    items.forEach(item => {
        const text = item.querySelector('label span:first-child')?.textContent.toLowerCase() || '';
        if (text.includes(searchText)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function toggleCustomer(makh, hoten, sdt) {
    if (selectedCustomerId === makh) {
        selectedCustomerId = null;
    } else {
        selectedCustomerId = makh;
    }

    document.querySelectorAll('.customer-item').forEach(item => {
        item.classList.remove('selected');
    });

    if (selectedCustomerId !== null) {
        document.querySelector(`.customer-item[data-makh="${selectedCustomerId}"]`)?.classList.add('selected');
    }

    updateSelectedCustomer(makh, hoten, sdt);
}

function updateSelectedCustomer(makh, hoten, sdt) {
    const container = document.getElementById('selectedCustomer');
    const inputHidden = document.getElementById('customer-id');
    if (!container || !inputHidden) return;

    if (selectedCustomerId === null) {
        container.innerHTML = '<span class="empty-selection">Chưa chọn khách hàng nào</span>';
        inputHidden.value = '';
    } else {
        container.innerHTML = `
            <div class="service-tag customer-tag">
                <span>${hoten} - ${sdt}</span>
                <button type="button" onclick="removeSelectedCustomer()">×</button>
            </div>
        `;
        inputHidden.value = makh;
    }
}

function removeSelectedCustomer() {
    selectedCustomerId = null;
    updateSelectedCustomer(null, '', '');
    document.querySelectorAll('.customer-item').forEach(item => item.classList.remove('selected'));
}

function filterCustomers() {
    const searchText = document.getElementById('customerSearch').value.toLowerCase();
    const customerList = document.getElementById('customerList');
    if (!customerList) return;
    
    const items = customerList.querySelectorAll('.customer-item');
    
    items.forEach(item => {
        const nameText = item.querySelector('span:first-child')?.textContent.toLowerCase() || '';
        const sdtText = item.querySelector('.customer-sdt')?.textContent.toLowerCase() || '';
        
        if (nameText.includes(searchText) || sdtText.includes(searchText)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}


function renderAppointmentsTable() {
    const tbody = document.querySelector('#appointments-table tbody');
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedData = allAppointments.slice(startIndex, startIndex + itemsPerPage);
    
    if (paginatedData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">Không có lịch hẹn nào</td></tr>';
        return;
    }
    
    tbody.innerHTML = paginatedData.map(apt => {
        let serviceName = apt.dichvu_ten || 'N/A';
        let customerName = apt.khachhang_hoten || 'N/A';
        let staffName = apt.nhanvien_hoten || 'Chưa gán';
        const canEdit = currentUserRole !== 'staff';
        
        return `
            <tr>
                <td class="d-none">#${apt.malh}</td>
                <td>${formatDateTime(apt.ngaygio)}</td>
                <td>${customerName}</td>
                <td>${serviceName}</td>
                <td>${staffName}</td>
                <td><span class="badge badge-${getStatusClass(apt.trangthai)}">${getAppointmentStatusText(apt.trangthai)}</span></td>
                <td class="d-none">${apt.ghichu || ''}</td>
                <td class="action-buttons">
                    ${canEdit ? `
                        <button class="btn btn-info btn-sm" onclick="viewAppointmentDetail(${apt.malh})" title="Xem chi tiết">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${(apt.trangthai === 'Chờ xác nhận' || apt.trangthai === 'pending') ? `
                            <button class="btn btn-success btn-sm" onclick="confirmAppointment(${apt.malh})" title="Xác nhận">
                                <i class="fas fa-check"></i>
                            </button>
                        ` : ''}
                        ${(apt.trangthai === 'Đã xác nhận' || apt.trangthai === 'confirmed') ? `
                            <button class="btn btn-primary btn-sm" onclick="completeAppointment(${apt.malh})" title="Hoàn thành">
                                <i class="fas fa-check-double"></i>
                            </button>
                        ` : ''}
                        ${(apt.trangthai !== 'Đã hoàn thành' && apt.trangthai !== 'Đã hủy' && apt.trangthai !== 'completed' && apt.trangthai !== 'cancelled') ? `
                            <button class="btn btn-danger btn-sm" onclick="cancelAppointment(${apt.malh})" title="Hủy">
                                <i class="fas fa-times"></i>
                            </button>
                        ` : ''}
                        ${(apt.trangthai === 'Đã hoàn thành' || apt.trangthai === 'completed') ? `
                            <button class="btn btn-warning btn-sm" onclick="createInvoiceForAppointment(${apt.malh})" title="Tạo hóa đơn">
                                <i class="fas fa-file-invoice-dollar"></i>
                            </button>
                        ` : ''}
                    ` : `
                        <button class="btn btn-info btn-sm" onclick="viewAppointmentDetail(${apt.malh})" title="Xem chi tiết">
                            <i class="fas fa-eye"></i>
                        </button>
                    `}
                </td>
            </tr>
        `;
    }).join('');
}

function renderPagination() {
    const totalPages = Math.ceil(allAppointments.length / itemsPerPage);
    const paginationDiv = document.getElementById('pagination');
    
    if (!paginationDiv || totalPages <= 1) {
        if (paginationDiv) paginationDiv.innerHTML = '';
        return;
    }
    
    let html = '<div class="pagination-controls">';
    html += `<button class="btn btn-sm ${currentPage === 1 ? 'disabled' : ''}" 
             onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
             <i class="fas fa-chevron-left"></i></button>`;
    
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button class="btn btn-sm ${i === currentPage ? 'btn-primary' : 'btn-secondary'}" 
                     onclick="changePage(${i})">${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span>...</span>';
        }
    }
    
    html += `<button class="btn btn-sm ${currentPage === totalPages ? 'disabled' : ''}" 
             onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
             <i class="fas fa-chevron-right"></i></button>`;
    
    html += '</div>';
    paginationDiv.innerHTML = html;
}

function changePage(page) {
    const totalPages = Math.ceil(allAppointments.length / itemsPerPage);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderAppointmentsTable();
    renderPagination();
}

function filterAppointments() {
    // SỬA: Lấy giá trị từ dropdown mới
    const dateValue = document.getElementById('filter-date-select').value;
    const status = document.getElementById('filter-status-select').value;
    
    const filters = {};
    if (status) filters.status = status;
    
    currentPage = 1;
    loadAppointments(filters); 
    loadStatistics(); 
}

function resetFilters() {
    document.getElementById('filter-date-select').value = ''; 
    document.getElementById('filter-status-select').value = '';
    
    document.getElementById('search-input').value = '';
    document.querySelector('.search-clear')?.classList.remove('active');
    
    currentPage = 1;
    loadAppointments();
    loadStatistics(); 
}

function openAddAppointmentModal() {
    document.getElementById('modal-title').innerHTML = '<i class="fas fa-calendar-plus"></i> Tạo lịch hẹn mới';
    document.getElementById('appointmentForm').reset();
    document.getElementById('appointment-id').value = '';
    
    selectedServiceIds = [];
    selectedCustomerId = null;
    selectedStaffId = null;
    availableStaff = [];
    
    updateSelectedServices();
    updateSelectedCustomer(null, '', '');
    updateSelectedStaff(null, '', '');
    
    renderServiceList();
    renderCustomerList();
    
    document.getElementById('staffList').innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Vui lòng chọn ngày, giờ và dịch vụ để xem nhân viên rảnh</div>';

    const today = new Date().toISOString().split('T')[0];
    document.getElementById('appointment-date').value = today;
    
    document.getElementById('appointmentModal').style.display = 'flex';
}

function closeAppointmentModal() {
    document.getElementById('appointmentModal').style.display = 'none';
}

async function handleAppointmentSubmit(e) {
    const malh = document.getElementById('appointment-id').value;
    const makh = document.getElementById('customer-id').value;
    const manv = document.getElementById('staff-id').value;
    const ngay = document.getElementById('appointment-date').value;
    const gio = document.getElementById('appointment-time').value;

    if (!makh) {
        showError('Vui lòng chọn Khách hàng!');
        return;
    }
    
    if (selectedServiceIds.length === 0) {
        showError('Vui lòng chọn ít nhất một Dịch vụ!');
        return;
    }
    
    const madv_list = selectedServiceIds;
    const ngaygio = `${ngay}T${gio}`;

    const url = malh ? `/api/admin/appointments/${malh}` : '/api/admin/appointments';
    const method = malh ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: getAuthHeaders(),
            body: JSON.stringify({
                makh: parseInt(makh),
                madv_list: madv_list,
                manv: manv ? parseInt(manv) : null,
                ngaygio: ngaygio,
                ghichu: document.getElementById('appointment-note')?.value || ''
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.msg || 'Lưu lịch hẹn thành công!');
            closeAppointmentModal();
            loadAppointments();
            loadStatistics(); 
        } else {
            if (response.status === 409 && data.conflicts) {
                 const conflictMsg = data.conflicts.map(c => 
                     ` - ${c.ngaygio} - ${c.ketthuc}: ${c.dichvu} (${c.khachhang})`
                 ).join('\n');
                 showError(`${data.msg}\nCác lịch hẹn xung đột:\n${conflictMsg}`);
            } else {
                showError(data.msg || 'Thao tác lịch hẹn thất bại');
            }
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra khi lưu lịch hẹn');
    }
}

async function viewAppointmentDetail(malh) {
    try {
        const response = await fetch(`/api/admin/appointments/${malh}`, { headers: getAuthHeaders(false) });
        if (!response.ok) { throw new Error('Không thể tải chi tiết lịch hẹn'); }
        const data = await response.json();
        if (data.success && data.appointment) {
            populateAndShowDetailModal(data.appointment);
        } else {
            showError(data.msg || 'Không tìm thấy lịch hẹn');
        }
    } catch (error) {
        console.error('Lỗi xem chi tiết:', error);
        showError(error.message);
    }
}

function populateAndShowDetailModal(apt) {
    const modal = document.getElementById('appointmentDetailModal');
    if (!modal) { showError('Lỗi: Không tìm thấy #appointmentDetailModal trong HTML.'); return; }

    document.getElementById('detail-customer-name').textContent = apt.khachhang ? apt.khachhang.hoten : 'N/A';
    document.getElementById('detail-customer-phone').textContent = apt.khachhang ? apt.khachhang.sdt : 'N/A';
    document.getElementById('detail-apt-id').textContent = `#${apt.malh}`;
    document.getElementById('detail-apt-time').textContent = formatDateTime(apt.ngaygio);
    document.getElementById('detail-apt-staff').textContent = apt.nhanvien ? apt.nhanvien.hoten : 'Chưa gán';
    document.getElementById('detail-apt-status').innerHTML = `<span class="badge badge-${getStatusClass(apt.trangthai)}">${getAppointmentStatusText(apt.trangthai)}</span>`;
    document.getElementById('detail-apt-notes').textContent = apt.ghichu || 'Không có ghi chú';

    const servicesList = document.getElementById('detail-services-list');
    if (apt.services && apt.services.length > 0) {
        servicesList.innerHTML = apt.services.map(s => `
            <li><span>${s.tendv}</span><span>${formatCurrency(s.gia)}</span></li>
        `).join('');
    } else {
        servicesList.innerHTML = '<li>Không có dịch vụ</li>';
    }
    modal.style.display = 'flex';
}

function closeDetailModal() {
    document.getElementById('appointmentDetailModal').style.display = 'none';
}

async function confirmAppointment(malh) {
    showConfirm('Xác nhận lịch hẹn', 'Bạn có chắc muốn xác nhận lịch hẹn này?', async () => {
        try {
            const response = await fetch(`/api/admin/appointments/${malh}/confirm`, { method: 'POST', headers: getAuthHeaders() });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Xác nhận lịch hẹn thành công');
                loadAppointments();
                loadStatistics();
            } else {
                showError(data.msg || 'Xác nhận lịch hẹn thất bại');
            }
        } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra'); }
    });
}

async function completeAppointment(malh) {
    showConfirm('Hoàn thành lịch hẹn', 'Xác nhận lịch hẹn đã hoàn thành?', async () => {
        try {
            const response = await fetch(`/api/admin/appointments/${malh}/complete`, { method: 'POST', headers: getAuthHeaders() });
            
            let data;
            try { data = await response.json(); } 
            catch (jsonError) {
                if (!response.ok) { showError(`Lỗi API không xác định (HTTP ${response.status})`); return; }
                data = { success: true, msg: 'Đã đánh dấu hoàn thành' };
            }

            if (response.ok && data.success) {
                showSuccess(data.msg || 'Đã đánh dấu hoàn thành');
                loadAppointments();
                loadStatistics();
                
                showConfirm(
                    'Tạo hóa đơn', 
                    'Lịch hẹn đã hoàn thành. Bạn có muốn tạo hóa đơn ngay không?',
                    () => createInvoiceForAppointment(malh), 
                    null, 
                    'Tạo hóa đơn'
                );
            } else {
                showError(data.msg || 'Cập nhật thất bại');
            }
        } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra'); }
    });
}

async function cancelAppointment(malh) {
    const reason = prompt('Lý do hủy lịch hẹn:');
    if (reason === null) return;
    
    try {
        const response = await fetch(`/api/admin/appointments/${malh}/cancel`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ reason: reason }) });
        const data = await response.json();
        if (response.ok) {
            showSuccess(data.msg || 'Hủy lịch hẹn thành công');
            loadAppointments();
            loadStatistics();
        } else {
            showError(data.msg || 'Hủy lịch hẹn thất bại');
        }
    } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra'); }
}



async function createInvoiceForAppointment(appointmentId) {
    try {
        const response = await fetch(`/api/admin/appointments/${appointmentId}/create-invoice`, { method: 'POST', headers: getAuthHeaders() });
        const data = await response.json();
        
        if (response.ok && data.invoice_id) {
            showSuccess(data.msg || 'Tạo hóa đơn thành công!');
            openPaymentSelectionModal(data.invoice_id);
        } else {
            showError(data.msg || 'Tạo hóa đơn thất bại');
        }
    } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra khi tạo hóa đơn'); }
}

function openPaymentSelectionModal(invoiceId) {
    currentInvoiceId = invoiceId;
    
    fetch(`/api/admin/invoices/${invoiceId}`, { headers: getAuthHeaders(false) })
        .then(res => res.json())
        .then(invoice => {
            if (!invoice || !invoice.tongtien) throw new Error("Invalid invoice data");
            const totalAmount = invoice.tongtien;
            
            const modalHtml = `
                <div id="paymentModal-${invoiceId}" class="modal show" style="display: grid !important; place-items: center;">
                    <div class="modal-content modal-sm">
                        <div class="modal-header" style="padding: 15px 25px;">
                            <h3 style="margin:0; font-size: 18px;"><i class="fas fa-credit-card"></i> Thanh toán</h3>
                            <button class="close" onclick="closeModal('paymentModal-${invoiceId}')">&times;</button>
                        </div>
                        <div class="modal-body" style="padding: 20px 25px;">
                            <div class="info-card" style="text-align: center; margin-bottom: 25px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                                <h6 style="color: #666; margin-bottom: 5px;">TỔNG TIỀN CẦN THANH TOÁN</h6>
                                <h3 style="color: #10b981; font-size: 24px;">${formatCurrency(totalAmount)}</h3>
                            </div>
                            <h5 style="text-align: center; margin: 15px 0 20px 0; color: #333; font-weight: 600;">Chọn phương thức thanh toán:</h5>
                            <div class="payment-options" style="display: flex; gap: 15px; justify-content: center;">
                                <div class="payment-option cash" onclick="openCashPaymentModal(${invoiceId}, ${totalAmount})">
                                    <i class="fas fa-money-bill-wave"></i><h4>Tiền mặt</h4><p>Nhận tiền trực tiếp</p>
                                </div>
                                <div class="payment-option qr" onclick="generateMomoQrCode(${invoiceId})">
                                    <i class="fas fa-qrcode"></i><h4>QR Code</h4><p>Quét mã Momo</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            document.body.style.overflow = 'hidden';
            const modal = document.getElementById(`paymentModal-${invoiceId}`);
            modal.addEventListener('click', function(e) { if (e.target === this) closeModal(`paymentModal-${invoiceId}`); });
        })
        .catch(error => { console.error('Lỗi lấy tổng tiền:', error); showError('Không thể lấy tổng tiền hóa đơn'); });
}

function openCashPaymentModal(invoiceId, totalAmount) {
    closeModal(`paymentModal-${invoiceId}`);
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
                            <input type="number" id="amountPaid" class="form-control" placeholder="Nhập số tiền..." required min="${totalAmountFloat}">
                        </div>
                        <div class="form-group" style="margin-bottom: 25px;">
                            <label for="changeAmount" style="font-weight: 600;">Tiền thối lại</label>
                            <input type="text" id="changeAmount" class="form-control" readonly value="${formatCurrency(0)}" style="background: #f3f4f6; color: #e11d48; font-weight: bold;">
                        </div>
                        <div class="btn-group" style="display: flex; justify-content: flex-end; gap: 10px;">
                            <button type="button" class="btn btn-secondary" onclick="closeModal('cashPaymentModal')">Hủy</button>
                            <button type="submit" class="btn btn-primary" id="confirmCashBtn"><i class="fas fa-check"></i> Xác nhận</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', cashModalHtml);
    const modal = document.getElementById('cashPaymentModal');
    if (modal) {
        modal.style.display = 'grid'; modal.style.placeItems = 'center'; document.body.style.overflow = 'hidden';
        modal.addEventListener('click', function(e) { if (e.target === this) closeModal('cashPaymentModal'); });
    }

    const inputPaid = document.getElementById('amountPaid');
    const inputChange = document.getElementById('changeAmount');
    
    inputPaid.addEventListener('input', function() {
        const paid = parseFloat(this.value);
        if (isNaN(paid) || paid < totalAmountFloat) { inputChange.value = formatCurrency(0); document.getElementById('confirmCashBtn').disabled = true; return; }
        const change = paid - totalAmountFloat;
        inputChange.value = formatCurrency(change); document.getElementById('confirmCashBtn').disabled = false;
    });
    
    document.getElementById('confirmCashBtn').disabled = true; 
}

async function handleCashPaymentSubmit(invoiceId, totalAmount) {
    const amountPaid = document.getElementById('amountPaid').value;
    const amountPaidFloat = parseFloat(amountPaid);
    
    if (amountPaidFloat < parseFloat(totalAmount)) { showError('Số tiền khách trả không đủ!'); return; }
    
    try {
        const response = await fetch(`/api/admin/invoices/${invoiceId}/record-payment`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ sotien: amountPaidFloat, phuongthuc: 'Tiền mặt' }) });
        const data = await response.json();
        
        if (response.ok) {
            const change = amountPaidFloat - parseFloat(totalAmount);
            showSuccess(`Thanh toán thành công! Tiền thối: ${formatCurrency(change)}`);
            closeModal('cashPaymentModal');
            loadAppointments(); 
        } else {
            showError(data.msg || 'Ghi nhận thanh toán thất bại');
        }

    } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra khi ghi nhận tiền mặt'); }
}

async function generateMomoQrCode(invoiceId) {
    closeModal(`paymentModal-${invoiceId}`);
    
    const qrModalHtml = `
        <div id="qrCodeModal" class="modal show" style="display: grid !important; place-items: center;">
            <div class="modal-content modal-sm">
                <div class="modal-header">
                    <h3><i class="fas fa-qrcode"></i> Quét mã QR Momo</h3>
                    <button class="close" onclick="closeQRModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="qr-code-container">
                        <div class="text-center"><i class="fas fa-spinner fa-spin"></i><p>Đang tạo mã QR...</p></div>
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
    modal.addEventListener('click', function(e) { if (e.target === this) closeQRModal(); });

    try {
        const response = await fetch(`/api/admin/invoices/${invoiceId}/generate-qr`, { method: 'POST', headers: getAuthHeaders() });
        const data = await response.json();
        
        if (response.ok && data.qrCodeUrl) {
            const qrContainer = document.getElementById('qr-code-container');
            qrContainer.innerHTML = '';
            
            const qrDiv = document.createElement('div');
            qrDiv.id = `qrcode-canvas-${invoiceId}`;
            qrDiv.style.margin = '20px auto';
            qrContainer.appendChild(qrDiv);
            
            if (typeof QRCode !== 'undefined') { new QRCode(qrDiv, { text: data.qrCodeUrl, width: 250, height: 250, colorDark: "#000000", colorLight: "#ffffff", correctLevel: QRCode.CorrectLevel.H });
            } else { qrContainer.innerHTML = `<p style="color:red;">Lỗi: Thư viện QRCode không tải được.</p>`; throw new Error('Thư viện QRCode chưa được load'); }
            
            qrContainer.insertAdjacentHTML('beforeend', `<div class="qr-instructions" style="text-align: left; margin-top: 20px; border-top: 1px solid #eee; padding-top: 15px;"><p style="margin-bottom: 5px; font-weight: 600;"><i class="fas fa-mobile-alt" style="color: #667eea; width: 20px;"></i> Bước 1: Mở ứng dụng Momo</p><p style="margin-bottom: 5px; font-weight: 600;"><i class="fas fa-qrcode" style="color: #667eea; width: 20px;"></i> Bước 2: Quét mã QR phía trên</p><p style="margin-bottom: 5px; font-weight: 600;"><i class="fas fa-check-circle" style="color: #667eea; width: 20px;"></i> Bước 3: Xác nhận thanh toán</p></div><div id="payment-status" style="text-align: center; margin-top: 20px; font-weight: 600; color: #667eea;"><i class="fas fa-spinner fa-spin"></i> Đang chờ thanh toán...</div>`);
            
            showSuccess("Mã QR đã được tạo thành công!");
            startPaymentPolling(invoiceId);
            
        } else { throw new Error(data.msg || 'Không thể tạo mã QR'); }

    } catch (error) { console.error('Lỗi:', error); document.getElementById('qr-code-container').innerHTML = `<div class="alert alert-danger"><i class="fas fa-times-circle"></i> ${error.message || 'Lỗi kết nối'}</div>`; showError(error.message || 'Không thể tạo mã QR'); }
}

async function startPaymentPolling(invoiceId) {
    pollingAttempts = 0;
    
    window.paymentPollingInterval = setInterval(async () => {
        pollingAttempts++;
        
        try {
            const response = await fetch(`/api/admin/invoices/${invoiceId}`, { headers: getAuthHeaders(false) });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.trangthai === 'Đã thanh toán') {
                    clearInterval(window.paymentPollingInterval);
                    const statusDiv = document.getElementById('payment-status');
                    if (statusDiv) { statusDiv.innerHTML = `<i class="fas fa-check-circle" style="color: #10b981; font-size: 28px;"></i> <p style="color: #10b981; font-weight: bold; margin-top: 10px; font-size: 16px;">Thanh toán thành công!</p>`; }
                    
                    showSuccess('Thanh toán Momo thành công!');
                    
                    setTimeout(() => { closeQRModal(); loadAppointments(); }, 2000);
                }
            }
            
            if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
                clearInterval(window.paymentPollingInterval);
                const statusDiv = document.getElementById('payment-status');
                if (statusDiv) { statusDiv.innerHTML = `<i class="fas fa-clock" style="color: #f59e0b; font-size: 24px;"></i> <p style="color: #f59e0b;">Quá thời gian chờ</p>`; }
            }
            
        } catch (error) { console.error('Lỗi polling:', error); }
        
    }, 3000);
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove(); 
            document.body.style.overflow = 'auto';
        }, 300);
    }
}

function closeQRModal() {
    const modal = document.getElementById('qrCodeModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => { modal.remove(); document.body.style.overflow = 'auto'; }, 300);
    }
    if (window.paymentPollingInterval) { clearInterval(window.paymentPollingInterval); window.paymentPollingInterval = null; }
}


function getAuthHeaders(includeContentType = true) {
    const token = localStorage.getItem('admin_token') || localStorage.getItem('access_token');
    const headers = {};
    if (includeContentType) { headers['Content-Type'] = 'application/json'; }
    if (token) { headers['Authorization'] = `Bearer ${token}`; }
    return headers;
}

function formatDateTime(dateTimeString) {
    if (!dateTimeString) return 'N/A';
    const date = new Date(dateTimeString);
    return date.toLocaleString('vi-VN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function formatCurrency(amount) {
    if (!amount) return '0₫';
    // Đảm bảo xử lý số float đúng cách
    const numberAmount = parseFloat(amount);
    if (isNaN(numberAmount)) return 'N/A';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(numberAmount);
}

function getAppointmentStatusText(status) {
    const statusMap = {
        'pending': 'Chờ xác nhận', 'Chờ xác nhận': 'Chờ xác nhận', 'confirmed': 'Đã xác nhận', 'Đã xác nhận': 'Đã xác nhận', 'in_progress': 'Đang thực hiện',
        'completed': 'Đã hoàn thành', 'Đã hoàn thành': 'Đã hoàn thành', 'cancelled': 'Đã hủy', 'Đã hủy': 'Đã hủy'
    };
    return statusMap[status] || status;
}

function getStatusClass(status) {
    const classMap = {
        'pending': 'warning', 'Chờ xác nhận': 'warning', 'confirmed': 'info', 'Đã xác nhận': 'info', 'in_progress': 'primary',
        'completed': 'success', 'Đã hoàn thành': 'success', 'cancelled': 'danger', 'Đã hủy': 'danger'
    };
    return classMap[status] || 'secondary';
}

function showToast(message, type = 'success') {
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) { toastContainer = document.createElement('div'); toastContainer.id = 'toast-container'; document.body.appendChild(toastContainer); }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`; 
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `<i class="fas ${iconClass}"></i> ${message}`;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.classList.add('show'); }, 100);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => { if (toast && toast.parentNode) { toast.parentNode.removeChild(toast); } }, 500); }, 3000);
}

function showSuccess(message) { showToast(message, 'success'); }
function showError(message) { showToast(message, 'error'); }

function showConfirm(title, message, onConfirm, onCancel = null, confirmText = 'OK', cancelText = 'Hủy') {
    const oldModal = document.getElementById('confirm-toast-modal');
    if (oldModal) oldModal.remove();
    const modalHtml = `<div id="confirm-toast-modal"><div class="confirm-toast-content"><div class="confirm-toast-header"><i class="fas fa-exclamation-triangle"></i><h4>${title}</h4></div><div class="confirm-toast-body">${message}</div><div class="confirm-toast-actions"><button type="button" class="btn btn-secondary" id="confirm-btn-cancel">${cancelText}</button><button type="button" class="btn btn-primary" id="confirm-btn-ok">${confirmText}</button></div></div></div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = document.getElementById('confirm-toast-modal');
    const closeMod = () => { modal.classList.remove('show'); setTimeout(() => { modal.remove(); }, 200); };
    document.getElementById('confirm-btn-ok').onclick = function() { onConfirm(); closeMod(); };
    document.getElementById('confirm-btn-cancel').onclick = function() { if (onCancel) { onCancel(); } closeMod(); };
    setTimeout(() => { modal.classList.add('show'); }, 10);
}

function exportAppointments() { showError('Chức năng xuất Excel đang được phát triển'); }

// HÀM SEARCH LỊCH HẸN
function searchAppointments() {
    const searchText = document.getElementById('search-input').value.toLowerCase();
    const clearBtn = document.querySelector('.search-clear');
    
    if (searchText.length > 0) {
        clearBtn.classList.add('active');
    } else {
        clearBtn.classList.remove('active');
    }

    const filteredAppointments = allAppointments.filter(apt => {
        const customerName = (apt.khachhang_hoten || '').toLowerCase();
        const appointmentId = (apt.malh || '').toString().toLowerCase();
        
        return customerName.includes(searchText) || appointmentId.includes(searchText);
    });

    const originalAppointments = allAppointments; // Lưu trữ danh sách gốc
    allAppointments = filteredAppointments;
    currentPage = 1;
    renderAppointmentsTable();
    renderPagination();
    allAppointments = originalAppointments; 
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    document.querySelector('.search-clear').classList.remove('active');
    filterAppointments(); 
}