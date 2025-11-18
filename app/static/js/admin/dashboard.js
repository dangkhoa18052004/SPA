// ============ CONSTANTS ============
const STATUS_LABELS = {
    'pending': 'Chờ xác nhận',
    'confirmed': 'Đã xác nhận',
    'in_progress': 'Đang thực hiện',
    'completed': 'Đã hoàn thành',
    'cancelled': 'Đã hủy'
};

const STATUS_CLASSES = {
    'pending': 'status-pending',
    'confirmed': 'status-confirmed',
    'in_progress': 'status-progress',
    'completed': 'status-completed',
    'cancelled': 'status-cancelled'
};

// ============ UTILITY FUNCTIONS ============
function formatCurrency(amount) {
    const numericAmount = Number(amount);
    if (isNaN(numericAmount) || numericAmount === 0) return '0₫';
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(numericAmount);
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getStatusBadge(status) {
    const label = STATUS_LABELS[status] || status;
    const className = STATUS_CLASSES[status] || 'status-default';
    return `<span class="status-badge badge-${className}">${label}</span>`;
}

// Giữ nguyên các hàm showToast, createToastContainer, logout, getAuthHeaders
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    const container = document.getElementById('toast-container') || createToastContainer();
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
    return container;
}

function logout() {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_role');
    window.location.href = '/admin/login';
}

function getAuthHeaders(includeJson = true) {
    const headers = {
        'Authorization': `Bearer ${localStorage.getItem('admin_token')}`
    };
    if (includeJson) {
        headers['Content-Type'] = 'application/json';
    }
    return headers;
}


// ===================================
// ============ MAIN INIT ============
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('current-date').textContent = new Date().toLocaleDateString('vi-VN', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    const role = localStorage.getItem('admin_role');
    if (!role) return;
    
    showDashboardByRole(role);
    loadDashboardData(role);
});

function showDashboardByRole(role) {
    document.querySelectorAll('.dashboard-container > div').forEach(el => {
        if (el.id !== 'welcome-section') el.style.display = 'none';
    });
    
    const targetId = `${role}-dashboard`;
    if (role === 'admin' || role === 'manager') {
        document.getElementById('admin-dashboard').style.display = 'block';
    } else {
        const dashboard = document.getElementById(targetId);
        if (dashboard) dashboard.style.display = 'block';
    }
}

function loadDashboardData(role) {
    if (role === 'admin' || role === 'manager') {
        loadAdminDashboard();
    } else if (role === 'letan') {
        loadLetanDashboard();
    } else if (role === 'staff') {
        loadStaffDashboard();
    }
}


// ===================================
// ======= ADMIN/MANAGER DASHBOARD =======
// ===================================

async function loadAdminDashboard() {
    try {
        await loadAdminStats();
        await loadAdminTodayAppointments();
    } catch (error) {
        console.error('❌ Error loading admin dashboard:', error);
        showToast('Lỗi tải dữ liệu dashboard', 'error');
    }
}

async function loadAdminStats() {
    try {
        const response = await fetch('/api/dashboard/stats', { headers: getAuthHeaders(false) });
        if (!response.ok) throw new Error('Failed to fetch stats');
        
        const data = await response.json();
        
        if (data.success && data.stats) {
            const stats = data.stats;
            
            // Stats Today
            const todayAptEl = document.getElementById('stat-today-appointments');
            if (todayAptEl) todayAptEl.textContent = stats.today.total_appointments;
            
            const workingStaffEl = document.getElementById('stat-working-staff');
            if (workingStaffEl) workingStaffEl.textContent = stats.today.working_staff;

            const newCustomersEl = document.getElementById('stat-total-customers');
            if (newCustomersEl) newCustomersEl.textContent = stats.general.total_customers; 

            // Stats Month
            const monthRevenueEl = document.getElementById('stat-month-revenue');
            if (monthRevenueEl) monthRevenueEl.textContent = formatCurrency(stats.month.revenue);

        }
    } catch (error) {
        console.error('Error loading admin stats:', error);
    }
}

