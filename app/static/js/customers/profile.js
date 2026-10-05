// ==================== AUTH HELPER ====================
function getAuthToken() {
    return window.CustomerAuth
        ? window.CustomerAuth.getAccessToken()
        : localStorage.getItem('access_token');
}

function getAuthHeaders(includeContentType = true) {
    const token = getAuthToken();
    const headers = {};

    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
        headers['Accept'] = 'application/json';
    }
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

function customerAuthFetch(input, options) {
    return window.CustomerAuth
        ? window.CustomerAuth.fetch(input, options)
        : fetch(input, options);
}

// ==================== INIT ====================
window.addEventListener('hashchange', () => {
    const section = location.hash.slice(1);
    if (section && document.getElementById(`${section}-section`)) switchSection(section);
});
document.addEventListener('DOMContentLoaded', async function() {
    initMenuLinks();
    initAvatarUpload();
    initForms();
    
    // Link trực tiếp (#treatments, #loyalty, ...) mở đúng tab; mặc định là Lịch hẹn.
    const initialSection = location.hash.slice(1);
    switchSection(initialSection && document.getElementById(`${initialSection}-section`) ? initialSection : 'appointments');

    await initializeProfilePage();
    const reviewId = Number(new URLSearchParams(location.search).get('review'));
    if (reviewId > 0) {
        switchSection('appointments');
        openReviewModal(reviewId, 'Lịch hẹn đã hoàn thành');
    }
});

// ==================== CHECK LOGIN ====================
async function initializeProfilePage() {
    let token = getAuthToken();
    if (!token && window.CustomerAuth) {
        token = await window.CustomerAuth.restoreAccessToken();
    }

    if (!token) {
        window.CustomerAuth.redirectToLogin(
            'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
            location.pathname + location.search + location.hash
        );
        return;
    }

    await Promise.all([loadUserProfile(), loadUserAppointments()]);
}

// ==================== LOAD USER PROFILE ====================
async function loadUserProfile() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/auth/login?redirect=/profile';
        return;
    }

    try {
        const response = await customerAuthFetch('/api/profile', {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            if (response.status === 401 || response.status === 422) {
                window.CustomerAuth.redirectToLogin(
                    'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
                    location.pathname + location.search + location.hash
                );
            } else {
                displayProfileLoadError();
            }
            return;
        }
        
        const data = await response.json();
        
        if (data.success && data.user) {
            displayUserInfo(data.user);
        } else {
            displayProfileLoadError(data.message);
        }
    } catch (error) {
        console.error('Error loading profile:', error);
        displayProfileLoadError('Không thể tải thông tin. Vui lòng thử lại.');
    }
}

// ==================== DISPLAY USER INFO ====================
function setDynamicProfileText(elementId, value) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.textContent = value;
    // translateDOM caches the initial "Loading..." value. Keep that cache in
    // sync so changing language cannot overwrite data loaded from the API.
    element.setAttribute('data-orig-vi', value);
}

function displayUserInfo(user) {
    setDynamicProfileText('userName', user.hoten || 'Chưa cập nhật');
    setDynamicProfileText('userEmail', user.email || 'Chưa cập nhật');
    
    const avatarImgEl = document.getElementById('avatarImg');
    if (avatarImgEl) {
        avatarImgEl.src = user.anhdaidien ? `/api/profile/avatar/${user.anhdaidien}` : '/static/images/default-avatar.svg';
        avatarImgEl.onerror = function() {
            this.onerror = null;
            this.src = '/static/images/default-avatar.svg';
        };
    }
    
    // Info section
    setDynamicProfileText('infoHoten', user.hoten || 'Chưa cập nhật');
    setDynamicProfileText('infoEmail', user.email || 'Chưa cập nhật');
    setDynamicProfileText('infoSdt', user.sdt || 'Chưa cập nhật');
    setDynamicProfileText('infoDiachi', user.diachi || 'Chưa cập nhật');
    
    // Edit form
    document.getElementById('editHoten').value = user.hoten;
    document.getElementById('editSdt').value = user.sdt || '';
    document.getElementById('editDiachi').value = user.diachi || '';

    if (typeof window.changeLang === 'function') {
        window.changeLang(localStorage.getItem('spa_lang') || 'vi');
    }
}

