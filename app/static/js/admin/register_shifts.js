// ====== BIẾN GLOBAL ======
let availableShifts = [];
let mySchedule = []; // Lịch của tôi
let currentWeekStart = null;

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    const today = new Date();
    currentWeekStart = getMonday(today);
    loadData(); // Tải cả hai
    setupNavigation();
});

// ====== SETUP NAVIGATION ======
function setupNavigation() {
    const prevBtn = document.getElementById('prev-week');
    const nextBtn = document.getElementById('next-week');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            currentWeekStart.setDate(currentWeekStart.getDate() - 7);
            loadAvailableShifts(); // Chỉ cần tải lại ca
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            currentWeekStart.setDate(currentWeekStart.getDate() + 7);
            loadAvailableShifts(); // Chỉ cần tải lại ca
        });
    }
}

// ====== TẢI DỮ LIỆU (TẢI 1 LẦN KHI VÀO TRANG) ======
async function loadData() {
    await loadMySchedule(); // Tải lịch của tôi trước
    await loadAvailableShifts(); // Sau đó tải ca có sẵn
}

// ====== HÀM MỚI: TẢI LỊCH LÀM CỦA TÔI ======
async function loadMySchedule() {
    try {
        const response = await fetch('/api/admin/my-schedule-list', {
             headers: getAuthHeaders(false)
        });
        if (!response.ok) {
            throw new Error('Không thể tải trạng thái đăng ký');
        }
        const data = await response.json();
        mySchedule = data.schedule || [];
    } catch (error) {
        console.error('Lỗi tải đăng ký:', error);
        mySchedule = [];
    }
}

// ====== TẢI CA LÀM CÓ SẴN ======
async function loadAvailableShifts() {
    try {
        showLoading(true);
        
        const weekEnd = new Date(currentWeekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        
        const startDate = formatDateForAPI(currentWeekStart);
        const endDate = formatDateForAPI(weekEnd);
        
        const response = await fetch(`/api/admin/all-schedules?start_date=${startDate}&end_date=${endDate}`, {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            availableShifts = processShiftsData(data);
            renderShiftsTable();
            updateWeekLabel();
        } else {
            showError('Không thể tải danh sách ca làm');
        }
    } catch (error) {
        console.error('Lỗi tải ca làm:', error);
        showError('Không thể tải danh sách ca làm');
    } finally {
        showLoading(false);
    }
}

// ====== XỬ LÝ DỮ LIỆU CA LÀM (ĐÃ BỎ "availableSlots") ======
function processShiftsData(scheduleData) {
    const shifts = [];
    for (const [dateStr, dayShifts] of Object.entries(scheduleData)) {
        dayShifts.forEach(shift => {
            shifts.push({
                ...shift,
                ngay: dateStr
                // Đã xóa logic "availableSlots: 5 - ..."
            });
        });
    }
    shifts.sort((a, b) => {
        if (a.ngay === b.ngay) {
            return a.start_time.localeCompare(b.start_time);
        }
        return a.ngay.localeCompare(b.ngay);
    });
    return shifts;
}

// ====== RENDER BẢNG CA LÀM (ĐÃ SỬA) ======
function renderShiftsTable() {
    const tbody = document.querySelector('#shifts-table tbody');
    
    if (availableShifts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">Không có ca làm nào trong tuần này</td></tr>';
        return;
    }
    
    tbody.innerHTML = availableShifts.map(shift => {
        const registrationStatus = checkIfRegistered(shift.maca); 
        
        let buttonHtml = '';
        if (registrationStatus === 'approved') {
            buttonHtml = '<button class="btn btn-success btn-sm" disabled><i class="fas fa-check"></i> Đã duyệt</button>';
        } else if (registrationStatus === 'pending') {
            buttonHtml = '<button class="btn btn-secondary btn-sm" disabled>Chờ duyệt</button>';
        } else {
            // Nút đăng ký mặc định
            buttonHtml = `<button class="btn btn-primary btn-sm" onclick="registerForShift(${shift.maca})">
                            <i class="fas fa-plus"></i> Đăng ký
                          </button>`;
        }

        return `
            <tr>
                <td>${formatDateDisplay(shift.ngay)}</td>
                <td class='d-none'>Ca #${shift.maca}</td>
                <td>${shift.start_time} - ${shift.end_time}</td>
                <td>${buttonHtml}</td>
            </tr>
        `;
    }).join('');
}

// ====== KIỂM TRA ĐÃ ĐĂNG KÝ CHƯA ======
function checkIfRegistered(maca) {
    const found = mySchedule.find(item => item.ten_ca === `Ca #${maca}`);
    if (found) {
        return found.trangthai_code; // 'approved' hoặc 'pending'
    }
    return false;
}

// ====== ĐĂNG KÝ CA LÀM ======
async function registerForShift(maca) {
    const doRegister = async () => {
        try {
            const response = await fetch('/api/admin/shifts/register', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ maca: maca })
            });
            const data = await response.json();
            
            if (response.ok) {
                showSuccess(data.msg || 'Đăng ký ca làm thành công');
                await loadData(); // Tải lại cả lịch và ca
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra khi đăng ký ca');
        }
    };
    
    showConfirm("Xác nhận đăng ký", "Bạn muốn đăng ký ca làm này?", doRegister);
}

// ====== CẬP NHẬT LABEL TUẦN ======
function updateWeekLabel() {
    const label = document.getElementById('current-week');
    if (!label) return;
    const weekEnd = new Date(currentWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    label.textContent = `${formatDateForAPI(currentWeekStart)} - ${formatDateForAPI(weekEnd)}`;
}

// ====== HELPER FUNCTIONS ======
function getMonday(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
}
function formatDateForAPI(date) {
    return date.toISOString().split('T')[0];
}
function formatDateDisplay(dateStr) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + 1); // Fix lỗi múi giờ (nếu cần)
    return date.toLocaleDateString('vi-VN', {
        weekday: 'short',
        month: '2-digit',
        day: '2-digit'
    });
}
function showLoading(show) {
    const tbody = document.querySelector('#shifts-table tbody');
    if (show) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
}
// (Các hàm showToast, showSuccess, showError, showConfirm giữ nguyên)
// ... (Hãy đảm bảo bạn đã copy các hàm này từ file shifts.js hoặc file layout)
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