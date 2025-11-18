// ====== BIẾN GLOBAL ======
let allShifts = [];
let allStaff = [];

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    // 1. Tải dữ liệu chính
    loadShifts();
    loadStaff();
    
    // 2. Tạo các lựa chọn cho dropdown giờ/phút
    populateTimePickers(); 

    // 3. Gắn sự kiện submit cho form TẠO/SỬA CA LÀM
    document.getElementById('shiftForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const id = document.getElementById('shift-id').value;
        const date = document.getElementById('shift-date').value;
        
        const startHour = document.getElementById('shift-start-hour').value;
        const startMinute = document.getElementById('shift-start-minute').value;
        const endHour = document.getElementById('shift-end-hour').value;
        const endMinute = document.getElementById('shift-end-minute').value;

        const startTime = `${startHour}:${startMinute}`;
        const endTime = `${endHour}:${endMinute}`;
        
        if (endTime <= startTime) {
            showError("Giờ kết thúc phải sau giờ bắt đầu.");
            return;
        }

        let method = 'POST';
        let url = '/api/admin/shifts';
        
        if (id) {
            method = 'PUT';
            url = `/api/admin/shifts/${id}`;
        }
        
        const payload = {
            ngay: date,
            giobatdau: startTime,
            gioketthuc: endTime
        };

        try {
            // Giả định getAuthHeaders() trả về headers cần thiết cho POST/PUT (có Content-Type)
            const response = await fetch(url, {
                method: method,
                headers: getAuthHeaders(), 
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showSuccess(data.msg || (id ? 'Cập nhật thành công' : 'Tạo ca thành công'));
                closeShiftModal();
                loadShifts(); // Tải lại bảng
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra khi lưu ca');
        }
    });

    // 4. Gắn sự kiện submit cho form LỌC
    document.getElementById('filterForm').addEventListener('submit', function(e) {
        e.preventDefault();
        loadShifts(); 
    });
    
    // 5. Thêm nút Reset vào HTML và gắn sự kiện (Nếu có nút Reset trong HTML)
    // Tạm thời bỏ qua phần gán sự kiện nếu nút không có sẵn
});

// ====== HÀM MỚI: CẬP NHẬT THẺ THỐNG KÊ ======
function updateStats() {
    const countElement = document.getElementById('total-shifts-count');
    if (countElement) {
        countElement.textContent = allShifts.length;
    }
}

// ====== HÀM MỚI: RESET BỘ LỌC ======
function resetFilter() {
    document.getElementById('filter-date-from').value = '';
    document.getElementById('filter-date-to').value = '';
    document.getElementById('filter-assignment').value = '';
    loadShifts(); // Tải lại dữ liệu sau khi reset
}


// ====== TẠO LỰA CHỌN GIỜ/PHÚT ======
function populateTimePickers() {
    const hourSelects = document.querySelectorAll('#shift-start-hour, #shift-end-hour');
    const minuteSelects = document.querySelectorAll('#shift-start-minute, #shift-end-minute');

    let hourOptions = '';
    for (let i = 0; i < 24; i++) {
        const hour = i.toString().padStart(2, '0');
        hourOptions += `<option value="${hour}">${hour}</option>`;
    }
    
    const minuteSteps = ['00', '15', '30', '45'];
    let minuteOptions = minuteSteps.map(m => `<option value="${m}">${m}</option>`).join('');

    hourSelects.forEach(select => { select.innerHTML = hourOptions; });
    minuteSelects.forEach(select => { select.innerHTML = minuteOptions; });

    document.getElementById('shift-start-hour').value = '09';
    document.getElementById('shift-start-minute').value = '00';
    document.getElementById('shift-end-hour').value = '18';
    document.getElementById('shift-end-minute').value = '00';
}