function displayProfileLoadError(message = 'Không thể tải thông tin') {
    setDynamicProfileText('userName', message);
    setDynamicProfileText('userEmail', 'Vui lòng tải lại trang');
    setDynamicProfileText('infoHoten', message);
    setDynamicProfileText('infoEmail', 'Vui lòng tải lại trang');
    setDynamicProfileText('infoSdt', 'Không có dữ liệu');
    setDynamicProfileText('infoDiachi', 'Không có dữ liệu');
}

// ==================== MENU NAVIGATION ====================
function initMenuLinks() {
    const menuLinks = document.querySelectorAll('.menu-link');
    
    menuLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const sectionName = this.getAttribute('data-section');
            switchSection(sectionName);
        });
    });
    document.querySelectorAll('[data-goto-section]').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            switchSection(link.dataset.gotoSection);
        });
    });
}

// Chỉnh sửa thông tin / đổi mật khẩu thuộc nhóm Tài khoản trên menu.
const SECTION_MENU = { edit: 'info', password: 'info' };

function switchSection(sectionName) {
    document.querySelectorAll('.profile-section').forEach(section => {
        section.classList.remove('active');
    });
    
    document.getElementById(`${sectionName}-section`).classList.add('active');
    
    const menuSection = SECTION_MENU[sectionName] || sectionName;
    document.querySelectorAll('.menu-link').forEach(link => {
        const isActive = link.getAttribute('data-section') === menuSection;
        link.classList.toggle('active', isActive);
        if (isActive) {
            link.setAttribute('aria-current', 'page');
            // Mobile: tab hiện hành luôn nằm trong vùng nhìn của thanh tab kéo ngang.
            link.scrollIntoView?.({ block: 'nearest', inline: 'center' });
        } else {
            link.removeAttribute('aria-current');
        }
    });
    if (location.hash !== `#${sectionName}`) {
        history.replaceState(null, '', `${location.pathname}${location.search}#${sectionName}`);
    }
    
    // Load data khi chuyển section
    if (sectionName === 'appointments') {
        loadUserAppointments();
    } else if (sectionName === 'invoices') {
        loadUserInvoices();
    } else if (sectionName === 'treatments') {
        window.PackageCare?.loadTreatments();
    } else if (sectionName === 'reviews') {
        window.ReviewUI?.loadMy();
    } else if (sectionName === 'loyalty') {
        window.CustomerLoyalty?.load();
    }
}

// ==================== AVATAR UPLOAD ====================
function initAvatarUpload() {
    const avatarInput = document.getElementById('avatarInput');
    
    avatarInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            showAlert('error', 'Vui lòng chọn file ảnh!');
            return;
        }
        
        if (file.size > 2 * 1024 * 1024) {
            showAlert('error', 'File ảnh không được vượt quá 2MB!');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('avatarImg').src = e.target.result;
        };
        reader.readAsDataURL(file);
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const token = getAuthToken();
            const response = await customerAuthFetch('/api/profile/upload-avatar', {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert('success', 'Cập nhật avatar thành công!');
            } else {
                showAlert('error', data.message || 'Upload avatar thất bại!');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showAlert('error', 'Có lỗi xảy ra khi upload!');
        }
    });
}

