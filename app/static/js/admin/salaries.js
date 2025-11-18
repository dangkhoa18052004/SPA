// ====== BIẾN GLOBAL ======
let allSalaries = []; // Dữ liệu hiện tại đang hiển thị
let currentFilterType = 'month'; // 'month' hoặc 'day'

// Tiêu đề cho 2 chế độ xem
const MONTH_HEADER = `
    <tr>
        <th>Họ tên</th>
        <th>Tháng/Năm</th>
        <th>Tổng lương</th>
        <th>Lương cơ bản</th>
        <th>Thưởng</th>
        <th>Khấu trừ</th>
        <th>Thao tác</th>
    </tr>
`;

const DAY_HEADER = `
    <tr>
        <th>Họ tên</th>
        <th>Chức vụ</th>
        <th>Lương ca</th>
        <th>Thưởng ca</th>
        <th>Khấu trừ ca</th>
        <th>Tổng nhận (ca)</th>
        <th>Thao tác</th>
    </tr>
`;

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    // Set giá trị mặc định cho bộ lọc
    const now = new Date();
    const year = now.getFullYear();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    
    document.getElementById('filter-month-input').value = `${year}-${month}`;
    document.getElementById('filter-day-input').value = `${year}-${month}-${day}`;
    
    applySalaryFilter();
});

// ====== ĐIỀU KHIỂN BỘ LỌC ======
function toggleFilterInputs() {
    currentFilterType = document.getElementById('filter-type').value;
    if (currentFilterType === 'month') {
        document.getElementById('filter-month-group').style.display = 'flex';
        document.getElementById('filter-day-group').style.display = 'none';
    } else {
        document.getElementById('filter-month-group').style.display = 'none';
        document.getElementById('filter-day-group').style.display = 'flex';
    }
    applySalaryFilter();
}

// ====== TẢI LỊCH SỬ LƯƠNG (HÀM CHÍNH) ======
async function applySalaryFilter() {
    try {
        showLoading(true);
        
        const params = new URLSearchParams();
        params.append('filter_type', currentFilterType);
        
        let shouldProceed = true;

        if (currentFilterType === 'month') {
            const monthYear = document.getElementById('filter-month-input').value;
            if (monthYear) { 
                params.append('month_year', monthYear); 
            } else {
                // Nếu không chọn tháng, mặc định lấy tháng hiện tại (Backend tự xử lý)
            }
        } else {
            const day = document.getElementById('filter-day-input').value;
            if (!day) { 
                showError("Vui lòng chọn ngày"); 
                shouldProceed = false; 
            }
            params.append('day', day);
        }
        
        if (!shouldProceed) {
            showLoading(false);
            return;
        }

        const response = await fetch(`/api/admin/salaries?${params.toString()}`, {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.msg || `HTTP ${response.status}`);
        }
        
        allSalaries = await response.json();
        renderSalariesTable();
        updateSalaryStats(); // <--- CẬP NHẬT THỐNG KÊ
        
    } catch (error) {
        console.error('Lỗi tải lương:', error);
        showError(error.message || 'Không thể tải danh sách lương');
    } finally {
        showLoading(false);
    }
}

// ====== CẬP NHẬT STATS TỔNG LƯƠNG (HÀM MỚI) ======
function updateSalaryStats() {
    const titleElement = document.getElementById('total-salary-title');
    const valueElement = document.getElementById('total-salary-stat');
    let total = 0;
    
    if (!titleElement || !valueElement) return;

    if (currentFilterType === 'month') {
        // Tổng hợp lương tháng
        titleElement.textContent = 'Tổng Lương (Tháng)';
        // tongluong là tổng đã tính (luongcoban + thuong - khautru)
        total = allSalaries.reduce((sum, salary) => sum + parseFloat(salary.tongluong || 0), 0);
    } else {
        // Tổng hợp lương ngày
        titleElement.textContent = 'Tổng Lương (Ngày)';
        total = allSalaries.reduce((sum, salary) => {
            // Tổng ngày = lương ca + thưởng ca - khấu trừ ca
            const luongCa = parseFloat(salary.luong_ca || 0);
            const thuongCa = parseFloat(salary.thuong_ca || 0);
            const khautruCa = parseFloat(salary.khautru_ca || 0);
            return sum + (luongCa + thuongCa - khautruCa);
        }, 0);
    }
    
    valueElement.textContent = formatCurrency(total);
}