async function loadAdminTodayAppointments() {
    try {
        const response = await fetch('/api/dashboard/appointments/today', { headers: getAuthHeaders(false) });
        const data = await response.json();
        const tableBody = document.getElementById('admin-appointments-table');
        
        if (!tableBody) return; 
        
        if (data.success && data.appointments && data.appointments.length > 0) {
            tableBody.innerHTML = data.appointments.map(apt => `
                <tr>
                    <td class="d-none">#${apt.malh}</td>
                    <td><strong>${formatTime(apt.ngaygio)}</strong></td>
                    <td>${apt.khachhang_hoten}</td>
                    <td><span class="service-tag">${apt.dichvu_ten}</span></td>
                    <td>${apt.nhanvien_hoten}</td>
                    <td>${getStatusBadge(apt.trangthai)}</td>
                    <td class="d-none">
                        <button class="btn-icon btn-info btn-sm" onclick="viewAppointment(${apt.malh})" title="Xem chi tiết">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn-icon btn-warning btn-sm" onclick="editAppointment(${apt.malh})" title="Sửa">
                            <i class="fas fa-edit"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center empty-state">
                        <i class="fas fa-calendar-times"></i>
                        <p>Không có lịch hẹn nào hôm nay</p>
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading today appointments:', error);
        const tableBody = document.getElementById('admin-appointments-table');
        if (tableBody) { tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger"><i class="fas fa-exclamation-triangle"></i> Lỗi tải dữ liệu</td></tr>`; }
    }
}

// ===================================
// ======== LỄ TÂN DASHBOARD =========
// ===================================

async function loadLetanDashboard() {
    try {
        await loadLetanStats();
        await loadLetanTodayAppointments();
    } catch (error) {
        console.error('❌ Error loading letan dashboard:', error);
        showToast('Lỗi tải dữ liệu dashboard', 'error');
    }
}

async function loadLetanStats() {
    try {
        const response = await fetch('/api/dashboard/letan-stats', { headers: getAuthHeaders(false) });
        const data = await response.json();
        
        if (data.success && data.stats) {
            // Stats Today
            const todayEl = document.getElementById('letan-today-appointments');
            if (todayEl) todayEl.textContent = data.stats.today_appointments;
            
            const pendingEl = document.getElementById('letan-pending-appointments');
            if (pendingEl) pendingEl.textContent = data.stats.pending_appointments;
            
            // Sửa ID KHÁCH HÀNG MỚI
            const customerEl = document.getElementById('letan-new-customers');
            if(customerEl) customerEl.textContent = data.stats.new_customers;
            
            // LƯU Ý: Vẫn còn ID letan-unpaid-invoices chưa được gán. Giả định giá trị = 0
            const unpaidEl = document.getElementById('letan-unpaid-invoices');
            if(unpaidEl) unpaidEl.textContent = 0; 
        }
    } catch (error) {
        console.error('Error loading letan stats:', error);
    }
}

async function loadLetanTodayAppointments() {
    try {
        const response = await fetch('/api/dashboard/appointments/today', { headers: getAuthHeaders(false) });
        const data = await response.json();
        const tableBody = document.getElementById('letan-appointments-table');
        
        if (!tableBody) return;
        
        if (data.success && data.appointments && data.appointments.length > 0) {
            tableBody.innerHTML = data.appointments.map(apt => `
                <tr>
                    <td><strong>${formatTime(apt.ngaygio)}</strong></td>
                    <td>${apt.khachhang_hoten}</td>
                    <td><span class="service-tag">${apt.dichvu_ten}</span></td>
                    <td>${apt.nhanvien_hoten}</td>
                    <td>${getStatusBadge(apt.trangthai)}</td>
                    <td>
                        <button class="btn-icon btn-info btn-sm" onclick="viewAppointment(${apt.malh})" title="Xem">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${apt.trangthai === 'pending' ? `
                            <button class="btn-icon btn-success btn-sm" onclick="confirmAppointment(${apt.malh})" title="Xác nhận">
                                <i class="fas fa-check"></i>
                            </button>
                        ` : ''}
                    </td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-center empty-state"><i class="fas fa-calendar-times"></i><p>Không có lịch hẹn nào hôm nay</p></td></tr>`;
        }
    } catch (error) {
        console.error('Error loading letan appointments:', error);
        const tableBody = document.getElementById('letan-appointments-table');
        if (tableBody) { tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger"><i class="fas fa-exclamation-triangle"></i> Lỗi tải dữ liệu</td></tr>`; }
    }
}

// ===================================
// ======== STAFF DASHBOARD ==========
// ===================================

async function loadStaffDashboard() {
    try {
        await loadStaffStats();
        await loadStaffTodaySchedule();
    } catch (error) {
        console.error('❌ Error loading staff dashboard:', error);
        showToast('Lỗi tải dữ liệu dashboard', 'error');
    }
}

async function loadStaffStats() {
    try {
        const response = await fetch('/api/dashboard/staff-stats', { headers: getAuthHeaders(false) });
        const data = await response.json();
        
        if (data.success && data.stats) {
            const stats = data.stats;
            
            const todayEl = document.getElementById('staff-today-schedule');
            if (todayEl) todayEl.textContent = stats.today_schedule;
            
            const weekShiftsEl = document.getElementById('staff-week-schedule');
            if (weekShiftsEl) weekShiftsEl.textContent = stats.week_schedule;
            
            const monthShiftsEl = document.getElementById('staff-month-shifts');
            if (monthShiftsEl) monthShiftsEl.textContent = stats.month_shifts; 
            
            // BỎ QUA stat-completed-appointments (API không có)
            const completedAptEl = document.getElementById('staff-completed-appointments');
            if (completedAptEl) completedAptEl.textContent = 'N/A'; // Hoặc giá trị mặc định
        }
    } catch (error) {
        console.error('Error loading staff stats:', error);
    }
}

async function loadStaffTodaySchedule() {
    try {
        const response = await fetch('/api/dashboard/appointments/my-schedule-today', { headers: getAuthHeaders(false) });
        const data = await response.json();
        const tableBody = document.getElementById('staff-appointments-table');
        
        if (!tableBody) return;

        if (data.success && data.appointments && data.appointments.length > 0) {
            tableBody.innerHTML = data.appointments.map(apt => `
                <tr>
                    <td><strong>${formatTime(apt.ngaygio)}</strong></td>
                    <td>${apt.khachhang_hoten}</td>
                    <td><span class="service-tag">${apt.dichvu_ten}</span></td>
                    <td>${getStatusBadge(apt.trangthai)}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn-icon btn-info btn-sm" onclick="viewAppointment(${apt.malh})" title="Xem">
                                <i class="fas fa-eye"></i>
                            </button>
                            ${apt.trangthai === 'confirmed' ? `
                                <button class="btn-icon btn-info btn-sm" onclick="startAppointment(${apt.malh})" title="Bắt đầu">
                                    <i class="fas fa-play"></i>
                                </button>
                            ` : apt.trangthai === 'in_progress' ? `
                                <button class="btn-icon btn-success btn-sm" onclick="completeAppointment(${apt.malh})" title="Hoàn thành">
                                    <i class="fas fa-check"></i>
                                </button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center empty-state"><i class="fas fa-calendar-times"></i><p>Bạn không có lịch làm việc nào hôm nay</p></td></tr>`;
        }
    } catch (error) {
        console.error('Error loading staff schedule:', error);
        const tableBody = document.getElementById('staff-appointments-table');
        if (tableBody) { tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger"><i class="fas fa-exclamation-triangle"></i> Lỗi tải dữ liệu</td></tr>`; }
    }
}


// ===================================
// ========= ACTION FUNCTIONS ========
// ===================================

function viewAppointment(malh) {
    window.location.href = `/admin/appointments?view=${malh}`;
}

function editAppointment(malh) {
    window.location.href = `/admin/appointments?edit=${malh}`;
}

async function confirmAppointment(malh) {
    if (!confirm('Xác nhận lịch hẹn này?')) return;
    
    try {
        const response = await fetch(`/api/appointments/${malh}/confirm`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Đã xác nhận lịch hẹn', 'success');
            loadDashboardData(localStorage.getItem('admin_role'));
        } else {
            showToast(data.msg || 'Lỗi xác nhận', 'error');
        }
    } catch (error) {
        console.error('Error confirming appointment:', error);
        showToast('Lỗi hệ thống', 'error');
    }
}

async function startAppointment(malh) {
    if (!confirm('Bắt đầu thực hiện lịch hẹn này?')) return;
    
    try {
        const response = await fetch(`/api/appointments/${malh}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ trangthai: 'in_progress' })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Đã bắt đầu thực hiện', 'success');
            loadStaffTodaySchedule();
        } else {
            showToast(data.msg || 'Lỗi cập nhật', 'error');
        }
    } catch (error) {
        console.error('Error starting appointment:', error);
        showToast('Lỗi hệ thống', 'error');
    }
}

async function completeAppointment(malh) {
    if (!confirm('Đánh dấu lịch hẹn đã hoàn thành?')) return;
    
    try {
        const response = await fetch(`/api/appointments/${malh}/complete`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Đã hoàn thành lịch hẹn', 'success');
            loadStaffTodaySchedule();
        } else {
            showToast(data.msg || 'Lỗi cập nhật', 'error');
        }
    } catch (error) {
        console.error('Error completing appointment:', error);
        showToast('Lỗi hệ thống', 'error');
    }
}