// ==================== FORM HANDLERS ====================
function initForms() {
    // Edit profile form
    const editForm = document.getElementById('editProfileForm');
    editForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            hoten: document.getElementById('editHoten').value,
            sdt: document.getElementById('editSdt').value,
            diachi: document.getElementById('editDiachi').value
        };
        
        try {
            const response = await customerAuthFetch('/api/profile/update', {
                method: 'PUT',
                headers: getAuthHeaders(true),
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('success', 'Cập nhật thông tin thành công!');
                await loadUserProfile();
                setTimeout(() => switchSection('info'), 1500);
            } else {
                showAlert('error', result.message || 'Cập nhật thất bại!');
            }
        } catch (error) {
            console.error('Update error:', error);
            showAlert('error', 'Có lỗi xảy ra!');
        }
    });
    
    // Change password form
    const passwordForm = document.getElementById('changePasswordForm');
    passwordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const oldPassword = document.getElementById('oldPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (newPassword !== confirmPassword) {
            showAlert('error', 'Mật khẩu mới không khớp!');
            return;
        }
        
        try {
            const response = await customerAuthFetch('/api/profile/change-password', {
                method: 'PUT',
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    matkhau_cu: oldPassword,
                    matkhau_moi: newPassword
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showAlert('success', 'Đổi mật khẩu thành công!');
                passwordForm.reset();
            } else {
                showAlert('error', result.message || 'Đổi mật khẩu thất bại!');
            }
        } catch (error) {
            console.error('Change password error:', error);
            showAlert('error', 'Có lỗi xảy ra!');
        }
    });
}

