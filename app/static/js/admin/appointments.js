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
let appointmentSearchText = '';

let selectedServiceIds = []; 
let selectedCustomerId = null;
let selectedStaffId = null;
let customerTreatments = [];
let selectedPackageItems = new Map(); // One exact entitlement per service in this appointment.
let bookingServiceMethod = 'regular';
let treatmentLoadVersion = 0;
let treatmentLoadState = 'idle';
let treatmentLoadError = '';
let appointmentSubmitting = false;


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
            
            // Select ngày/trạng thái đã có onchange trong template; chỉ bổ sung phím Enter.
            document.getElementById('filter-start-date')?.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') applyCustomDateFilter();
            });
            document.getElementById('filter-end-date')?.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') applyCustomDateFilter();
            });
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

// ========== HÀM HỖ TRỢ ĐỊNH DẠNG DATE LOCAL YYYY-MM-DD ==========
function formatLocalDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// ========== HÀM HỖ TRỢ DUY NHẤT: LẤY DATE RANGE HIỆN TẠI TỪ BỘ LỌC ==========
function getActiveDateRange() {
    const filterDateSelect = document.getElementById('filter-date-select');
    const filterValue = filterDateSelect ? filterDateSelect.value : '';

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let startDate = null;
    let endDate = null;

    switch (filterValue) {
        case 'today':
            startDate = formatLocalDate(today);
            endDate = formatLocalDate(today);
            break;
        case 'this_week': {
            const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday
            const startOfWeek = new Date(today);
            startOfWeek.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1)); // Thứ Hai
            startDate = formatLocalDate(startOfWeek);
            endDate = formatLocalDate(today);
            break;
        }
        case 'this_month': {
            const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
            startDate = formatLocalDate(startOfMonth);
            endDate = formatLocalDate(today);
            break;
        }
        case 'custom': {
            const startInput = document.getElementById('filter-start-date');
            const endInput = document.getElementById('filter-end-date');
            const startVal = startInput ? startInput.value.trim() : '';
            let endVal = endInput ? endInput.value.trim() : '';

            if (!startVal) {
                showError('Vui lòng chọn ngày bắt đầu');
                return null;
            }

            if (!endVal) {
                endVal = startVal;
                if (endInput) endInput.value = startVal;
            } else if (endVal < startVal) {
                showError('Ngày kết thúc không được nhỏ hơn ngày bắt đầu');
                return null;
            }

            startDate = startVal;
            endDate = endVal;
            break;
        }
        default:
            // Tổng toàn bộ: startDate = null, endDate = null
            break;
    }

    return { start_date: startDate, end_date: endDate };
}

function getDateRangeFromFilter(filterValue) {
    return getActiveDateRange();
}

// ========== XỬ LÝ KHI THAY ĐỔI DROPDOWN BỘ LỌC NGÀY ==========
function handleDateSelectChange() {
    const filterDateSelect = document.getElementById('filter-date-select');
    const customContainer = document.getElementById('custom-date-filter');
    const filterValue = filterDateSelect ? filterDateSelect.value : '';

    if (filterValue === 'custom') {
        if (customContainer) {
            customContainer.classList.remove('d-none');
            const startInput = document.getElementById('filter-start-date');
            if (startInput) startInput.focus();
        }
        // Chưa filter ngay khi chọn custom, chờ người dùng chọn ngày và bấm "Lọc"
        return;
    }

    // Nếu chọn các tùy chọn định sẵn (Tổng toàn bộ, Hôm nay, Tuần này, Tháng này):
    if (customContainer) {
        customContainer.classList.add('d-none');
        const startInput = document.getElementById('filter-start-date');
        const endInput = document.getElementById('filter-end-date');
        if (startInput) startInput.value = '';
        if (endInput) endInput.value = '';
    }

    filterAppointments();
}

function applyCustomDateFilter() {
    filterAppointments();
}