// ====== RENDER BẢNG LƯƠNG ======
function renderSalariesTable() {
    const thead = document.getElementById('salaries-table-head');
    const tbody = document.getElementById('salaries-table-body');
    
    if (currentFilterType === 'month') {
        // === RENDER BẢNG THÁNG ===
        thead.innerHTML = MONTH_HEADER;
        if (allSalaries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Chưa có dữ liệu lương</td></tr>';
            return;
        }
        tbody.innerHTML = allSalaries.map(salary => `
            <tr>
                <td>${salary.hoten || 'N/A'}</td>
                <td>${salary.thang}/${salary.nam}</td>
                <td><strong>${formatCurrency(salary.tongluong)}</strong></td>
                <td>${formatCurrency(salary.luongcoban || 0)}</td>
                <td class="text-success">+ ${formatCurrency(salary.thuong || 0)}</td>
                <td class="text-danger">- ${formatCurrency(salary.khautru || 0)}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-warning btn-sm" onclick="openMonthlyAdjustModal(${salary.maluong})" title="Điều chỉnh Thưởng/Phạt (Tổng hợp tháng)">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        
    } else {
        // === RENDER BẢNG NGÀY ===
        thead.innerHTML = DAY_HEADER;
        if (allSalaries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Không có dữ liệu lương</td></tr>';
            return;
        }
        tbody.innerHTML = allSalaries.map(salary => {
            // Tính tổng ngày
            const luongCa = parseFloat(salary.luong_ca || 0);
            const thuongCa = parseFloat(salary.thuong_ca || 0);
            const khautruCa = parseFloat(salary.khautru_ca || 0);
            const tongNgay = luongCa + thuongCa - khautruCa;

            return `
            <tr>
                <td>${salary.hoten || 'N/A'}</td>
                <td>${salary.chucvu || 'N/A'}</td>
                <td>${formatCurrency(luongCa)}</td>
                <td class="text-success">+ ${formatCurrency(thuongCa)}</td>
                <td class="text-danger">- ${formatCurrency(khautruCa)}</td>
                <td><strong>${formatCurrency(tongNgay)}</strong></td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-warning btn-sm" onclick="openDailyAdjustModal(${salary.id_chitiet})" title="Điều chỉnh Thưởng/Phạt (Ca này)">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </td>
            </tr>
            `;
        }).join('');
    }
}

// ====== XUẤT PDF ======
async function exportSalaryPDF() {
    showToast('Đang chuẩn bị file PDF, vui lòng chờ...', 'success');
    const filterType = document.getElementById('filter-type').value;
    const monthYear = document.getElementById('filter-month-input').value;
    const day = document.getElementById('filter-day-input').value;
    
    const params = new URLSearchParams();
    params.append('filter_type', filterType);
    params.append('month_year', monthYear);
    params.append('day', day);

    try {
        const response = await fetch(`/api/admin/salaries/export-pdf?${params.toString()}`, {
            method: 'GET',
            headers: getAuthHeaders(false) 
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.msg || 'Không thể tạo file PDF');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `bao_cao_luong_${filterType}_${day || monthYear}.pdf`;
        
        document.body.appendChild(a);
        a.click(); 
        
        window.URL.revokeObjectURL(url);
        a.remove();

    } catch (error) {
        console.error('Lỗi xuất PDF:', error);
        showError(error.message || 'Có lỗi xảy ra khi xuất PDF');
    }
}

// ====== TÍNH LƯƠNG (MODAL TỔNG HỢP) ======
function openCalculateSalaryModal() {
    const currentDate = new Date();
    const currentMonth = currentDate.getMonth() + 1;
    const currentYear = currentDate.getFullYear();
    
    const html = `
        <div id="calculateModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Tính lương tháng</h3>
                    <span class="close" onclick="closeCalculateModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <p style="margin-bottom: 15px;">Hệ thống sẽ tổng hợp lương chi tiết (theo ca) vào bảng lương tháng.</p>
                    <form id="calculateForm">
                        <div class="form-group">
                            <label>Tháng <span class="required">*</span></label>
                            <select id="salary-month" class="form-control" required>
                                ${Array.from({length: 12}, (_, i) => i + 1).map(m => 
                                    `<option value="${m}" ${m === currentMonth ? 'selected' : ''}>${m}</option>`
                                ).join('')}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Năm <span class="required">*</span></label>
                            <input type="number" id="salary-year" class="form-control" value="${currentYear}" required min="2020" max="2030">
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeCalculateModal()">Hủy</button>
                            <button type="submit" class="btn btn-primary">Tính lương</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', html);
    
    document.getElementById('calculateForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const month = document.getElementById('salary-month').value;
        const year = document.getElementById('salary-year').value;
        
        try {
            const response = await fetch('/api/admin/salaries/calculate', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ thang: parseInt(month), nam: parseInt(year) })
            });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Tổng hợp lương thành công');
                closeCalculateModal();
                applySalaryFilter(); 
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra');
        }
    });
}
function closeCalculateModal() {
    const modal = document.getElementById('calculateModal');
    if (modal) { modal.remove(); }
}