// ==================== LOAD APPOINTMENTS ====================
async function loadUserAppointments() {
    try {
        const response = await customerAuthFetch('/api/appointments/my-appointments', {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load appointments');
        }
        
        const data = await response.json();
        
        if (data.success && data.appointments) {
            displayAppointments(data.appointments);
        } else {
            displayNoAppointments();
        }
    } catch (error) {
        console.error('Error loading appointments:', error);
        displayNoAppointments();
    }
}

let myAppointments = [];

function displayAppointments(appointments) {
    myAppointments = appointments;
    const list = document.getElementById('appointmentsList');
    
    if (appointments.length === 0) {
        displayNoAppointments();
        return;
    }
    
    list.innerHTML = appointments.map(apt => {
        // Nhãn tiếng Việt lấy từ server (AppointmentStatus.VI_MAP) để admin và hồ sơ dùng chung.
        const statusMap = {
            'pending': { text: 'Chờ xác nhận', class: 'status-pending' },
            'confirmed': { text: 'Đã xác nhận', class: 'status-confirmed' },
            'in_progress': { text: 'Đang thực hiện', class: 'status-in-progress' },
            'completed': { text: 'Đã hoàn thành', class: 'status-completed' },
            'cancelled': { text: 'Đã hủy', class: 'status-cancelled' }
        };
        const known = statusMap[apt.trangthai];
        const status = {
            text: apt.trangthai_vi && apt.trangthai_vi !== apt.trangthai ? apt.trangthai_vi : (known ? known.text : 'Không xác định'),
            class: known ? known.class : 'status-pending'
        };
        
        return `
            <li class="appointment-item">
                <div class="appointment-header">
                    <h3>${apt.dichvu || 'Dịch vụ'}</h3>
                    <span class="appointment-status ${status.class}">
                        ${status.text}
                    </span>
                </div>
                <div class="appointment-details">
                    <p><i class="fas fa-calendar"></i> ${formatDate(apt.ngaygio)}</p>
                    <p><i class="fas fa-user"></i> ${apt.nhanvien || 'Chưa phân công'}</p>
                    ${apt.ghichu ? `<p><i class="fas fa-sticky-note" aria-hidden="true"></i> ${escapeProfileHtml(apt.ghichu)}</p>` : ''}
                    ${apt.invoice && apt.trangthai !== 'cancelled' ? `<p class="appointment-payment ${apt.invoice.trangthai === 'Đã thanh toán' ? 'is-paid' : ''}">
                        <i class="fas fa-${apt.invoice.trangthai === 'Đã thanh toán' ? 'circle-check' : 'clock'}" aria-hidden="true"></i>
                        ${apt.invoice.trangthai === 'Đã thanh toán' ? 'Đã thanh toán trước' : 'Chờ thanh toán'} · ${formatCurrency(apt.invoice.payable_amount)}</p>` : ''}
                    ${apt.last_service_change_at || apt.checked_in_at ? `<p class="appointment-events">
                        ${apt.last_service_change_at ? `<span><i class="fas fa-exchange-alt" aria-hidden="true"></i> Đã đổi dịch vụ lúc ${escapeProfileHtml(apt.last_service_change_at)}</span>` : ''}
                        ${apt.checked_in_at ? `<span><i class="fas fa-user-check" aria-hidden="true"></i> Check-in lúc ${escapeProfileHtml(apt.checked_in_at)}</span>` : ''}
                    </p>` : ''}
                </div>
                <div class="appointment-actions" style="margin-top: 15px; display: flex; flex-wrap: wrap; gap: 10px;">
                    ${apt.can_change_services ? `
                        <button type="button" class="btn btn-primary" style="padding: 8px 15px; font-size: 14px;" onclick="openChangeServices(${apt.malh})">
                            <i class="fas fa-exchange-alt" aria-hidden="true"></i> Đổi dịch vụ
                        </button>` : ''}
                    ${apt.invoice && apt.invoice.trangthai === 'Chưa thanh toán' && ['pending', 'confirmed'].includes(apt.trangthai) ? `
                        <button type="button" class="btn btn-primary" style="padding: 8px 15px; font-size: 14px;" onclick="payPrepaidInvoice(${apt.invoice.mahd})">
                            <i class="fas fa-qrcode" aria-hidden="true"></i> Thanh toán ngay
                        </button>` : ''}
                    ${apt.can_cancel ? `
                        <button type="button" class="btn btn-outline" style="padding: 8px 15px; font-size: 14px;" onclick="cancelAppointment(${apt.malh})">
                            <i class="fas fa-times" aria-hidden="true"></i> Hủy lịch
                        </button>` : ''}
                    ${!apt.can_cancel && ['pending', 'confirmed'].includes(apt.trangthai) ? `
                        <p class="appointment-hint">Đã đến giờ hẹn. Nếu bạn không đến trong 30 phút, lịch sẽ tự động hủy và hoàn lại buổi gói (nếu có).</p>` : ''}
                    ${apt.trangthai === 'completed' ? (window.ReviewUI?.appointmentActions(apt.malh) || '') : ''}
                </div>
            </li>
        `;
    }).join('');
}

function displayNoAppointments() {
    const list = document.getElementById('appointmentsList');
    list.innerHTML = `
        <li style="text-align: center; padding: 40px; color: #999;">
            <i class="fas fa-calendar-times" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
            <p>Bạn chưa có lịch hẹn nào</p>
            <a href="/appointments/create" class="btn btn-primary" style="margin-top: 20px; display: inline-block;">
                <i class="fas fa-plus"></i> Đặt lịch ngay
            </a>
        </li>
    `;
}

async function cancelAppointment(id) {
    if (!confirm('Bạn có chắc muốn hủy lịch hẹn này?')) return;
    
    try {
        const response = await customerAuthFetch(`/api/appointments/${id}/cancel`, {
            method: 'PUT',
            headers: getAuthHeaders(true)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('success', 'Hủy lịch hẹn thành công! Buổi gói đã giữ (nếu có) được hoàn lại.');
            loadUserAppointments();
        } else {
            // API trả lý do ở "message"; hiện đúng lý do thay vì câu chung chung.
            showAlert('error', data.message || data.msg || 'Không thể hủy lịch hẹn!');
        }
    } catch (error) {
        console.error('Cancel error:', error);
        showAlert('error', 'Có lỗi xảy ra!');
    }
}

// ==================== ĐỔI DỊCH VỤ (trước giờ hẹn) ====================
function escapeProfileHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

async function openChangeServices(malh) {
    const apt = myAppointments.find(a => a.malh === malh);
    if (!apt || !window.ChangeServicesDialog) return;
    try {
        const [servicesRes, treatmentsRes] = await Promise.all([
            customerAuthFetch('/api/services', { headers: getAuthHeaders(false) }).then(r => r.json()),
            customerAuthFetch('/api/packages/my-treatments', { headers: getAuthHeaders(false) })
                .then(r => r.ok ? r.json() : { treatments: [] }).catch(() => ({ treatments: [] })),
        ]);
        const current = new Map((apt.services || []).map(s => [s.madv, { package: s.package, label: 'Đang dùng buổi gói' }]));
        const day = apt.ngaygio.slice(0, 10);
        // Lượt gói còn dùng được vào ngày hẹn, cho dịch vụ thêm mới.
        const packageOptions = madv => (treatmentsRes.treatments || []).flatMap(t => t.status === 'cancelled' ? [] :
            t.items.filter(i => i.madv === madv && i.usable !== false && i.available_sessions > 0
                && (!i.effective_expires_at || i.effective_expires_at.slice(0, 10) >= day)
                && (!i.valid_from || i.valid_from.slice(0, 10) <= day))
                .map(i => ({ value: `${t.mathe}:${i.id}`, label: `${i.source_type === 'gift' ? 'Quà tặng' : 'Dùng buổi gói'}: ${t.tengoi} — còn ${i.available_sessions} buổi` })));
        const services = (servicesRes.services || []).filter(s => s.active !== false || current.has(s.madv));
        window.ChangeServicesDialog.open({
            title: 'Đổi dịch vụ',
            subtitle: `Lịch #${malh} · ${escapeProfileHtml(formatDate(apt.ngaygio))} · giữ nguyên giờ hẹn và kỹ thuật viên. Dịch vụ bỏ đi sẽ được hoàn buổi gói.`,
            services, current, packageOptions, startAt: apt.ngaygio,
            submit: async (madv_list, package_usages) => {
                const response = await customerAuthFetch(`/api/appointments/${malh}/services`, {
                    method: 'PUT', headers: getAuthHeaders(true), body: JSON.stringify({ madv_list, package_usages }),
                });
                const data = await response.json();
                if (!response.ok || !data.success) throw new Error(data.message || 'Không thể đổi dịch vụ');
                showAlert('success', `Đã đổi dịch vụ. Dự kiến kết thúc lúc ${data.end_time}.`);
                loadUserAppointments();
            },
        });
    } catch (error) {
        showAlert('error', 'Không tải được danh sách dịch vụ. Vui lòng thử lại.');
    }
}
window.openChangeServices = openChangeServices;

// Thanh toán hóa đơn trả trước; khi hộp đóng (đã trả hoặc để sau) thì tải lại danh sách lịch.
async function payPrepaidInvoice(mahd) {
    await window.LoyaltyPayment.openCustomerInvoice(mahd);
    const watcher = setInterval(() => {
        if (!document.getElementById('customerLoyaltyPayment')) {
            clearInterval(watcher);
            loadUserAppointments();
        }
    }, 400);
}
window.payPrepaidInvoice = payPrepaidInvoice;

// ==================== LOAD INVOICES ====================
async function loadUserInvoices() {
    try {
        const response = await customerAuthFetch('/api/payment/invoices', {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load invoices');
        }
        
        const invoices = await response.json();
        displayInvoices(invoices);
    } catch (error) {
        console.error('Error loading invoices:', error);
        displayNoInvoices();
    }
}

function displayInvoices(invoices) {
    const list = document.getElementById('invoicesList');
    
    if (!invoices || invoices.length === 0) {
        displayNoInvoices();
        return;
    }
    
    list.innerHTML = invoices.map(invoice => `
        <li class="invoice-item">
            <div class="invoice-header">
                <div class="invoice-info">
                    <div class="invoice-detail">
                        <span class="invoice-label">Mã hóa đơn</span>
                        <span class="invoice-value">#${invoice.mahd}</span>
                    </div>
                    <div class="invoice-detail">
                        <span class="invoice-label">Ngày lập</span>
                        <span class="invoice-value">${formatDate(invoice.ngaylap)}</span>
                    </div>
                    <div class="invoice-detail">
                        <span class="invoice-label">Tổng tiền</span>
                        <span class="invoice-amount">${formatCurrency(invoice.payable_amount ?? invoice.tongtien)}</span>
                    </div>
                </div>
                <span class="invoice-status status-${getStatusClass(invoice.trangthai)}">
                    ${getStatusText(invoice.trangthai)}
                </span>
            </div>
            
            <div class="invoice-actions">
                <button class="btn btn-outline btn-sm" onclick="viewInvoiceDetails(${invoice.mahd})">
                    <i class="fas fa-eye"></i> Xem chi tiết
                </button>
                ${invoice.trangthai !== 'Đã thanh toán' ? `
                    <button class="btn btn-primary btn-sm" onclick="payInvoice(${invoice.mahd}, ${invoice.tongtien})">
                        <i class="fas fa-credit-card"></i> Thanh toán
                    </button>
                ` : ''}
            </div>
        </li>
    `).join('');
}

function displayNoInvoices() {
    const list = document.getElementById('invoicesList');
    list.innerHTML = `
        <li style="text-align: center; padding: 40px; color: #999;">
            <i class="fas fa-receipt" style="font-size: 48px; margin-bottom: 15px; display: block;"></i>
            <p>Bạn chưa có hóa đơn nào</p>
        </li>
    `;
}

// ==================== INVOICE DETAILS MODAL ====================
async function viewInvoiceDetails(invoiceId) {
    try {
        const response = await customerAuthFetch(`/api/payment/invoices/${invoiceId}`, {
            headers: getAuthHeaders(true)
        });
        
        if (!response.ok) {
            throw new Error('Failed to load invoice details');
        }
        
        const invoice = await response.json();
        showInvoiceModal(invoice);
    } catch (error) {
        console.error('Error loading invoice details:', error);
        showAlert('error', 'Không thể tải chi tiết hóa đơn!');
    }
}

function showInvoiceModal(invoice) {
    const modal = document.createElement('div');
    modal.className = 'invoice-details-modal active';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 style="margin: 0;">Chi tiết hóa đơn #${invoice.mahd}</h3>
                <button class="modal-close" onclick="this.closest('.invoice-details-modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="invoice-info" style="margin-bottom: 20px;">
                <div class="invoice-detail">
                    <span class="invoice-label">Ngày lập</span>
                    <span class="invoice-value">${formatDate(invoice.ngaylap)}</span>
                </div>
                <div class="invoice-detail">
                    <span class="invoice-label">Trạng thái</span>
                    <span class="invoice-status status-${getStatusClass(invoice.trangthai)}">
                        ${getStatusText(invoice.trangthai)}
                    </span>
                </div>
            </div>
            
            <h4>Chi tiết dịch vụ</h4>
            <ul class="details-list">
                ${invoice.chitiet ? invoice.chitiet.map(item => `
                    <li class="detail-item">
                        <span class="detail-name">${item.tendv}</span>
                        <span class="detail-quantity">${item.soluong} x</span>
                        <span class="detail-price">${formatCurrency(item.dongia)}</span>
                        <span class="detail-total">${formatCurrency(item.thanhtien)}</span>
                    </li>
                `).join('') : '<li>Không có chi tiết</li>'}
            </ul>
            
              <div class="total-section">
                ${window.LoyaltyPayment ? LoyaltyPayment.summary(invoice) : 'Tổng cộng: '+formatCurrency(invoice.tongtien)}
            </div>
            
            ${invoice.trangthai !== 'Đã thanh toán' ? `
                <div class="invoice-actions" style="margin-top: 20px; justify-content: center;">
                    <button class="btn btn-primary" onclick="payInvoice(${invoice.mahd}, ${invoice.tongtien})">
                        <i class="fas fa-credit-card"></i> Thanh toán ngay
                    </button>
                </div>
            ` : ''}
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// ==================== PAYMENT HANDLING (ĐÃ SỬA: TẠO QR MOMO) ====================
async function ensureQRCodeLoaded() {
    if (typeof QRCode !== 'undefined') return true;
    return new Promise((resolve) => {
        const localScript = document.createElement('script');
        localScript.src = '/static/js/admin/qrcode.min.js';
        localScript.onload = () => resolve(typeof QRCode !== 'undefined');
        localScript.onerror = () => {
            const cdnScript = document.createElement('script');
            cdnScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
            cdnScript.onload = () => resolve(typeof QRCode !== 'undefined');
            cdnScript.onerror = () => resolve(false);
            document.head.appendChild(cdnScript);
        };
        document.head.appendChild(localScript);
    });
}

async function payInvoice(invoiceId, amount) {
    if(window.LoyaltyPayment?.openCustomerInvoice){
        try{await LoyaltyPayment.openCustomerInvoice(invoiceId);}catch(error){showAlert('error',error.message);}
        return;
    }
    if (!confirm(`Bạn có chắc muốn thanh toán hóa đơn #${invoiceId} với số tiền ${formatCurrency(amount)}? Hệ thống sẽ tạo mã QR Momo.`)) {
        return;
    }
    
    try {
        showQRModal(invoiceId); // Hiện modal QR
        
        const response = await customerAuthFetch(`/api/payment/invoices/${invoiceId}/generate-qr`, {
            method: 'POST',
            headers: getAuthHeaders(true),
        });
        
        const data = await response.json();
        
        if (response.ok && data.qrCodeUrl) {
            
            const qrContainer = document.getElementById('qr-code-container-cust');
            qrContainer.innerHTML = '';
            
            if (data.qrCodeUrl.startsWith('http://') || data.qrCodeUrl.startsWith('https://')) {
                const img = document.createElement('img');
                img.src = data.qrCodeUrl;
                img.alt = 'Mã QR VietQR';
                img.style.maxWidth = '250px';
                img.style.width = '100%';
                img.style.borderRadius = '8px';
                img.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                img.style.margin = '10px auto';
                qrContainer.appendChild(img);
            } else {
                const qrDiv = document.createElement('div');
                qrDiv.id = `qrcode-canvas-${invoiceId}`;
                qrDiv.style.margin = '20px auto';
                qrContainer.appendChild(qrDiv);
                
                const qrLoaded = await ensureQRCodeLoaded();
                if (qrLoaded && typeof QRCode !== 'undefined') {
                     new QRCode(qrDiv, {
                        text: data.qrCodeUrl,
                        width: 200,
                        height: 200,
                        colorDark: "#000000",
                        colorLight: "#ffffff",
                        correctLevel: QRCode.CorrectLevel.H
                    });
                }
            }
            
            qrContainer.insertAdjacentHTML('afterend', `
                <div class="bank-info-box" style="background: #f8fafc; padding: 12px; border-radius: 8px; margin-top: 10px; text-align: left; font-size: 13px; border: 1px solid #e2e8f0;">
                    <p style="margin: 3px 0;"><strong>Chủ TK:</strong> ${data.accountName || 'DANG VAN KHOA'}</p>
                    <p style="margin: 3px 0;"><strong>Số TK:</strong> <span style="color: #005baa; font-weight: bold;">${data.accountNo || '19071655175011'}</span> (${data.bank || 'Techcombank'})</p>
                    <p style="margin: 3px 0;"><strong>Nội dung:</strong> <span style="color: #d97706; font-weight: bold;">${data.description || ('HD' + invoiceId)}</span></p>
                </div>
            `);
            
            startCustomerPaymentPolling(invoiceId);
            
        } else {
            closeQRModal();
            showAlert('error', data.msg || 'Không thể tạo mã VietQR!');
        }
    } catch (error) {
        closeQRModal();
        console.error('Payment error:', error);
        showAlert('error', 'Có lỗi xảy ra khi tạo mã VietQR!');
    }
}

// ==================== HÀM HIỂN THỊ QR (MỚI) ====================
function showQRModal(invoiceId) {
    const modal = document.createElement('div');
    modal.className = 'qr-payment-modal active';
    modal.id = 'qrPaymentModal';
    
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.7); display: flex; justify-content: center; 
        align-items: center; z-index: 10000;
    `;
    
    modal.innerHTML = `
        <div class="modal-content" style="width: 350px; padding: 20px; text-align: center; border-radius: 12px; background: white;">
            <div class="modal-header" style="justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px;">
                <h3 style="margin: 0; font-size: 16px; color: #005baa;"><i class="fas fa-qrcode"></i> Thanh toán VietQR #${invoiceId}</h3>
                <button class="modal-close" onclick="closeQRModal()" style="border: none; background: transparent; font-size: 18px; cursor: pointer;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div id="qr-code-container-cust" style="display: flex; justify-content: center; align-items: center; min-height: 220px;">
                <div class="text-center" style="padding: 30px;">
                    <i class="fas fa-spinner fa-spin" style="font-size: 24px; color: #005baa;"></i>
                    <p style="margin-top: 10px;">Đang tạo mã VietQR...</p>
                </div>
            </div>
            <p id="customer-payment-status" style="margin-top: 15px; font-weight: 600; color: #005baa; font-size: 13px;">
                <i class="fas fa-spinner fa-spin"></i> Đang chờ tự động nhận tiền...
            </p>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeQRModal();
        }
    });
}

