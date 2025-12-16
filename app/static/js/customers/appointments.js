// ==================== IIFE để tránh conflict với main.js ====================
(function() {
    'use strict';

// ==================== AUTH HELPER ====================
function getAuthToken() {
    return localStorage.getItem('access_token');
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

// ==================== GLOBAL VARIABLES ====================
let selectedServices = [];
let allServices = [];
let selectedStaff = null;
let currentStep = 1;
let currentPage = 1;
let servicesPerPage = 8;
let filteredServices = [];

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', function() {
    loadAllServices();
    setupDateTimeLimits();
    autoSelectServiceFromURL();
});

// ==================== AUTO SELECT SERVICE FROM URL ====================
function autoSelectServiceFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const serviceId = urlParams.get('service');
    
    if (serviceId) {
        const checkServicesLoaded = setInterval(() => {
            if (allServices.length > 0) {
                clearInterval(checkServicesLoaded);
                
                const serviceIdNum = parseInt(serviceId);
                const service = allServices.find(s => s.madv === serviceIdNum);
                
                if (service) {
                    selectedServices = [serviceIdNum];
                    filteredServices = [service];
                    currentPage = 1;
                    displayServicesInForm(filteredServices);
                    updateSelectedServicesDisplay();
                    updateSummary();
                    addViewAllServicesButton();
                    
                    if (window.Toast) {
                        Toast.success(`Đã chọn dịch vụ: ${service.tendv}`, 'Thông báo', 3000);
                    }
                    
                    setTimeout(() => {
                        document.getElementById('servicesSelection')?.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                        });
                    }, 500);
                }
            }
        }, 100);
        
        setTimeout(() => clearInterval(checkServicesLoaded), 5000);
    }
}

function addViewAllServicesButton() {
    const container = document.getElementById('servicesSelection');
    if (!container) return;
    
    const buttonHTML = `
        <div style="grid-column: 1/-1; text-align: center; margin-top: 15px;">
            <button class="btn btn-outline" onclick="showAllServices()" type="button" style="padding: 10px 20px;">
                <i class="fas fa-list"></i> Xem tất cả dịch vụ
            </button>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', buttonHTML);
}

function showAllServices() {
    filteredServices = allServices;
    currentPage = 1;
    displayServicesInForm(filteredServices);
    
    const container = document.getElementById('servicesSelection');
    const viewAllBtn = container?.querySelector('div[style*="grid-column"]');
    if (viewAllBtn) viewAllBtn.remove();
}

// ==================== LOAD SERVICES ====================
async function loadAllServices() {
    try {
        const response = await fetch('/api/services', {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (data.success && data.services) {
            allServices = data.services;
            filteredServices = allServices;
            displayServicesInForm(filteredServices);
        }
    } catch (error) {
        console.error('Error loading services:', error);
        Toast.error('Không thể tải danh sách dịch vụ');
    }
}

function displayServicesInForm(services) {
    const container = document.getElementById('servicesSelection');
    if (!container) return;
    
    const totalPages = Math.ceil(services.length / servicesPerPage);
    const startIndex = (currentPage - 1) * servicesPerPage;
    const endIndex = startIndex + servicesPerPage;
    const currentServices = services.slice(startIndex, endIndex);
    
    container.innerHTML = currentServices.map(service => `
        <div class="service-card-small ${selectedServices.includes(service.madv) ? 'selected' : ''}" 
             data-service-id="${service.madv}"
             onclick="toggleServiceSelection(${service.madv})">
            <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                 alt="${service.tendv}"
                 onerror="this.src='/static/images/default-service.jpg'">
            <div class="service-info">
                <h4>${service.tendv}</h4>
                <p class="price">${formatPrice(service.gia)}</p>
                ${service.thoiluong ? `<p class="duration"><i class="fas fa-clock"></i> ${service.thoiluong} phút</p>` : ''}
            </div>
            <div class="service-check">
                <i class="fas fa-check"></i>
            </div>
        </div>
    `).join('');
    
    displayPagination(totalPages, services.length);
}

function displayPagination(totalPages, totalItems) {
    const container = document.getElementById('servicesSelection');
    if (!container) return;
    
    if (totalPages <= 1) return;
    
    const paginationHTML = `
        <div class="services-pagination" style="grid-column: 1/-1; display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 10px;">
            <button class="pagination-btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left"></i>
            </button>
            <span style="color: #666; font-size: 14px;">
                Trang ${currentPage} / ${totalPages} 
                <span style="color: #999;">(${totalItems} dịch vụ)</span>
            </span>
            <button class="pagination-btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                <i class="fas fa-chevron-right"></i>
            </button>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', paginationHTML);
}