// ====== ĐIỀU CHỈNH LƯƠNG THÁNG (MODAL CŨ) ======
async function openMonthlyAdjustModal(maluong) {
    const salary = allSalaries.find(s => s.maluong === maluong);
    if (!salary) return;
    
    const html = `
        <div id="adjustModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Điều chỉnh lương tháng - ${salary.hoten}</h3>
                    <span class="close" onclick="closeAdjustModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <p>Lưu ý: Thưởng/Khấu trừ này sẽ <b>ghi đè</b> lên tổng thưởng/khấu trừ đã tính từ các ca.</p>
                    <form id="adjustForm">
                        <div class="form-group">
                            <label>Lương cơ bản (đã tổng hợp)</label>
                            <input type="text" class="form-control" value="${formatCurrency(salary.luongcoban || 0)}" disabled>
                        </div>
                        <div class="form-group">
                            <label>Thưởng (VNĐ)</label>
                            <input type="number" id="adjust-bonus" class="form-control" value="${parseFloat(salary.thuong || 0)}" min="0" step="1000">
                        </div>
                        <div class="form-group">
                            <label>Khấu trừ (VNĐ)</label>
                            <input type="number" id="adjust-deduction" class="form-control" value="${parseFloat(salary.khautru || 0)}" min="0" step="1000">
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeAdjustModal()">Hủy</button>
                            <button type="submit" class="btn btn-primary">Lưu</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', html);
    
    document.getElementById('adjustForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const bonus = document.getElementById('adjust-bonus').value;
        const deduction = document.getElementById('adjust-deduction').value;
        
        try {
            const response = await fetch(`/api/admin/salaries/${maluong}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    thuong: parseFloat(bonus),
                    khautru: parseFloat(deduction)
                })
            });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Điều chỉnh lương thành công');
                closeAdjustModal();
                applySalaryFilter(); 
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra');
        }
    });
}

// ====== HÀM MỚI: ĐIỀU CHỈNH LƯƠNG NGÀY (CA) ======
async function openDailyAdjustModal(id_chitiet) {
    const salary = allSalaries.find(s => s.id_chitiet === id_chitiet);
    if (!salary) return;
    
    const html = `
        <div id="adjustModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Điều chỉnh ca - ${salary.hoten}</h3>
                    <span class="close" onclick="closeAdjustModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <p>Điều chỉnh thưởng/phạt cho ca làm ngày <b>${formatDate(salary.ngay_lam)}</b></p>
                    <form id="adjustForm">
                        <div class="form-group">
                            <label>Lương ca (gốc)</label>
                            <input type="text" class="form-control" value="${formatCurrency(salary.luong_ca || 0)}" disabled>
                        </div>
                        <div class="form-group">
                            <label>Thưởng ca (VNĐ)</label>
                            <input type="number" id="adjust-bonus-daily" class="form-control" value="${parseFloat(salary.thuong_ca || 0)}" min="0" step="1000">
                        </div>
                        <div class="form-group">
                            <label>Khấu trừ ca (VNĐ)</label>
                            <input type="number" id="adjust-deduction-daily" class="form-control" value="${parseFloat(salary.khautru_ca || 0)}" min="0" step="1000">
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeAdjustModal()">Hủy</button>
                            <button type="submit" class="btn btn-primary">Lưu</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', html);
    
    document.getElementById('adjustForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const bonus = document.getElementById('adjust-bonus-daily').value;
        const deduction = document.getElementById('adjust-deduction-daily').value;
        
        try {
            // Gọi API mới
            const response = await fetch(`/api/admin/salaries/daily/${id_chitiet}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    thuong_ca: parseFloat(bonus),
                    khautru_ca: parseFloat(deduction)
                })
            });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Cập nhật ca thành công');
                closeAdjustModal();
                applySalaryFilter(); // Tải lại bảng
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra');
        }
    });
}

function closeAdjustModal() {
    const modal = document.getElementById('adjustModal');
    if (modal) { modal.remove(); }
}

// ====== HELPER FUNCTIONS ======
function formatCurrency(amount) {
    if (!amount) return '0₫';
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(parseFloat(amount));
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('vi-VN', { 
        day: '2-digit', 
        month: '2-digit',
        year: 'numeric'
    });
}

function showLoading(show) {
    const tbody = document.querySelector('#salaries-table-body');
    const thead = document.querySelector('#salaries-table-head');
    if (show) {
        thead.innerHTML = ''; 
        tbody.innerHTML = '<tr><td colspan="7" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
}

// ====== HỆ THỐNG TOAST ======
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