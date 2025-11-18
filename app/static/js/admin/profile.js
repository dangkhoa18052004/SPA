// app/static/js/admin/profile.js
// Giả định hàm getAuthHeaders, getStatusClass, getAppointmentStatusText tồn tại trong base JS

let currentProfile = {};

document.addEventListener('DOMContentLoaded', function() {
    loadProfileData();
    setupTabSwitching();
    document.getElementById('profile-form')?.addEventListener('submit', handleProfileUpdate);
    document.getElementById('password-form')?.addEventListener('submit', handlePasswordChange);
    document.getElementById('schedule-start-date')?.addEventListener('change', loadMySchedule);
    document.getElementById('schedule-end-date')?.addEventListener('change', loadMySchedule);
    
    // Đặt ngày mặc định cho lịch hẹn
    const today = new Date().toISOString().split('T')[0];
    const startDateElement = document.getElementById('schedule-start-date');
    const endDateElement = document.getElementById('schedule-end-date');

    if (startDateElement) startDateElement.value = today;
    if (endDateElement) endDateElement.value = today;

    // Load lịch hẹn ban đầu
    loadMySchedule();
});

// ====== TAB SWITCHING LOGIC ======
function setupTabSwitching() {
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.dataset.tab;
            
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            document.querySelectorAll('.tab-pane').forEach(pane => pane.style.display = 'none');
            
            const selectedPane = document.getElementById(tabId);
            if (selectedPane) { 
                 selectedPane.style.display = 'block';
            }
        });
    });
    
    // Khởi tạo trạng thái ban đầu:
    const profilePane = document.getElementById('profile');
    const passwordPane = document.getElementById('password');
    const schedulePane = document.getElementById('schedule');

    if (profilePane) profilePane.style.display = 'block';
    if (passwordPane) passwordPane.style.display = 'none';
    if (schedulePane) schedulePane.style.display = 'none';
}

// ====== BỔ SUNG: HÀM ĐIỀN DỮ LIỆU VÀO INPUTS ======
function populateFormInputs() {
    if (Object.keys(currentProfile).length === 0) return;

    document.getElementById('hoten').value = currentProfile.hoten || '';
    // Đảm bảo SĐT không bị null
    document.getElementById('sdt').value = currentProfile.sdt || ''; 
    document.getElementById('email').value = currentProfile.email || '';
    document.getElementById('diachi').value = currentProfile.diachi || '';
    
    // Trường chỉ xem
    document.getElementById('role').value = currentProfile.role ? currentProfile.role.toUpperCase() : currentProfile.chucvu || 'N/A';
}


// ====== LOAD PROFILE DATA (ĐÃ SỬA GỌI API) ======
async function loadProfileData() {
    try {
        const response = await fetch('/api/profile', { headers: getAuthHeaders(false) });
        if (!response.ok) throw new Error("Không thể tải profile");
        
        const result = await response.json();
        currentProfile = result.user;

        // Xử lý đường dẫn Avatar
        const avatarField = currentProfile.anhnhanvien || currentProfile.anhdaidien;
        const avatarWrapper = document.querySelector('.profile-avatar-wrapper');
        const currentAvatarImg = document.getElementById('current-avatar'); 
        
        // 1. Logic hiển thị ảnh / icon
        if (avatarField && currentAvatarImg) {
            const avatarSrc = `/api/profile/avatar/${avatarField}`;
            currentAvatarImg.src = avatarSrc;
            
            avatarWrapper.classList.remove('no-avatar'); 
            currentAvatarImg.style.display = 'block';
        } else {
            if (currentAvatarImg) {
                currentAvatarImg.style.display = 'none';
            }
            avatarWrapper.classList.add('no-avatar'); 
        }
        
        // 2. Điền dữ liệu vào form sau khi tải thành công
        populateFormInputs();

    } catch (error) {
         console.error('Lỗi tải profile:', error);
         showError('Lỗi tải thông tin cá nhân.');
    }
}


// ====== EDIT MODE TOGGLE (ĐÃ SỬA: Điền dữ liệu khi Bật chế độ sửa) ======
function toggleEditMode(enable) {
    const inputs = document.querySelectorAll('#profile-form input');
    const actions = document.getElementById('save-actions');
    const editBtn = document.getElementById('edit-profile-btn');
    const uploadGroup = document.querySelector('.avatar-upload-group');

    inputs.forEach(input => {
        if (input.id !== 'role') {
            input.readOnly = !enable;
        }
    });

    if (enable) {
        // QUAN TRỌNG: ĐIỀN LẠI DỮ LIỆU GỐC NGAY KHI BẬT CHẾ ĐỘ SỬA
        populateFormInputs(); 

        actions.style.display = 'flex';
        editBtn.style.display = 'none';
        uploadGroup.style.display = 'block';
    } else {
        actions.style.display = 'none';
        editBtn.style.display = 'block';
        uploadGroup.style.display = 'none';
        // Tải lại dữ liệu từ cache khi hủy
        loadProfileData(); 
    }
}

