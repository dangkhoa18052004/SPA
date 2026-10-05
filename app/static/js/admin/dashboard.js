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

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
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
    initDashboardRange();
    initAiSummary();
    try {
        await Promise.all([loadAdminStats(), loadAdminTodayAppointments(), refreshRangeAnalytics()]);
    } catch (error) {
        console.error('❌ Error loading admin dashboard:', error);
        showToast('Lỗi tải dữ liệu dashboard', 'error');
    }
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

// Các số "hôm nay" và tổng khách không phụ thuộc khoảng ngày đã chọn.
async function loadAdminStats() {
    try {
        const response = await fetch('/api/dashboard/stats', { headers: getAuthHeaders(false) });
        if (!response.ok) throw new Error('Failed to fetch stats');
        const data = await response.json();
        if (data.success && data.stats) {
            setText('stat-today-appointments', data.stats.today.total_appointments);
            setText('stat-working-staff', data.stats.today.working_staff);
            setText('stat-total-customers', data.stats.general.total_customers);
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
                    <td><strong>${formatTime(apt.ngaygio)}</strong></td>
                    <td>${escapeHtml(apt.khachhang_hoten)}</td>
                    <td><span class="service-tag">${escapeHtml(apt.dichvu_ten)}</span></td>
                    <td>${escapeHtml(apt.nhanvien_hoten)}</td>
                    <td>${getStatusBadge(apt.trangthai)}</td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center empty-state">
                        <i class="fas fa-calendar-times"></i>
                        <p>Không có lịch hẹn nào hôm nay</p>
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading today appointments:', error);
        const tableBody = document.getElementById('admin-appointments-table');
        if (tableBody) { tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger"><i class="fas fa-exclamation-triangle"></i> Lỗi tải dữ liệu</td></tr>`; }
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
                        ${['pending', 'confirmed'].includes(apt.trangthai) ? `
                            <button class="btn btn-primary btn-sm" onclick="startAppointment(${apt.malh})" aria-label="Check-in: khách đã đến">
                                <i class="fas fa-user-check" aria-hidden="true"></i> Check-in
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
                            ${['pending', 'confirmed'].includes(apt.trangthai) ? `
                                <button class="btn btn-primary btn-sm" onclick="startAppointment(${apt.malh})" aria-label="Check-in: khách đã đến">
                                    <i class="fas fa-user-check" aria-hidden="true"></i> Check-in
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

// Check-in: khách đã đến → Đang thực hiện (dùng chung API với trang Lịch hẹn, lịch không còn bị tự hủy).
async function startAppointment(malh) {
    if (!confirm('Xác nhận khách đã đến (check-in)?')) return;
    
    try {
        const response = await fetch(`/api/admin/appointments/${malh}/check-in`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.msg || 'Đã check-in', 'success');
            loadDashboardData(localStorage.getItem('admin_role'));
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

// ===================================
// ======= ANALYTICS (KHOẢNG NGÀY CHUNG)
// ===================================
let revenueChartInstance = null;
let appointmentChartInstance = null;
let serviceMixChartInstance = null;
const dashboardRange = { from: null, to: null };

function isoDate(d) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatViDate(iso) {
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

function presetRange(preset) {
    const today = new Date();
    const to = isoDate(today);
    if (preset === 'today') return { from: to, to };
    if (preset === 'month') return { from: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)), to };
    const days = Number(preset) || 30;
    const start = new Date(today);
    start.setDate(start.getDate() - (days - 1));
    return { from: isoDate(start), to };
}

function rangeQuery() {
    return `from=${dashboardRange.from}&to=${dashboardRange.to}`;
}

function initDashboardRange() {
    const preset = document.getElementById('dash-range-preset');
    if (!preset || preset.dataset.bound) return;
    preset.dataset.bound = '1';
    const custom = document.getElementById('dash-range-custom');
    const fromInput = document.getElementById('dash-from');
    const toInput = document.getElementById('dash-to');
    Object.assign(dashboardRange, presetRange(preset.value));

    preset.addEventListener('change', () => {
        if (preset.value === 'custom') {
            custom.hidden = false;
            fromInput.value = dashboardRange.from;
            toInput.value = dashboardRange.to;
            fromInput.focus();
            return;
        }
        custom.hidden = true;
        Object.assign(dashboardRange, presetRange(preset.value));
        refreshRangeAnalytics();
    });
    document.getElementById('dash-range-apply').addEventListener('click', () => {
        if (!fromInput.value || !toInput.value) {
            showToast('Vui lòng chọn đủ Từ ngày và Đến ngày', 'error');
            return;
        }
        if (fromInput.value > toInput.value) {
            showToast('Từ ngày phải trước hoặc bằng Đến ngày', 'error');
            return;
        }
        Object.assign(dashboardRange, { from: fromInput.value, to: toInput.value });
        refreshRangeAnalytics();
    });
    document.getElementById('revenue-group-select').addEventListener('change', e => loadRevenueChart(e.target.value));
}

async function refreshRangeAnalytics() {
    setText('dash-range-label', `Đang xem: ${formatViDate(dashboardRange.from)} – ${formatViDate(dashboardRange.to)}`);
    const group = document.getElementById('revenue-group-select');
    await Promise.all([
        loadRangeSummary(),
        loadRevenueChart(group ? group.value : 'day'),
        loadServiceMixChart(),
        loadAppointmentChart(),
    ]);
}

async function fetchAnalytics(path) {
    const response = await fetch(`/api/analytics/${path}`, { headers: getAuthHeaders(false) });
    const res = await response.json();
    if (!response.ok || !res.success) throw new Error(res.msg || 'Lỗi tải dữ liệu');
    return res;
}

async function loadRangeSummary() {
    try {
        const res = await fetchAnalytics(`summary?${rangeQuery()}`);
        setText('kpi-revenue-total', formatCurrency(res.revenue.total));
        setText('kpi-revenue-service', formatCurrency(res.revenue.service));
        setText('kpi-revenue-package', formatCurrency(res.revenue.package));
        setText('kpi-aov', formatCurrency(res.revenue.average_transaction));
        setText('kpi-transactions', res.revenue.transactions);
        setText('kpi-appointments', res.appointments.total);
        setText('kpi-completed', res.appointments.completed);
        setText('kpi-cancelled', res.appointments.cancelled);
        setText('kpi-cancel-rate', `${res.appointments.cancel_rate}%`);
        setText('kpi-new-customers', res.new_customers);
    } catch (e) {
        console.error('Error loading summary:', e);
        showToast('Không tải được chỉ số KPI', 'error');
    }
}

function compactMoney(value) {
    return value >= 1000000 ? (value / 1000000) + 'M' : value >= 1000 ? (value / 1000) + 'k' : value;
}

async function loadRevenueChart(groupBy = 'day') {
    const canvas = document.getElementById('revenueTimeseriesChart');
    if (!canvas || typeof Chart === 'undefined') return;
    try {
        const res = await fetchAnalytics(`revenue-timeseries?group_by=${groupBy}&${rangeQuery()}`);
        if (revenueChartInstance) revenueChartInstance.destroy();
        revenueChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: res.chart_data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${formatCurrency(ctx.raw)}` } }
                },
                scales: { y: { beginAtZero: true, ticks: { callback: compactMoney } } }
            }
        });
    } catch (e) {
        console.error('Error loading revenue chart:', e);
    }
}

async function loadServiceMixChart() {
    const canvas = document.getElementById('serviceMixChart');
    const list = document.getElementById('top-services-list');
    if (!canvas || typeof Chart === 'undefined') return;
    try {
        const res = await fetchAnalytics(`top-services?limit=5&${rangeQuery()}`);
        if (serviceMixChartInstance) serviceMixChartInstance.destroy();
        serviceMixChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: res.chart_data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
        if (list) {
            const colors = res.chart_data.datasets[0]?.backgroundColor || [];
            list.innerHTML = res.top_services.length
                ? res.top_services.map((s, i) => `
                    <li><span class="dot" style="background:${colors[i] || '#999'}" aria-hidden="true"></span>
                        <span class="name">${escapeHtml(s.tendv)}</span>
                        <span class="count">${s.booking_count} lượt</span></li>`).join('')
                : '<li class="empty">Chưa có lượt đặt trong khoảng này</li>';
        }
    } catch (e) {
        console.error('Error loading service mix chart:', e);
    }
}

async function loadAppointmentChart() {
    const canvas = document.getElementById('appointmentStatsChart');
    if (!canvas || typeof Chart === 'undefined') return;
    try {
        const res = await fetchAnalytics(`appointment-stats?${rangeQuery()}`);
        if (appointmentChartInstance) appointmentChartInstance.destroy();
        appointmentChartInstance = new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: res.chart_data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
            }
        });
    } catch (e) {
        console.error('Error loading appointment chart:', e);
    }
}


// ===================================
// ======= TÓM TẮT KINH DOANH AI (GĐ5)
// ===================================
async function initAiSummary() {
    const panel = document.getElementById('ai-summary-panel');
    if (!panel) return;
    try {
        const status = await (await fetch('/api/ai/status')).json();
        if (!status.configured) return;
    } catch (e) { return; }
    panel.hidden = false;
    const button = document.getElementById('ai-summary-btn');
    const body = document.getElementById('ai-summary-body');
    button.addEventListener('click', async () => {
        button.disabled = true;
        body.innerHTML = '<p><i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Đang phân tích số liệu...</p>';
        try {
            const response = await fetch('/api/ai/business-summary', {
                method: 'POST', headers: getAuthHeaders(),
                body: JSON.stringify({ from: dashboardRange.from, to: dashboardRange.to }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.msg || 'Không tạo được tóm tắt');
            body.innerHTML = `
                <p class="ai-summary-range">Khoảng ${formatViDate(data.from_date)} – ${formatViDate(data.to_date)}</p>
                <div class="ai-summary-cols">
                    <section><h4>Số liệu thực tế (FACTS)</h4><ul>${data.facts.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul></section>
                    <section><h4>Nhận xét & gợi ý (AI – SUGGESTIONS)</h4>
                        ${data.summary ? `<p>${escapeHtml(data.summary)}</p>` : ''}
                        <ul>${data.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('') || '<li>Không có gợi ý.</li>'}</ul>
                        ${data.removed_unverified ? `<p class="ai-summary-hint">Đã loại ${data.removed_unverified} câu có số không có trong dữ liệu.</p>` : ''}
                    </section>
                </div>`;
        } catch (error) {
            body.innerHTML = `<p class="text-danger">${escapeHtml(error.message)}</p>`;
        } finally {
            button.disabled = false;
        }
    });
}