// ====== TẢI DANH SÁCH CA LÀM (ĐÃ SỬA LỖI 401) ======
async function loadShifts() {
    try {
        showLoading(true);
        
        // 1. ĐỌC GIÁ TRỊ TỪ BỘ LỌC
        const dateFrom = document.getElementById('filter-date-from').value;
        const dateTo = document.getElementById('filter-date-to').value;
        const assignment = document.getElementById('filter-assignment').value; // 'assigned' hoặc 'unassigned'

        // 2. TẠO CHUỖI QUERY PARAMETERS
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (assignment) params.append('assignment', assignment); 

        const queryString = params.toString();
        const url = `/api/admin/shifts${queryString ? `?${queryString}` : ''}`;
        
        // SỬA LỖI 401: Gửi headers đúng cấu trúc
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('admin_token')}` 
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                // Xử lý lỗi xác thực rõ ràng hơn cho người dùng
                throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
            }
            const errorData = await response.json();
            throw new Error(errorData.msg || `HTTP ${response.status}`);
        }
        
        allShifts = await response.json();
        renderShiftsTable(); 
        updateStats(); 
        
    } catch (error) {
        console.error('Lỗi tải ca làm:', error);
        document.getElementById('total-shifts-count').textContent = 'N/A'; 
        showError(`Không thể tải danh sách ca làm: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// ====== TẢI DANH SÁCH NHÂN VIÊN ======
async function loadStaff() {
    try {
        // Giữ nguyên loadStaff() vì log cho thấy nó đã hoạt động (200 OK)
        const response = await fetch('/api/admin/staff/list-all', {
            headers: getAuthHeaders(false) 
        });
        
        if (response.ok) {
            allStaff = await response.json();
        } else {
             console.error('Lỗi tải nhân viên:', response.statusText);
        }
    } catch (error) {
        console.error('Lỗi tải nhân viên:', error);
    }
}

// ====== RENDER BẢNG CA LÀM (Giữ nguyên) ======
function renderShiftsTable() {
    const tbody = document.getElementById('shifts-table-body');
    
    if (allShifts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">Không có ca làm nào</td></tr>';
        return;
    }
    
    tbody.innerHTML = allShifts.map(shift => {
        const assignedStaff = shift.assigned_staff || []; 
        const staffNames = assignedStaff.length > 0 
            ? `${assignedStaff.length} nhân viên` 
            : 'Chưa có';
        
        const totalHours = (shift.sogio !== null && shift.sogio !== undefined) ? parseFloat(shift.sogio).toFixed(1) : 'N/A';
        
        return `
            <tr>
                <td>${shift.maca}</td>
                <td>${formatDate(shift.ngay)}</td>
                <td>${shift.start_time}</td>
                <td>${shift.end_time}</td>
                <td>${totalHours} giờ</td> 
                <td>${staffNames}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-info btn-sm" onclick="viewShiftDetail(${shift.maca})" title="Xem chi tiết">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-warning btn-sm" onclick="openEditShiftModal(${shift.maca})" title="Sửa ca">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-primary btn-sm" onclick="assignStaffToShift(${shift.maca})" title="Gán nhân viên">
                            <i class="fas fa-user-plus"></i>
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="deleteShift(${shift.maca})" title="Xóa ca">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// ====== MODAL TẠO CA LÀM (Giữ nguyên) ======
function openShiftModal() {
    document.getElementById('shiftForm').reset(); 
    document.getElementById('shift-id').value = ''; 
    document.getElementById('modal-title').textContent = 'Tạo ca làm mới';
    
    document.getElementById('shift-start-hour').value = '09';
    document.getElementById('shift-start-minute').value = '00';
    document.getElementById('shift-end-hour').value = '18';
    document.getElementById('shift-end-minute').value = '00';
    
    document.getElementById('shiftModal').style.display = 'flex';
}

// ====== MODAL SỬA CA LÀM (Giữ nguyên) ======
function openEditShiftModal(maca) {
    const shift = allShifts.find(s => s.maca === maca);
    if (!shift) return;
    
    document.getElementById('shift-id').value = shift.maca; 
    document.getElementById('shift-date').value = shift.ngay;
    document.getElementById('modal-title').textContent = 'Chỉnh sửa ca làm';

    const [startH, startM] = shift.start_time.split(':');
    const [endH, endM] = shift.end_time.split(':');
    
    document.getElementById('shift-start-hour').value = startH;
    document.getElementById('shift-start-minute').value = startM;
    document.getElementById('shift-end-hour').value = endH;
    document.getElementById('shift-end-minute').value = endM;
    
    document.getElementById('shiftModal').style.display = 'flex';
}


function closeShiftModal() {
    const modal = document.getElementById('shiftModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// ====== XEM CHI TIẾT CA LÀM (Giữ nguyên) ======
async function viewShiftDetail(maca) {
    const shift = allShifts.find(s => s.maca === maca);
    if (!shift) return;
    
    const assignedStaff = shift.assigned_staff || [];
    
    let staffListHtml = '';
    if (assignedStaff.length === 0) {
        staffListHtml = '<li>Chưa có nhân viên nào được gán cho ca này.</li>';
    } else {
        staffListHtml = assignedStaff.map(nv => `
            <li class="staff-list-item">
                <span>${nv.hoten} (${nv.chucvu || 'Chưa có'})</span>
                <button class="btn-unassign" onclick="unassignStaff(${shift.maca}, ${nv.manv})" title="Hủy gán nhân viên này">
                    &times;
                </button>
            </li>
        `).join('');
    }

    const totalHours = (shift.sogio !== null && shift.sogio !== undefined) ? parseFloat(shift.sogio).toFixed(1) : 'N/A';

    const modalHtml = `
        <div id="viewDetailModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Chi tiết ca làm (Mã ca: ${shift.maca})</h3>
                    <span class="close" onclick="closeViewDetailModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <p><strong>Ngày:</strong> <span>${formatDate(shift.ngay)}</span></p>
                    <p><strong>Giờ làm:</strong> <span>${shift.start_time} - ${shift.end_time}</span></p>
                    <p><strong>Tổng số giờ:</strong> <span>${totalHours} giờ</span></p>
                    <hr>
                    <h4>Nhân viên đã gán (${assignedStaff.length}):</h4>
                    <ul class="staff-list-detail">
                        ${staffListHtml}
                    </ul>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeViewDetailModal()">Đóng</button>
                </div>
            </div>
        </div>
    `;
    
    closeViewDetailModal(); 
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function closeViewDetailModal() {
    const modal = document.getElementById('viewDetailModal');
    if (modal) {
        modal.remove();
    }
}

// ====== GÁN NHÂN VIÊN VÀO CA (Giữ nguyên) ======
async function assignStaffToShift(maca) {
    if (allStaff.length === 0) {
        showError("Chưa tải được danh sách nhân viên. Vui lòng thử lại.");
        return;
    }

    const shift = allShifts.find(s => s.maca === maca);
    if (!shift) {
        showError("Không tìm thấy thông tin ca làm.");
        return;
    }

    const assignedStaffIds = (shift.assigned_staff || []).map(nv => nv.manv);
    const availableStaff = allStaff.filter(s => 
        s.trangthai === true && !assignedStaffIds.includes(s.manv)
    );

    const staffOptions = availableStaff
        .map(s => `<option value="${s.manv}">${s.hoten} - ${s.chucvu || 'N/A'}</option>`)
        .join('');
    
    let staffSelectHtml = '';
    if (availableStaff.length === 0) {
        staffSelectHtml = `
            <select id="assign-staff" class="form-control" disabled>
                <option value="">Đã gán hết nhân viên</option>
            </select>
        `;
    } else {
        staffSelectHtml = `
            <select id="assign-staff" class="form-control" required>
                <option value="">-- Chọn nhân viên --</option>
                ${staffOptions}
            </select>
        `;
    }

    const html = `
        <div id="assignModal" class="modal" style="display: flex;">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Gán nhân viên vào ca</h3>
                    <span class="close" onclick="closeAssignModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <form id="assignForm">
                        <div class="form-group">
                            <label>Chọn nhân viên <span class="required">*</span></label>
                            ${staffSelectHtml}
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary" onclick="closeAssignModal()">Hủy</button>
                            <button type="submit" class="btn btn-primary" ${availableStaff.length === 0 ? 'disabled' : ''}>Gán</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    closeAssignModal();
    document.body.insertAdjacentHTML('beforeend', html);
    
    document.getElementById('assignForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const manv = document.getElementById('assign-staff').value;
        if (!manv) { showError("Vui lòng chọn nhân viên"); return; }
        
        try {
            const response = await fetch('/api/admin/shifts/assign', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ maca: maca, manv: parseInt(manv) })
            });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Gán nhân viên thành công');
                closeAssignModal();
                loadShifts();
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra khi gán');
        }
    });
}