// ====== PROFILE UPDATE LOGIC (PUT) ======
async function handleProfileUpdate(e) {
    e.preventDefault();
    
    const data = {
        hoten: document.getElementById('hoten').value,
        sdt: document.getElementById('sdt').value,
        email: document.getElementById('email').value,
        diachi: document.getElementById('diachi').value
    };

    try {
        const response = await fetch('/api/profile/update', {
            method: 'PUT',
            headers: getAuthHeaders(true),
            body: JSON.stringify(data)
        });

        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Cập nhật thành công!');
            toggleEditMode(false);
            loadProfileData(); // Cập nhật lại cache
        } else {
            showError(result.message || 'Cập nhật thất bại.');
        }
    } catch (error) {
        console.error('Lỗi update profile:', error);
        showError('Lỗi hệ thống khi cập nhật.');
    }
}

// ====== AVATAR UPLOAD LOGIC (POST) ======
async function handleAvatarUpload() {
    const fileInput = document.getElementById('avatar-file-input');
    if (!fileInput.files.length) {
        return showError('Vui lòng chọn file ảnh.');
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const response = await fetch('/api/profile/upload-avatar', {
            method: 'POST',
            headers: getAuthHeaders(false), // KHÔNG set Content-Type: application/json
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showSuccess(result.message || 'Cập nhật ảnh đại diện thành công!');
            
            const avatarSrc = `/api/profile/avatar/${result.filename}`;
            document.getElementById('current-avatar').src = avatarSrc;
            document.querySelector('.profile-avatar-wrapper').classList.remove('no-avatar');
            document.getElementById('current-avatar').style.display = 'block';

            fileInput.value = null; 
            
        } else {
            showError(result.message || 'Upload ảnh thất bại.');
        }
    } catch (error) {
        console.error('Lỗi upload avatar:', error);
        showError('Lỗi hệ thống khi upload ảnh.');
    }
}

// ====== PASSWORD CHANGE LOGIC (PUT) ======
async function handlePasswordChange(e) {
    e.preventDefault();
    
    const currentPass = document.getElementById('current-password').value;
    const newPass = document.getElementById('new-password').value;
    const confirmPass = document.getElementById('confirm-new-password').value;

    if (newPass !== confirmPass) { return showError('Mật khẩu mới không khớp.'); }
    if (newPass.length < 6) { return showError('Mật khẩu phải có ít nhất 6 ký tự.'); }

    const data = { matkhau_cu: currentPass, matkhau_moi: newPass };

    try {
        const response = await fetch('/api/profile/change-password', {
            method: 'PUT', headers: getAuthHeaders(true), body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            showSuccess(result.message || 'Đổi mật khẩu thành công! Vui lòng đăng nhập lại.');
            document.getElementById('password-form').reset();
        } else {
            showError(result.message || 'Đổi mật khẩu thất bại. Kiểm tra lại mật khẩu cũ.');
        }
    } catch (error) {
        console.error('Lỗi đổi mật khẩu:', error);
        showError('Lỗi hệ thống khi đổi mật khẩu.');
    }
}

// ====== MY SCHEDULE LOGIC (GET) ======
async function loadMySchedule() {
    const startDate = document.getElementById('schedule-start-date').value;
    const endDate = document.getElementById('schedule-end-date').value;
    const tbody = document.querySelector('#my-schedule-table tbody');

    if (!startDate || !endDate) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center">Vui lòng chọn ngày để xem lịch hẹn.</td></tr>`;
        return;
    }

    tbody.innerHTML = `<tr><td colspan="5" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>`;

    try {
        const url = `/api/admin/my-schedule-list?start_date=${startDate}&end_date=${endDate}`;
        const response = await fetch(url, { headers: getAuthHeaders(false) });
        
        const result = await response.json();

        if (response.ok && result.success && result.appointments) {
            if (result.appointments.length === 0) {
                 tbody.innerHTML = `<tr><td colspan="5" class="text-center">Không có lịch hẹn nào được gán trong thời gian này.</td></tr>`;
                 return;
            }

            tbody.innerHTML = result.appointments.map(apt => {
                const date = new Date(apt.ngaygio);
                const timeStr = date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
                const dateStr = date.toLocaleDateString('vi-VN');
                
                return `
                    <tr>
                        <td>#${apt.malh}</td>
                        <td>${dateStr} (${timeStr})</td>
                        <td>${apt.khachhang_hoten || 'Khách vãng lai'}</td>
                        <td>${apt.dichvu_ten || 'N/A'}</td>
                        <td><span class="badge badge-${getStatusClass(apt.trangthai)}">${getAppointmentStatusText(apt.trangthai)}</span></td>
                    </tr>
                `;
            }).join('');

        } else {
            showError(result.msg || 'Không thể tải lịch hẹn của bạn.');
            tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--danger-color)">❌ Lỗi: ${result.msg || 'Không tải được lịch.'}</td></tr>`;
        }
    } catch (error) {
        console.error('Lỗi load schedule:', error);
        showError('Lỗi hệ thống khi tải lịch hẹn.');
        tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--danger-color)">❌ Lỗi kết nối.</td></tr>`;
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
    toast.className = `toast toast-${type}`; 
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `<i class="fas ${iconClass}"></i> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, 3000);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}