function closeQRModal() {
    const modal = document.getElementById('qrPaymentModal');
    if (modal) {
        modal.remove();
        document.body.style.overflow = 'auto';
    }
    
    if (window.customerPollingInterval) {
        clearInterval(window.customerPollingInterval);
        window.customerPollingInterval = null;
    }
}

// ==================== POLLING (MỚI) ====================
let customerPollingAttempts = 0;
const MAX_CUSTOMER_POLLING_ATTEMPTS = 60;

async function startCustomerPaymentPolling(invoiceId) {
    customerPollingAttempts = 0;
    
    window.customerPollingInterval = setInterval(async () => {
        customerPollingAttempts++;
        
        try {
            const response = await customerAuthFetch(`/api/payment/invoices/${invoiceId}`, {
                headers: getAuthHeaders(false)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.trangthai === 'Đã thanh toán') {
                    clearInterval(window.customerPollingInterval);
                    
                    const statusDiv = document.getElementById('customer-payment-status');
                    if (statusDiv) {
                        statusDiv.textContent = 'Thanh toán thành công!';
                        statusDiv.style.color = '#155724';
                    }
                    
                    showAlert('success', 'Thanh toán Momo thành công!');
                    
                    setTimeout(() => {
                        closeQRModal();
                        loadUserInvoices(); 
                    }, 2000);
                }
            }
            
            if (customerPollingAttempts >= MAX_CUSTOMER_POLLING_ATTEMPTS) {
                clearInterval(window.customerPollingInterval);
                const statusDiv = document.getElementById('customer-payment-status');
                if (statusDiv) {
                    statusDiv.textContent = 'Quá thời gian chờ thanh toán.';
                    statusDiv.style.color = '#721c24';
                }
            }
            
        } catch (error) {
            console.error('Lỗi polling:', error);
        }
        
    }, 3000);
}

// ==================== UTILITY FUNCTIONS ====================
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(amount);
}

function getStatusClass(status) {
    const statusMap = {
        'Đã thanh toán': 'paid',
        'Chờ thanh toán': 'pending',
        'Đã hủy': 'cancelled'
    };
    return statusMap[status] || 'pending';
}

function getStatusText(status) {
    const statusMap = {
        'Đã thanh toán': 'Đã thanh toán',
        'Chờ thanh toán': 'Chờ thanh toán',
        'Đã hủy': 'Đã hủy'
    };
    return statusMap[status] || status;
}

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#d4edda' : '#f8d7da'};
        color: ${type === 'success' ? '#155724' : '#721c24'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    alertDiv.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        ${message}
    `;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}


// Review context also handles existing reviews from email links.
function openReviewModal(malh) {
    return window.ReviewUI.openAppointmentReview(malh);
}
document.addEventListener('reviews-updated', () => {
    if (document.getElementById('appointments-section')?.classList.contains('active')) loadUserAppointments();
});