function closeAssignModal() {
    const modal = document.getElementById('assignModal');
    if (modal) { modal.remove(); }
}

function showConfirm(title, message, onConfirm) {
    const oldModal = document.getElementById('confirm-toast-modal');
    if (oldModal) { oldModal.remove(); }

    const modalHtml = `
        <div id="confirm-toast-modal">
            <div class="confirm-toast-content">
                <div class="confirm-toast-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h4>${title}</h4>
                </div>
                <div class="confirm-toast-body">
                    ${message}
                </div>
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

// ====== HÀM MỚI: HỦY GÁN NHÂN VIÊN (Giữ nguyên) ======
async function unassignStaff(maca, manv) {

    const doUnassign = async () => {
        try {
            const response = await fetch('/api/admin/shifts/unassign', {
                method: 'DELETE',
                headers: getAuthHeaders(),
                body: JSON.stringify({ maca: maca, manv: manv })
            });

            const data = await response.json();

            if (response.ok) {
                showSuccess(data.msg || 'Hủy gán thành công');
                await loadShifts(); 
                closeViewDetailModal();
                setTimeout(() => { viewShiftDetail(maca); }, 100); 
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi khi hủy gán:', error);
            showError('Có lỗi xảy ra');
        }
    };

    const title = "Xác nhận hủy gán";
    const message = `Bạn có chắc muốn hủy gán nhân viên (Mã NV: ${manv}) khỏi ca (Mã ca: ${maca})?\n\nLương của ca này sẽ bị hoàn trả.`;

    showConfirm(title, message, doUnassign);
}

// ====== XÓA CA LÀM (Giữ nguyên) ======
async function deleteShift(maca) {

    const doDelete = async () => {
        try {
            // SỬA: Đảm bảo gửi header xác thực cho DELETE
            const response = await fetch(`/api/admin/shifts/${maca}`, {
                method: 'DELETE',
                headers: getAuthHeaders() 
            });
            const data = await response.json();
            if (response.ok) {
                showSuccess(data.msg || 'Xóa ca làm thành công');
                loadShifts(); 
            } else {
                showError(data.msg || 'Có lỗi xảy ra');
            }
        } catch (error) {
            console.error('Lỗi:', error);
            showError('Có lỗi xảy ra khi xóa');
        }
    };

    const title = "Xác nhận xóa ca";
    const message = "Bạn có chắc muốn xóa ca làm này? Hãy đảm bảo không có nhân viên nào trong ca này.";

    showConfirm(title, message, doDelete);
}

// ====== HELPER FUNCTIONS (Giữ nguyên) ======
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('vi-VN', { 
        day: '2-digit', 
        month: '2-digit' 
    }).replace('/', '-'); 
}

function showLoading(show) {
    const tbody = document.getElementById('shifts-table-body');
    if (show) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
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