function changePage(page) {
    const totalPages = Math.ceil(filteredServices.length / servicesPerPage);
    
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    displayServicesInForm(filteredServices);
    
    document.getElementById('servicesSelection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function filterServicesInForm() {
    const searchTerm = document.getElementById('serviceSearch').value.toLowerCase();
    
    if (searchTerm === '') {
        filteredServices = allServices;
    } else {
        filteredServices = allServices.filter(service => 
            service.tendv.toLowerCase().includes(searchTerm) ||
            (service.mota && service.mota.toLowerCase().includes(searchTerm))
        );
    }
    
    currentPage = 1;
    displayServicesInForm(filteredServices);
}

// ==================== SERVICE SELECTION ====================
function toggleServiceSelection(serviceId) {
    const index = selectedServices.indexOf(serviceId);
    
    if (index > -1) {
        selectedServices.splice(index, 1);
    } else {
        selectedServices.push(serviceId);
    }
    
    const card = document.querySelector(`[data-service-id="${serviceId}"]`);
    if (card) {
        card.classList.toggle('selected');
    }
    
    updateSelectedServicesDisplay();
    updateSummary();
    
    const date = document.getElementById('appointmentDate')?.value;
    const time = document.getElementById('appointmentTime')?.value;
    if (date && time && selectedServices.length > 0) {
        loadAvailableStaff();
    }
}

function updateSelectedServicesDisplay() {
    const container = document.getElementById('selectedServices');
    if (!container) return;
    
    if (selectedServices.length === 0) {
        container.innerHTML = '<p style="color: #999;">Chưa chọn dịch vụ nào</p>';
        return;
    }
    
    const selectedServicesData = allServices.filter(s => selectedServices.includes(s.madv));
    
    container.innerHTML = selectedServicesData.map(service => `
        <div class="selected-service-tag">
            <span>${service.tendv}</span>
            <button onclick="toggleServiceSelection(${service.madv})" type="button">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `).join('');
}

// ==================== DATE TIME SETUP ====================
function setupDateTimeLimits() {
    const dateInput = document.getElementById('appointmentDate');
    if (!dateInput) return;
    
    const today = new Date().toISOString().split('T')[0];
    dateInput.setAttribute('min', today);
    
    const maxDate = new Date();
    maxDate.setMonth(maxDate.getMonth() + 3);
    dateInput.setAttribute('max', maxDate.toISOString().split('T')[0]);
}

// ==================== LOAD AVAILABLE STAFF ====================
async function loadAvailableStaff() {
    const dateInput = document.getElementById('appointmentDate');
    const timeSelect = document.getElementById('appointmentTime');
    const staffContainer = document.getElementById('staffSelection');
    
    if (!dateInput || !timeSelect || !staffContainer) return;
    
    const date = dateInput.value;
    const time = timeSelect.value;
    
    if (!date || !time) {
        staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Vui lòng chọn ngày giờ để xem nhân viên rảnh</p>';
        return;
    }
    
    if (selectedServices.length === 0) {
        staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Vui lòng chọn dịch vụ trước</p>';
        return;
    }
    
    staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;"><i class="fas fa-spinner fa-spin"></i> Đang kiểm tra...</p>';
    
    try {
        const datetime = `${date}T${time}`;
        
        // === SỬA LỖI 1: Sửa URL tải nhân viên ===
        const staffResponse = await fetch('/api/staff', {
            headers: getAuthHeaders(false)
        });
        
        const staffData = await staffResponse.json();
        
        if (!staffData.success || !staffData.staff) {
            staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Không thể tải danh sách nhân viên</p>';
            return;
        }
        
        const availableStaff = [];
        
        for (const staff of staffData.staff) {
            // === SỬA LỖI 2: Sửa URL check lịch rảnh ===
            const checkResponse = await fetch('/api/appointments/check-availability', {
                method: 'POST', 
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    manv: staff.manv,
                    ngaygio: datetime,
                    madv_list: selectedServices  // Gửi tất cả dịch vụ
                })
            });
            
            const checkData = await checkResponse.json();
            
            availableStaff.push({
                ...staff,
                available: checkData.available,
                message: checkData.message
            });
        }
        
        if (availableStaff.length === 0) {
            staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Không có nhân viên nào</p>';
            return;
        }
        
        staffContainer.innerHTML = availableStaff.map(staff => `
            <div class="staff-card ${!staff.available ? 'unavailable' : ''} ${selectedStaff === staff.manv ? 'selected' : ''}"
                 onclick="${staff.available ? `selectStaff(${staff.manv}, '${staff.hoten}')` : ''}">
                <div class="staff-avatar">
                    ${staff.anhdaidien ? 
                        `<img src="/api/profile/avatar/${staff.anhdaidien}" alt="${staff.hoten}">` :
                        '<i class="fas fa-user-circle"></i>'}
                </div>
                <div class="staff-info">
                    <h4>${staff.hoten}</h4>
                    ${staff.chuyenmon ? `<p class="specialty">${staff.chuyenmon}</p>` : ''}
                    <p class="status ${staff.available ? 'available' : 'busy'}">
                        <i class="fas fa-circle"></i>
                        ${staff.available ? 'Còn trống' : 'Đã bận'}
                    </p>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading staff:', error);
        staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Có lỗi xảy ra khi tải nhân viên</p>';
    }
}

function selectStaff(staffId, staffName) {
    selectedStaff = staffId;
    
    document.querySelectorAll('.staff-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    event.currentTarget.classList.add('selected');
    
    const autoAssign = document.getElementById('autoAssign');
    if (autoAssign) {
        autoAssign.checked = false;
    }
    
    updateSummary();
}

// ==================== STEP NAVIGATION ====================
function goToStep(step) {
    if (step === 2 && selectedServices.length === 0) {
        Toast.warning('Vui lòng chọn ít nhất một dịch vụ!');
        return;
    }
    
    if (step === 3) {
        const date = document.getElementById('appointmentDate').value;
        const time = document.getElementById('appointmentTime').value;
        
        if (!date || !time) {
            Toast.warning('Vui lòng chọn ngày và giờ!');
            return;
        }
        
        loadAvailableStaff();
    }
    
    document.querySelectorAll('.form-step').forEach(s => {
        s.classList.remove('active');
    });
    
    document.getElementById(`step${step}`).classList.add('active');
    currentStep = step;
    
    updateSummary();
}

// ==================== UPDATE SUMMARY ====================
function updateSummary() {
    // Services
    const summaryServices = document.getElementById('summaryServices');
    if (summaryServices) {
        if (selectedServices.length === 0) {
            summaryServices.innerHTML = '<p class="empty-text">Chưa chọn dịch vụ</p>';
        } else {
            const selectedServicesData = allServices.filter(s => selectedServices.includes(s.madv));
            summaryServices.innerHTML = selectedServicesData.map(service => `
                <div class="summary-service-item">
                    <span>${service.tendv}</span>
                    <span>${formatPrice(service.gia)}</span>
                </div>
            `).join('');
        }
    }
    
    // DateTime
    const summaryDateTime = document.getElementById('summaryDateTime');
    if (summaryDateTime) {
        const date = document.getElementById('appointmentDate')?.value;
        const time = document.getElementById('appointmentTime')?.value;
        
        if (!date || !time) {
            summaryDateTime.innerHTML = '<p class="empty-text">Chưa chọn thời gian</p>';
        } else {
            const dateObj = new Date(date);
            const dateStr = dateObj.toLocaleDateString('vi-VN', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            summaryDateTime.innerHTML = `
                <p><i class="fas fa-calendar"></i> ${dateStr}</p>
                <p><i class="fas fa-clock"></i> ${time}</p>
            `;
        }
    }
    
    // Staff
    const summaryStaff = document.getElementById('summaryStaff');
    if (summaryStaff) {
        const autoAssign = document.getElementById('autoAssign')?.checked;
        
        if (autoAssign || !selectedStaff) {
            summaryStaff.innerHTML = '<p class="empty-text">Tự động sắp xếp</p>';
        } else {
            const staffName = document.querySelector(`.staff-card.selected h4`)?.textContent || 'Đã chọn';
            summaryStaff.innerHTML = `<p><i class="fas fa-user"></i> ${staffName}</p>`;
        }
    }
    
    // Total
    const summaryTotal = document.getElementById('summaryTotal');
    if (summaryTotal) {
        const selectedServicesData = allServices.filter(s => selectedServices.includes(s.madv));
        const total = selectedServicesData.reduce((sum, service) => sum + parseFloat(service.gia), 0);
        summaryTotal.textContent = formatPrice(total);
    }
}

// ==================== SUBMIT APPOINTMENT ====================
document.getElementById('appointmentForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (selectedServices.length === 0) {
        Toast.error('Vui lòng chọn ít nhất một dịch vụ!');
        return;
    }
    
    const date = document.getElementById('appointmentDate').value;
    const time = document.getElementById('appointmentTime').value;
    const autoAssign = document.getElementById('autoAssign').checked;
    
    if (!date || !time) {
        Toast.error('Vui lòng chọn ngày và giờ!');
        return;
    }
    
    const datetime = `${date}T${time}`;
    const manv = autoAssign ? null : selectedStaff;
    
    if (manv) {
        try {
            // === SỬA LỖI 2: Sửa URL check lịch rảnh ===
            const checkResponse = await fetch('/api/appointments/check-availability', {
                method: 'POST',
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    manv: manv,
                    ngaygio: datetime,
                    madv_list: selectedServices
                })
            });
            
            const checkData = await checkResponse.json();
            
            if (!checkData.available) {
                Toast.error(checkData.message || 'Khung giờ này đã bận!');
                return;
            }
        } catch (error) {
            console.error('Error checking availability:', error);
        }
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    
    try {
        // === SỬA LỖI 3: Sửa URL đặt lịch ===
        const response = await fetch('/api/appointments/create', {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({
                madv_list: selectedServices,
                ngaygio: datetime,
                manv: manv,
                ghichu: ''
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            Toast.success('Đặt lịch hẹn thành công! Chúng tôi đã gửi email xác nhận đến bạn.', 'Thành công!', 5000);
            
            setTimeout(() => {
                window.location.href = '/profile#appointments';
            }, 2000);
        } else {
            Toast.error(data.msg || 'Đặt lịch thất bại!');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check"></i> Xác nhận đặt lịch';
        }
    } catch (error) {
        console.error('Error booking appointment:', error);
        Toast.error('Có lỗi xảy ra. Vui lòng thử lại!');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-check"></i> Xác nhận đặt lịch';
    }
});

// ==================== UTILITY FUNCTIONS ====================
function formatPrice(price) {
    return new Intl.NumberFormat('vi-VN', { 
        style: 'currency', 
        currency: 'VND' 
    }).format(parseFloat(price));
}

// ==================== Expose functions to global scope ====================
window.toggleServiceSelection = toggleServiceSelection;
window.selectStaff = selectStaff;
window.goToStep = goToStep;
window.filterServicesInForm = filterServicesInForm;
window.changePage = changePage;
window.showAllServices = showAllServices;
window.loadAvailableStaff = loadAvailableStaff; // <-- SỬA LỖI 4: Thêm dòng này

})();