// ========== THỐNG KÊ ==========
async function loadStatistics(dateRange = null) {
    try {
        if (dateRange === null) {
            dateRange = getActiveDateRange();
            if (!dateRange) return;
        }

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

async function loadAppointments(filters = {}, dateRange = null) {
    try {
        let url;
        let params = new URLSearchParams();

        if (dateRange === null) {
            dateRange = getActiveDateRange();
            if (!dateRange) return;
        }

        if (currentUserRole === 'staff') {
            url = '/api/admin/appointments/my-schedule';
            const today = formatLocalDate(new Date());

            const startDate = filters.startDate || dateRange.start_date || today;
            const endDate = filters.endDate || dateRange.end_date || startDate;

            params.append('start_date', startDate);
            params.append('end_date', endDate);
        } else {
            url = '/api/admin/appointments';

            if (dateRange.start_date) params.append('start_date', dateRange.start_date);
            if (dateRange.end_date) params.append('end_date', dateRange.end_date);

            const status = document.getElementById('filter-status-select')?.value;
            if (status) params.append('status', status);
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



function escapeBookingText(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
}

function resetCustomerTreatments() {
    treatmentLoadVersion++; // Ignore responses for a previous customer or modal session.
    clearPackageSelections();
    customerTreatments = [];
    treatmentLoadState = 'idle';
    treatmentLoadError = '';
    document.getElementById('booking-service-method').hidden = selectedCustomerId === null;
    renderBookingTreatments();
}

function clearPackageSelections() {
    selectedServiceIds = selectedServiceIds.filter(id => !selectedPackageItems.has(id));
    selectedPackageItems.clear();
    renderServiceList();
    updateSelectedServices();
    removeSelectedStaff();
    loadAvailableStaff();
}

function setBookingServiceMethod(method) {
    bookingServiceMethod = method;
    document.querySelectorAll('input[name="service-method"]').forEach(input => {
        input.checked = input.value === method;
    });
    if (method === 'regular') clearPackageSelections();
    document.getElementById('booking-services-label').textContent = method === 'treatment'
        ? 'Dịch vụ mua thêm (thanh toán riêng, tùy chọn)' : 'Dịch vụ *';
    renderBookingTreatments();
}

async function loadCustomerTreatments() {
    const customerId = selectedCustomerId;
    const version = ++treatmentLoadVersion;
    if (customerId === null) return;
    treatmentLoadState = 'loading';
    renderBookingTreatments();
    try {
        const response = await fetch(`/api/admin/appointments/customers/${customerId}/treatments`, {
            headers: getAuthHeaders(false)
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.msg || 'Không thể tải liệu trình của khách');
        if (version !== treatmentLoadVersion || customerId !== selectedCustomerId) return;
        customerTreatments = data.treatments || [];
        treatmentLoadState = 'ready';
        // Refresh selected rows from the server before validating remaining sessions.
        for (const [serviceId, selection] of selectedPackageItems) {
            const treatment = customerTreatments.find(t => t.mathe === selection.mathe);
            const item = treatment?.items.find(i => i.id === selection.item.id);
            selectedPackageItems.set(serviceId, {...selection, item: item || {...selection.item, usable: false}});
        }
        if (revalidatePackageSelections()) showError('Liệu trình đã thay đổi. Vui lòng kiểm tra lại dịch vụ còn buổi và hạn sử dụng.');
    } catch (error) {
        if (version !== treatmentLoadVersion || customerId !== selectedCustomerId) return;
        treatmentLoadState = 'error';
        treatmentLoadError = error.message;
        customerTreatments = [];
        clearPackageSelections();
    }
    if (version === treatmentLoadVersion) renderBookingTreatments();
}

function bookingItemUsable(item) {
    if (!item.usable || item.available_sessions <= 0) return false;
    const day = document.getElementById('appointment-date').value;
    // Backend expiry uses calendar days in Asia/Saigon; gifts have their own effective expiry.
    return !day || ((!item.valid_from || day >= item.valid_from.slice(0, 10))
        && (!item.effective_expires_at || day <= item.effective_expires_at.slice(0, 10)));
}

function renderBookingTreatments() {
    const panel = document.getElementById('booking-treatment-panel');
    panel.hidden = bookingServiceMethod !== 'treatment' || selectedCustomerId === null;
    const message = document.getElementById('booking-treatment-message');
    const list = document.getElementById('booking-treatment-list');
    message.textContent = treatmentLoadState === 'loading' ? 'Đang tải liệu trình của khách…'
        : treatmentLoadState === 'error' ? treatmentLoadError
        : !customerTreatments.some(t => t.items.some(bookingItemUsable))
            ? 'Khách hàng hiện chưa có gói/liệu trình khả dụng.'
            : 'Chọn đúng nguồn cho mỗi dịch vụ. Có thể thêm dịch vụ thanh toán riêng bên dưới.';
    if (treatmentLoadState === 'loading') { list.innerHTML = ''; return; }
    if (treatmentLoadState === 'error') {
        list.innerHTML = '<button type="button" class="btn btn-secondary" onclick="loadCustomerTreatments()">Thử tải lại liệu trình</button>';
        return;
    }
    list.innerHTML = customerTreatments.map(treatment => `<details class="booking-treatment-card" open>
        <summary>${escapeBookingText(treatment.tengoi)} · #${treatment.mathe}</summary>
        ${treatment.items.map(item => {
            const usable = bookingItemUsable(item);
            const selected = selectedPackageItems.get(item.madv)?.item.id === item.id;
            const reason = item.available_sessions <= 0 ? 'Đã hết lượt' : !usable ? 'Không còn hiệu lực vào ngày đã chọn' : '';
            const expiry = item.effective_expires_at ? item.effective_expires_at.slice(0, 10).split('-').reverse().join('/') : 'Không giới hạn';
            return `<label class="booking-treatment-item">
                <input type="checkbox" ${selected ? 'checked' : ''} ${usable ? '' : 'disabled'}
                    onchange="togglePackageItem(${treatment.mathe}, ${item.id})" aria-label="${escapeBookingText(item.tendv)} · ${item.source_type === 'gift' ? 'Spa tặng' : 'Trong gói'} · ${escapeBookingText(treatment.tengoi)}">
                <span><strong>${escapeBookingText(item.tendv)}</strong>
                    <span class="booking-source-badge ${item.source_type === 'gift' ? 'gift' : ''}">${item.source_type === 'gift' ? '🎁 Spa tặng' : 'Trong gói'}</span>
                    <small>Còn ${item.available_sessions}/${item.total_sessions} buổi · Đã dùng ${item.consumed} · Đang giữ ${item.reserved}</small>
                    <small>Hạn: ${expiry}${item.valid_from ? ' · Từ: ' + item.valid_from.slice(0, 10).split('-').reverse().join('/') : ''}</small>
                    ${item.gifted_by_name ? `<small>Người tặng: ${escapeBookingText(item.gifted_by_name)}</small>` : ''}
                    ${item.gift_note ? `<small>${escapeBookingText(item.gift_note)}</small>` : ''}
                    ${reason ? `<small>${reason}</small>` : ''}
                </span></label>`;
        }).join('')}
    </details>`).join('');
}

function togglePackageItem(treatmentId, itemId) {
    if (bookingServiceMethod !== 'treatment' || treatmentLoadState !== 'ready') return;
    const treatment = customerTreatments.find(t => t.mathe === treatmentId);
    const item = treatment?.items.find(i => i.id === itemId);
    if (!item || !bookingItemUsable(item)) return;
    if (selectedPackageItems.get(item.madv)?.item.id === itemId) {
        removeService(item.madv);
        return;
    }
    selectedPackageItems.set(item.madv, {mathe: treatmentId, tengoi: treatment.tengoi, item});
    if (!selectedServiceIds.includes(item.madv)) selectedServiceIds.push(item.madv);
    renderServiceList();
    updateSelectedServices();
    renderBookingTreatments();
    removeSelectedStaff();
    loadAvailableStaff();
}

function revalidatePackageSelections() {
    let removed = false;
    for (const [serviceId, selection] of selectedPackageItems) {
        if (!bookingItemUsable(selection.item)) {
            selectedPackageItems.delete(serviceId);
            selectedServiceIds = selectedServiceIds.filter(id => id !== serviceId);
            removed = true;
        }
    }
    if (removed) {
        renderServiceList();
        updateSelectedServices();
        removeSelectedStaff();
        loadAvailableStaff();
    }
    return removed;
}

function bookingDateChanged() {
    if (revalidatePackageSelections()) showError('Dịch vụ liệu trình không còn hiệu lực vào ngày đã chọn.');
    renderBookingTreatments();
    removeSelectedStaff();
    loadAvailableStaff();
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
            <input type="checkbox" id="service-checkbox-${service.madv}" value="${service.madv}" ${selectedServiceIds.includes(service.madv) ? 'checked' : ''} onclick="event.stopPropagation()" onchange="toggleService(${service.madv})" ${selectedPackageItems.has(service.madv) ? 'disabled' : ''}>
            <label for="service-checkbox-${service.madv}" onclick="event.stopPropagation()">
                <span>${escapeBookingText(service.tendv)}${selectedPackageItems.has(service.madv) ? ' · Liệu trình' : ''}</span>
                <span class="service-duration">${service.thoiluong || 60} phút</span>
            </label>
        </div>
    `).join('');
}

function toggleService(serviceId) {
    if (selectedPackageItems.has(serviceId)) return;
    const checkbox = document.getElementById(`service-checkbox-${serviceId}`);
    if (!checkbox) return;
    checkbox.checked = !selectedServiceIds.includes(serviceId);

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
        const selection = selectedPackageItems.get(id);
        if (!service && !selection) return '';
        const source = selection ? `${selection.item.source_type === 'gift' ? '🎁 Spa tặng' : 'Trong gói'} · ${selection.tengoi}` : 'Thanh toán riêng';
        return `
            <div class="service-tag">
                <span>${escapeBookingText(service?.tendv || selection.item.tendv)} · ${escapeBookingText(source)}</span>
                <button type="button" onclick="removeService(${id})">×</button>
            </div>
        `;
    }).join('');
}

function removeService(serviceId) {
    selectedPackageItems.delete(serviceId);
    selectedServiceIds = selectedServiceIds.filter(id => id !== serviceId);
    const checkbox = document.getElementById(`service-checkbox-${serviceId}`);
    if (checkbox) checkbox.checked = false;
    updateSelectedServices();
    updateServiceItemStyles();
    renderServiceList();
    renderBookingTreatments();
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
    resetCustomerTreatments();
    if (selectedCustomerId !== null) loadCustomerTreatments();
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
    resetCustomerTreatments();
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


function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

// Danh sách sau khi áp dụng ô tìm kiếm; bảng, phân trang và tóm tắt dùng chung.
function visibleAppointments() {
    if (!appointmentSearchText) return allAppointments;
    return allAppointments.filter(apt =>
        (apt.khachhang_hoten || '').toLowerCase().includes(appointmentSearchText)
        || String(apt.malh || '').includes(appointmentSearchText));
}

function updateFilterSummary() {
    const summary = document.getElementById('filter-summary');
    if (!summary) return;
    const dateSelect = document.getElementById('filter-date-select');
    const statusSelect = document.getElementById('filter-status-select');
    const parts = [];
    if (dateSelect && dateSelect.value) {
        if (dateSelect.value === 'custom') {
            const start = document.getElementById('filter-start-date')?.value;
            const end = document.getElementById('filter-end-date')?.value || start;
            const vi = iso => iso ? iso.split('-').reverse().join('/') : '';
            if (start) parts.push(start === end ? vi(start) : `${vi(start)} – ${vi(end)}`);
        } else {
            parts.push(dateSelect.options[dateSelect.selectedIndex].text);
        }
    }
    if (statusSelect && statusSelect.value) parts.push(statusSelect.options[statusSelect.selectedIndex].text);
    if (appointmentSearchText) parts.push(`tìm “${appointmentSearchText}”`);
    const count = visibleAppointments().length;
    summary.textContent = parts.length
        ? `${count} lịch hẹn · Đang lọc: ${parts.join(' · ')}`
        : `${count} lịch hẹn · Không áp dụng bộ lọc`;
    document.getElementById('reset-filters-btn')?.toggleAttribute('data-active', parts.length > 0);
}

function renderAppointmentsTable() {
    const tbody = document.querySelector('#appointments-table tbody');
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedData = visibleAppointments().slice(startIndex, startIndex + itemsPerPage);
    updateFilterSummary();

    if (paginatedData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">Không có lịch hẹn nào</td></tr>';
        return;
    }
    
    tbody.innerHTML = paginatedData.map(apt => {
        let serviceName = apt.dichvu_ten || 'N/A';
        let customerName = apt.khachhang_hoten || 'N/A';
        let staffName = apt.nhanvien_hoten || 'Chưa gán';
        
        return `
            <tr data-appointment-id="${apt.malh}">
                <td class="d-none">#${apt.malh}</td>
                <td data-label="Ngày giờ" class="cell-time">${formatDateTime(apt.ngaygio)}</td>
                <td data-label="Khách hàng" class="cell-customer">${escapeHtml(customerName)}</td>
                <td data-label="Dịch vụ">${escapeHtml(serviceName)}</td>
                <td data-label="Nhân viên">${escapeHtml(staffName)}</td>
                <td data-label="Trạng thái" class="cell-status"><span class="badge badge-${getStatusClass(apt.trangthai)}">${getAppointmentStatusText(apt.trangthai)}</span></td>
                <td class="d-none">${appointmentPaymentBadge(apt)}</td>
                <td class="d-none">${escapeHtml(apt.ghichu || '')}</td>
                <td class="action-buttons" data-label="Thao tác">
                    ${appointmentActions(apt)}
                </td>
            </tr>
        `;
    }).join('');
}

function renderPagination() {
    const totalPages = Math.ceil(visibleAppointments().length / itemsPerPage);
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
    const totalPages = Math.ceil(visibleAppointments().length / itemsPerPage);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderAppointmentsTable();
    renderPagination();
}

function filterAppointments() {
    const dateRange = getActiveDateRange();
    if (!dateRange) {
        // Validation thất bại (đã hiển thị thông báo lỗi) -> KHÔNG gọi API
        return;
    }

    const status = document.getElementById('filter-status-select')?.value;
    const filters = {};
    if (status) filters.status = status;

    currentPage = 1;
    loadAppointments(filters, dateRange);
    loadStatistics(dateRange);
}

function resetFilters() {
    const filterDateSelect = document.getElementById('filter-date-select');
    if (filterDateSelect) filterDateSelect.value = '';

    const filterStatusSelect = document.getElementById('filter-status-select');
    if (filterStatusSelect) filterStatusSelect.value = '';

    const startInput = document.getElementById('filter-start-date');
    if (startInput) startInput.value = '';

    const endInput = document.getElementById('filter-end-date');
    if (endInput) endInput.value = '';

    const customContainer = document.getElementById('custom-date-filter');
    if (customContainer) {
        customContainer.classList.add('d-none');
    }

    const searchInput = document.getElementById('search-input');
    if (searchInput) searchInput.value = '';
    appointmentSearchText = '';
    document.querySelector('.search-clear')?.classList.remove('active');

    currentPage = 1;
    const emptyRange = { start_date: null, end_date: null };
    loadAppointments({}, emptyRange);
    loadStatistics(emptyRange);
}

function openAddAppointmentModal() {
    document.getElementById('modal-title').innerHTML = '<i class="fas fa-calendar-plus"></i> Tạo lịch hẹn mới';
    document.getElementById('appointmentForm').reset();
    document.getElementById('appointment-id').value = '';
    
    selectedServiceIds = [];
    selectedCustomerId = null;
    selectedStaffId = null;
    availableStaff = [];
    resetCustomerTreatments();
    setBookingServiceMethod('regular');
    
    updateSelectedServices();
    updateSelectedCustomer(null, '', '');
    updateSelectedStaff(null, '', '');
    
    renderServiceList();
    renderCustomerList();
    
    document.getElementById('staffList').innerHTML = '<div style="padding: 12px; color: #9ca3af; text-align: center;">Vui lòng chọn ngày, giờ và dịch vụ để xem nhân viên rảnh</div>';

    const today = formatLocalDate(new Date());
    document.getElementById('appointment-date').value = today;
    document.getElementById('appointment-date').min = today;
    
    document.getElementById('appointmentModal').style.display = 'flex';
}

function closeAppointmentModal() {
    document.getElementById('appointmentModal').style.display = 'none';
}

async function handleAppointmentSubmit(e) {
    e?.preventDefault();
    if (appointmentSubmitting) return;
    const form = document.getElementById('appointmentForm');
    if (!form.reportValidity()) return;
    if (revalidatePackageSelections()) {
        showError('Dịch vụ liệu trình không còn hiệu lực vào ngày đã chọn. Vui lòng kiểm tra lại dịch vụ.');
        return;
    }
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
    const packageUsages = [...selectedPackageItems.values()].map(selection => ({
        mathe: selection.mathe, the_item_id: selection.item.id, madv: selection.item.madv, quantity: 1
    }));
    appointmentSubmitting = true;
    document.getElementById('appointment-save').disabled = true;
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: getAuthHeaders(),
            body: JSON.stringify({
                makh: parseInt(makh),
                madv_list: madv_list,
                manv: manv ? parseInt(manv) : null,
                ngaygio: ngaygio,
                package_usages: packageUsages,
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
            if (packageUsages.length && [400, 409].includes(response.status)) await loadCustomerTreatments();
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
    } finally {
        appointmentSubmitting = false;
        document.getElementById('appointment-save').disabled = false;
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
    document.getElementById('detail-invoice').innerHTML = `Thanh toán: ${appointmentPaymentBadge(apt)} ${appointmentInvoiceAction(apt)}`;
    document.getElementById('detail-apt-notes').textContent = apt.ghichu || 'Không có ghi chú';
    const bookingSources = {admin: 'Bin Spa hỗ trợ đặt lịch', customer: 'Khách tự đặt', ai: 'Trợ lý AI', legacy: 'Lịch cũ'};
    document.getElementById('detail-booking-source').textContent = `${bookingSources[apt.booking_source] || 'Lịch cũ'}${apt.created_by_staff_name ? ' · ' + apt.created_by_staff_name : ''}`;

    const servicesList = document.getElementById('detail-services-list');
    if (apt.services && apt.services.length > 0) {
        servicesList.innerHTML = apt.services.map(s => `
            <li><span>${escapeBookingText(s.tendv)}</span><span>${s.coverage
                ? `${s.coverage.state === 'reserved' ? 'Đã giữ buổi' : 'Đã sử dụng liệu trình'} · ${s.coverage.source_type === 'gift' ? '🎁 Spa tặng' : 'Trong gói'} · ${escapeBookingText(s.coverage.tengoi)}`
                : `Thanh toán riêng · ${formatCurrency(s.gia)}`}</span></li>
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
    showConfirm('Hoàn thành lịch hẹn', 'Xác nhận khách hàng đã hoàn thành dịch vụ?', async () => {
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
                await loadAppointments();
                loadStatistics();
            } else {
                showError(data.msg || 'Cập nhật thất bại');
            }
        } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra'); }
    });
}

function cancelAppointment(malh) {
    showConfirm('Hủy lịch hẹn', `Lịch #${malh} sẽ bị hủy và các buổi gói đang giữ được hoàn lại. Thao tác này không hoàn tác được.`,
        reason => submitCancelAppointment(malh, reason), null, 'Hủy lịch', 'Quay lại',
        { danger: true, inputLabel: 'Lý do hủy (không bắt buộc)' });
}

async function submitCancelAppointment(malh, reason) {
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
        
        if ((response.ok || data.code === "INVOICE_ALREADY_EXISTS") && data.invoice_id) {
            showSuccess(data.msg || 'Tạo hóa đơn thành công!');
            await loadAppointments();
            openInvoicePayment(data.invoice_id);
        } else {
            showError(data.msg || 'Tạo hóa đơn thất bại');
        }
    } catch (error) { console.error('Lỗi:', error); showError('Có lỗi xảy ra khi tạo hóa đơn'); }
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

// Hộp xác nhận dùng chung. options.danger: nút xác nhận màu đỏ và focus mặc định ở nút "quay lại";
// options.inputLabel: thêm ô nhập (onConfirm nhận giá trị). Esc = hủy.
function showConfirm(title, message, onConfirm, onCancel = null, confirmText = 'OK', cancelText = 'Hủy', options = {}) {
    const oldModal = document.getElementById('confirm-toast-modal');
    if (oldModal) oldModal.remove();
    const input = options.inputLabel
        ? `<label class="confirm-toast-input">${options.inputLabel}<textarea id="confirm-input" rows="3" maxlength="500"></textarea></label>`
        : '';
    const modalHtml = `<div id="confirm-toast-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-toast-title" aria-describedby="confirm-toast-body"><div class="confirm-toast-content"><div class="confirm-toast-header"><i class="fas fa-exclamation-triangle" aria-hidden="true"></i><h4 id="confirm-toast-title">${title}</h4></div><div class="confirm-toast-body" id="confirm-toast-body">${message}${input}</div><div class="confirm-toast-actions"><button type="button" class="btn btn-secondary" id="confirm-btn-cancel">${cancelText}</button><button type="button" class="btn ${options.danger ? 'btn-danger' : 'btn-primary'}" id="confirm-btn-ok">${confirmText}</button></div></div></div>`;
    const previousFocus = document.activeElement;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = document.getElementById('confirm-toast-modal');
    const closeMod = () => {
        document.removeEventListener('keydown', onKey);
        modal.classList.remove('show');
        setTimeout(() => { modal.remove(); previousFocus?.focus?.(); }, 200);
    };
    const cancel = () => { if (onCancel) { onCancel(); } closeMod(); };
    const onKey = e => { if (e.key === 'Escape') cancel(); };
    document.addEventListener('keydown', onKey);
    document.getElementById('confirm-btn-ok').onclick = function() {
        const value = document.getElementById('confirm-input')?.value.trim();
        onConfirm(value);
        closeMod();
    };
    document.getElementById('confirm-btn-cancel').onclick = cancel;
    setTimeout(() => {
        modal.classList.add('show');
        (document.getElementById('confirm-input') || document.getElementById(options.danger ? 'confirm-btn-cancel' : 'confirm-btn-ok'))?.focus();
    }, 10);
}

function exportAppointments() { showError('Chức năng xuất Excel đang được phát triển'); }

// HÀM SEARCH LỊCH HẸN (lọc trên danh sách đã tải, giữ khi chuyển trang)
function searchAppointments() {
    const searchInput = document.getElementById('search-input');
    appointmentSearchText = (searchInput?.value || '').trim().toLowerCase();
    document.querySelector('.search-clear')?.classList.toggle('active', appointmentSearchText.length > 0);
    currentPage = 1;
    renderAppointmentsTable();
    renderPagination();
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    searchAppointments();
}

// Gán các hàm ra window để gọi từ HTML inline và modal
window.handleDateSelectChange = handleDateSelectChange;
window.applyCustomDateFilter = applyCustomDateFilter;
window.filterAppointments = filterAppointments;
window.resetFilters = resetFilters;
window.getActiveDateRange = getActiveDateRange;
window.loadAppointments = loadAppointments;
window.loadStatistics = loadStatistics;

function appointmentInvoiceAction(apt) {
    const permissions = apt.permissions || {};
    if (permissions.canPayInvoice) return `<button class="btn btn-warning btn-sm" onclick="openInvoicePayment(${apt.invoice.mahd})">Thanh toán hóa đơn</button>`;
    if (permissions.canViewInvoice) return `<button class="btn btn-info btn-sm" onclick="viewAppointmentInvoice(${apt.invoice.mahd})">Xem hóa đơn</button>`;
    if (permissions.canCreateInvoice) return `<button class="btn btn-warning btn-sm" onclick="createInvoiceForAppointment(${apt.malh})">Tạo hóa đơn</button>`;
    return '';
}
function appointmentActions(apt) {
    const permissions = apt.permissions || {};
    // Hành động tiếp theo đứng trước và nổi bật; "Xem" là nút phụ ở cuối.
    return `${permissions.canCheckIn ? `<button class="btn btn-primary btn-sm" onclick="checkInAppointment(${apt.malh})" aria-label="Check-in: khách đã đến lịch #${apt.malh}"><i class="fas fa-user-check" aria-hidden="true"></i> Check-in</button>` : ''}
        ${permissions.canConfirm ? `<button class="btn btn-primary btn-sm" onclick="confirmAppointment(${apt.malh})">Xác nhận</button>` : ''}
        ${permissions.canComplete ? `<button class="btn btn-success btn-sm" onclick="completeAppointment(${apt.malh})">Hoàn thành</button>` : ''}
        ${appointmentInvoiceAction(apt)}
        ${permissions.canChangeServices ? `<button class="btn btn-secondary btn-sm" onclick="openChangeServicesModal(${apt.malh})">Đổi dịch vụ</button>` : ''}
        ${permissions.canView ? `<button class="btn btn-secondary btn-sm" onclick="viewAppointmentDetail(${apt.malh})" aria-label="Xem chi tiết lịch #${apt.malh}">Xem</button>` : ''}`;
}
function appointmentPaymentBadge(apt) {
    if (!apt.payment_status) return '—';
    const paid = ['Đã thanh toán', 'Đã thanh toán bằng gói'].includes(apt.payment_status);
    return `<span class="badge badge-${paid ? 'success' : 'warning'}">${apt.payment_status}</span>`;
}
document.addEventListener('invoice-payment-updated', () => loadAppointments());

// ========== ĐỔI DỊCH VỤ THEO YÊU CẦU KHÁCH ==========
// Giữ giờ hẹn và KTV; server kiểm tra lại ca làm/trùng lịch với tổng thời lượng mới.
async function openChangeServicesModal(malh) {
    if (!window.ChangeServicesDialog) return;
    try {
        const detailRes = await fetch(`/api/admin/appointments/${malh}`, { headers: getAuthHeaders(false) });
        const detail = (await detailRes.json()).appointment;
        if (!detailRes.ok || !detail) throw new Error('Không tải được lịch hẹn');
        let services = allServices;
        if (!services.length) {
            const r = await fetch('/api/admin/services', { headers: getAuthHeaders(false) });
            services = r.ok ? await r.json() : [];
        }
        let treatments = [];
        if (detail.khachhang && currentUserRole !== 'staff') {
            const r = await fetch(`/api/admin/appointments/customers/${detail.khachhang.makh}/treatments`, { headers: getAuthHeaders(false) });
            if (r.ok) treatments = (await r.json()).treatments || [];
        }
        const current = new Map(detail.services.map(s => [s.madv, {
            package: !!s.coverage,
            label: s.coverage ? `${s.coverage.source_type === 'gift' ? 'Quà tặng' : 'Buổi gói'}: ${s.coverage.tengoi}` : '',
        }]));
        const day = detail.ngaygio.slice(0, 10);
        const packageOptions = madv => treatments.flatMap(t => t.status === 'cancelled' ? [] :
            t.items.filter(i => i.madv === madv && i.usable !== false && i.available_sessions > 0
                && (!i.effective_expires_at || i.effective_expires_at.slice(0, 10) >= day)
                && (!i.valid_from || i.valid_from.slice(0, 10) <= day))
                .map(i => ({ value: `${t.mathe}:${i.id}`, label: `${i.source_type === 'gift' ? 'Quà tặng' : 'Buổi gói'}: ${t.tengoi} — còn ${i.available_sessions}` })));
        window.ChangeServicesDialog.open({
            title: `Đổi dịch vụ – lịch #${malh}`,
            subtitle: `${escapeHtml(detail.khachhang?.hoten || 'Khách')} · ${formatDateTime(detail.ngaygio)} · KTV ${escapeHtml(detail.nhanvien?.hoten || 'chưa gán')}`,
            services: services.filter(s => s.active !== false || current.has(s.madv)),
            current, packageOptions, startAt: detail.ngaygio,
            submit: async (madv_list, package_usages) => {
                const response = await fetch(`/api/admin/appointments/${malh}/services`, {
                    method: 'PUT', headers: getAuthHeaders(), body: JSON.stringify({ madv_list, package_usages }),
                });
                const data = await response.json();
                if (!response.ok || !data.success) throw new Error(data.msg || 'Không thể đổi dịch vụ');
                showSuccess(`${data.msg}. Dự kiến kết thúc ${data.end_time}.`);
                loadAppointments();
            },
        });
    } catch (error) {
        showError(error.message || 'Không tải được dữ liệu');
    }
}
window.openChangeServicesModal = openChangeServicesModal;


// ========== CHECK-IN: KHÁCH ĐÃ ĐẾN ==========
function checkInAppointment(malh) {
    const apt = allAppointments.find(a => a.malh === malh);
    const who = apt ? `${escapeHtml(apt.khachhang_hoten || 'Khách')} – ${formatDateTime(apt.ngaygio)}` : `lịch #${malh}`;
    showConfirm('Check-in khách', `Xác nhận khách đã đến: ${who}?\nLịch chuyển sang "Đang thực hiện" và không còn bị tự hủy.`, async () => {
        try {
            const response = await fetch(`/api/admin/appointments/${malh}/check-in`, { method: 'POST', headers: getAuthHeaders() });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.msg || 'Check-in thất bại');
            showSuccess(data.msg);
            loadAppointments();
            loadStatistics();
        } catch (error) {
            showError(error.message);
        }
    }, null, 'Check-in', 'Quay lại');
}
window.checkInAppointment = checkInAppointment;
