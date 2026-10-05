// ==================== IIFE để tránh conflict với main.js ====================
(function() {
    'use strict';

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

// ==================== GLOBAL VARIABLES ====================
let selectedServices = [];
let allServices = [];
let selectedStaff = null;
let currentStep = 1;
let currentPage = 1;
let servicesPerPage = 8;
let filteredServices = [];

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', async function() {
    setupDateTimeLimits();
    setupAutoAssignToggle();
    await loadAllServices();
    await applyBookingContext();
    updateSelectedServicesDisplay();
    await window.PackageCare?.renderBooking(selectedServices, document.getElementById('appointmentDate')?.value);
    updateSummary();
});

function setupAutoAssignToggle() {
    const autoAssign = document.getElementById('autoAssign');
    if (!autoAssign) return;

    autoAssign.addEventListener('change', function() {
        if (this.checked) {
            // The previous staff choice is no longer applicable once the
            // customer switches back to automatic assignment.
            selectedStaff = null;
            document.querySelectorAll('.staff-card.selected').forEach(card => {
                card.classList.remove('selected');
            });
        }

        updateSummary();
    });
}

// ==================== AUTO SELECT SERVICE FROM URL ====================
async function applyBookingContext() {
    const params = new URLSearchParams(location.search);
    const panel = document.getElementById('bookingContext');
    const esc = window.PackageCare?.esc || (value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
    const readId = key => params.has(key) && /^[1-9]\d*$/.test(params.get(key)) ? Number(params.get(key)) : null;
    const serviceId = readId('service'), treatmentId = readId('treatment'), itemId = readId('item');
    const notice = text => { panel.hidden=false; panel.textContent=text; };
    if (['service','treatment','item'].some(key=>params.has(key)&&!readId(key))) {
        notice('Thông tin đặt lịch không hợp lệ. Vui lòng chọn dịch vụ khác.'); return;
    }
    if (treatmentId) {
        try {
            const {treatment} = await PackageCare.api(`/api/packages/my-treatments/${treatmentId}`);
            const available = treatment.items.filter(i=>i.usable&&i.available_sessions>0&&allServices.some(s=>s.madv===i.madv));
            if (!available.length) { notice('Liệu trình không còn dịch vụ khả dụng hoặc đã hết hạn. Bạn có thể chọn dịch vụ khác.'); return; }
            const choices = available.filter(i=>(!serviceId||i.madv===serviceId)&&(!itemId||i.id===itemId));
            if (!choices.length) { notice('Dịch vụ/lượt đã chọn không thuộc liệu trình hoặc không còn khả dụng.'); return; }
            panel.hidden=false;
            panel.innerHTML=`<h4>Dịch vụ khả dụng trong gói của bạn</h4><p>${esc(treatment.tengoi)}</p>${available.map(i=>`<p>${i.source_type==='gift'?'🎁 ':''}${esc(i.tendv)} · Còn ${i.available_sessions} buổi <button type="button" class="btn btn-outline" data-booking-item="${i.id}">Đặt dịch vụ này</button></p>`).join('')}`;
            const choose = item => {
                selectedServices=[item.madv];
                PackageCare.chooseBookingItem(treatment,item);
                filteredServices=allServices.filter(s=>s.madv===item.madv);
                currentPage=1;displayServicesInForm(filteredServices);addViewAllServicesButton();
                updateSelectedServicesDisplay();updateSummary();
            };
            panel.querySelectorAll('[data-booking-item]').forEach(button=>button.onclick=()=>{
                const item=available.find(i=>i.id===Number(button.dataset.bookingItem));
                history.replaceState(null,'',`/appointments/create?treatment=${treatmentId}&service=${item.madv}&item=${item.id}`);
                choose(item);
            });
            // Multiple entitlement rows can still represent one available service.
            // Choose exactly one source: original package first, then the gift expiring soonest.
            const singleService = new Set(choices.map(item=>item.madv)).size===1;
            const selected = singleService ? [...choices].sort((a,b)=>
                Number(b.source_type==='package')-Number(a.source_type==='package') ||
                (a.effective_expires_at||'9999').localeCompare(b.effective_expires_at||'9999') || a.id-b.id
            )[0] : null;
            if(selected) choose(selected);
            else { filteredServices=allServices.filter(s=>available.some(i=>i.madv===s.madv));displayServicesInForm(filteredServices);addViewAllServicesButton(); }
        } catch(error) { notice(error.message || 'Không thể tải liệu trình của bạn.'); }
        return;
    }
    if (itemId) { notice('Vui lòng chọn liệu trình tương ứng với lượt dịch vụ.'); return; }
    if (serviceId) {
        const service=allServices.find(s=>s.madv===serviceId);
        if(!service){notice('Dịch vụ đã ngừng hoạt động hoặc không tồn tại. Vui lòng chọn dịch vụ khác.');return;}
        selectedServices=[serviceId];filteredServices=[service];currentPage=1;
        displayServicesInForm(filteredServices);addViewAllServicesButton();
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
        const response = await customerAuthFetch('/api/services', {
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

    // Tổng thời lượng đổi → khung giờ trống có thể đổi theo.
    if (document.getElementById('appointmentDate')?.value) {
        loadTimeSlots();
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

// ==================== STAFF AVAILABILITY HELPER ====================
function getStaffAvailabilityBadge(staff) {
    const reason = staff.reason;
    if (staff.available === true && reason === 'available') {
        return {
            statusClass: 'available',
            text: 'Còn trống',
            isSelectable: true
        };
    }

    switch (reason) {
        case 'appointment_conflict':
            return {
                statusClass: 'conflict',
                text: 'Đã có lịch',
                isSelectable: false
            };
        default:
            return null;
    }
}

// ==================== TIME SLOTS (theo tổng thời lượng và ca làm) ====================
let slotRequestVersion = 0;

function escapeText(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function formatViDate(iso) {
    return new Date(`${iso}T00:00:00`).toLocaleDateString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' });
}

async function loadTimeSlots() {
    const dateInput = document.getElementById('appointmentDate');
    const timeSelect = document.getElementById('appointmentTime');
    const status = document.getElementById('slotStatus');
    if (!dateInput || !timeSelect) return;

    const date = dateInput.value;
    const previous = timeSelect.value;
    if (!date) {
        timeSelect.innerHTML = '<option value="">-- Chọn ngày trước --</option>';
        if (status) status.textContent = '';
        updateSummary();
        return;
    }
    if (selectedServices.length === 0) {
        timeSelect.innerHTML = '<option value="">-- Chọn dịch vụ trước --</option>';
        if (status) status.textContent = 'Vui lòng chọn dịch vụ ở bước 1.';
        return;
    }

    // Chỉ phản hồi mới nhất được ghi; đổi ngày nhanh không bị phản hồi ngày cũ ghi đè.
    const version = ++slotRequestVersion;
    timeSelect.disabled = true;
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Đang tìm khung giờ còn trống...';

    try {
        const params = new URLSearchParams({ date, madv_list: selectedServices.join(','), suggest: '1' });
        const response = await customerAuthFetch(`/api/appointments/available-slots?${params}`, { headers: getAuthHeaders(false) });
        const data = await response.json().catch(() => ({}));
        if (version !== slotRequestVersion) return;
        if (!response.ok || !data.success || !Array.isArray(data.slots)) {
            throw new Error(data.message || 'Không kiểm tra được khung giờ');
        }

        const open = data.slots.filter(slot => slot.available);
        timeSelect.innerHTML = '<option value="">-- Chọn giờ --</option>' + data.slots
            .filter(slot => slot.reason !== 'past')
            .map(slot => `<option value="${slot.time}" ${slot.available ? '' : 'disabled'}>${slot.time}${slot.available ? '' : ' – hết chỗ'}</option>`)
            .join('');
        timeSelect.disabled = false;

        if (open.some(slot => slot.time === previous)) {
            timeSelect.value = previous;
        } else if (previous) {
            Toast.warning(`Khung giờ ${previous} không còn phù hợp với dịch vụ đã chọn. Vui lòng chọn giờ khác.`);
        }

        if (status) {
            if (open.length) {
                status.textContent = `${open.length} khung giờ còn trống cho ${data.duration_minutes} phút dịch vụ.`;
            } else {
                const suggestions = data.suggestions || [];
                status.innerHTML = `<p>Ngày này đã hết chỗ cho ${data.duration_minutes} phút dịch vụ.</p>` + (suggestions.length
                    ? `<p>Gợi ý gần nhất:</p><div class="slot-suggestions">${suggestions.map(s =>
                        `<button type="button" class="btn btn-outline" data-suggest-date="${s.date}" data-suggest-time="${s.time}">${formatViDate(s.date)} · ${s.time}</button>`).join('')}</div>`
                    : '<p>Không còn chỗ trong 14 ngày tới. Vui lòng liên hệ spa.</p>');
                status.querySelectorAll('[data-suggest-date]').forEach(button => button.onclick = async () => {
                    dateInput.value = button.dataset.suggestDate;
                    await loadTimeSlots();
                    timeSelect.value = button.dataset.suggestTime;
                    loadAvailableStaff();
                    updateSummary();
                });
            }
        }
        if (timeSelect.value) loadAvailableStaff();
        updateSummary();
    } catch (error) {
        if (version !== slotRequestVersion) return;
        // Lỗi kết nối/API không được báo là "đã bận".
        timeSelect.innerHTML = '<option value="">-- Chưa tải được giờ --</option>';
        timeSelect.disabled = false;
        if (status) {
            status.innerHTML = `<p class="slot-error">Không tải được khung giờ: ${escapeText(error.message)}</p><button type="button" class="btn btn-outline" data-retry-slots>Thử lại</button>`;
            status.querySelector('[data-retry-slots]').onclick = () => loadTimeSlots();
        }
        updateSummary();
    }
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

        // API chỉ trả kỹ thuật viên active có ca bao phủ khung giờ đã chọn.
        const response = await customerAuthFetch('/api/appointments/available-staff', {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({
                ngaygio: datetime,
                madv_list: selectedServices
            })
        });

        if (!response.ok) {
            showStaffError(staffContainer);
            return;
        }

        const data = await response.json();

        if (!data || !data.success || !Array.isArray(data.staff)) {
            showStaffError(staffContainer);
            return;
        }

        const workingStaff = data.staff.filter(staff => getStaffAvailabilityBadge(staff) !== null);

        // Nếu nhân viên đang chọn không còn khả dụng trong khung giờ mới, bỏ chọn
        if (selectedStaff) {
            const currentSelected = workingStaff.find(s => s.manv === selectedStaff);
            if (!currentSelected || !currentSelected.available) {
                selectedStaff = null;
                updateSummary();
            }
        }

        if (workingStaff.length === 0) {
            staffContainer.innerHTML = '<p style="text-align: center; color: #999; grid-column: 1/-1;">Không có kỹ thuật viên nào làm việc trong khung giờ này</p>';
            return;
        }

        staffContainer.innerHTML = workingStaff.map(staff => {
            const badge = getStaffAvailabilityBadge(staff);
            const isSelected = selectedStaff === staff.manv;
            return `
                <div class="staff-card ${!badge.isSelectable ? 'unavailable' : ''} ${isSelected ? 'selected' : ''}"
                     data-staff-id="${staff.manv}"
                     onclick="${badge.isSelectable ? `selectStaff(${staff.manv}, '${staff.hoten}', event)` : ''}">
                    <div class="staff-avatar">
                        ${staff.anhdaidien ?
                            `<img src="/api/profile/avatar/${staff.anhdaidien}" alt="${staff.hoten}" onerror="this.onerror=null; this.src='/static/images/default-avatar.svg';">` :
                            '<img src="/static/images/default-avatar.svg" alt="Avatar">'}
                    </div>
                    <div class="staff-info">
                        <h4>${staff.hoten}</h4>
                        ${staff.chuyenmon ? `<p class="specialty">${staff.chuyenmon}</p>` : ''}
                        <p class="status ${badge.statusClass}">
                            <i class="fas fa-circle"></i>
                            ${badge.text}
                        </p>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading staff:', error);
        showStaffError(staffContainer);
    }
}

function showStaffError(container) {
    container.innerHTML = '<div style="text-align: center; color: #d9534f; grid-column: 1/-1;"><p><i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Lỗi kiểm tra lịch (không phải do kín lịch).</p><button type="button" class="btn btn-outline" data-retry-staff>Thử lại</button></div>';
    container.querySelector('[data-retry-staff]').onclick = () => loadAvailableStaff();
}

function selectStaff(staffId, staffName, evt) {
    selectedStaff = staffId;

    document.querySelectorAll('.staff-card').forEach(card => {
        card.classList.remove('selected');
    });

    const cardEl = (evt && evt.currentTarget) ? evt.currentTarget : document.querySelector(`.staff-card[data-staff-id="${staffId}"]`);
    if (cardEl) {
        cardEl.classList.add('selected');
    }

    const autoAssign = document.getElementById('autoAssign');
    if (autoAssign) {
        autoAssign.checked = false;
    }

    updateSummary();
}

function updateWizardProgress(step) {
    const s1 = document.getElementById('wizStep1');
    const s2 = document.getElementById('wizStep2');
    const s3 = document.getElementById('wizStep3');
    const l1 = document.getElementById('wizLine1');
    const l2 = document.getElementById('wizLine2');

    if (s1 && s2 && s3) {
        s1.classList.remove('active', 'completed');
        s2.classList.remove('active', 'completed');
        s3.classList.remove('active', 'completed');
        if (l1) l1.classList.remove('active');
        if (l2) l2.classList.remove('active');

        if (step === 1) {
            s1.classList.add('active');
        } else if (step === 2) {
            s1.classList.add('completed');
            s2.classList.add('active');
            if (l1) l1.classList.add('active');
        } else if (step >= 3) {
            s1.classList.add('completed');
            s2.classList.add('completed');
            s3.classList.add('active');
            if (l1) l1.classList.add('active');
            if (l2) l2.classList.add('active');
        }
    }
}

// ==================== STEP NAVIGATION ====================
function goToStep(step) {
    if (step === 2 && selectedServices.length === 0) {
        Toast.warning('Vui lòng chọn ít nhất một dịch vụ!');
        return;
    }

    if (step === 2 && document.getElementById('appointmentDate')?.value) {
        loadTimeSlots();
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

    const targetStep = document.getElementById(`step${step}`);
    if (targetStep) {
        targetStep.classList.add('active');
    }

    currentStep = step;
    updateWizardProgress(step);
    updateSummary();
}

window.goToStep = goToStep;

// ==================== UPDATE SUMMARY ====================
function updateSummary() {
    window.PackageCare?.renderBooking(selectedServices, document.getElementById('appointmentDate')?.value);
    // Services
    const summaryServices = document.getElementById('summaryServices');
    if (summaryServices) {
        if (selectedServices.length === 0) {
            summaryServices.innerHTML = '<p class="empty-text">Chưa chọn dịch vụ</p>';
        } else {
            const selectedServicesData = allServices.filter(s => selectedServices.includes(s.madv));
            const coveredIds = new Set((window.PackageCare?.getUsages() || []).map(u => u.madv));
            summaryServices.innerHTML = selectedServicesData.map(service => `
                <div class="summary-service-item">
                    <span>${service.tendv}</span>
                    ${coveredIds.has(service.madv)
                        ? `<span class="summary-covered"><s>${formatPrice(service.gia)}</s> Dùng buổi gói</span>`
                        : `<span>${formatPrice(service.gia)}</span>`}
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

        if (autoAssign) {
            summaryStaff.innerHTML = '<p class="empty-text">Tự động sắp xếp</p>';
        } else if (!selectedStaff) {
            summaryStaff.innerHTML = '<p class="empty-text">Chưa chọn nhân viên</p>';
        } else {
            const staffName = document.querySelector(`.staff-card.selected h4`)?.textContent || 'Đã chọn';
            summaryStaff.innerHTML = `<p><i class="fas fa-user"></i> ${staffName}</p>`;
        }
    }

    // Total
    const summaryTotal = document.getElementById('summaryTotal');
    if (summaryTotal) {
        const selectedServicesData = allServices.filter(s => selectedServices.includes(s.madv));
        const covered = new Set((window.PackageCare?.getUsages() || []).map(u => u.madv));
        const total = selectedServicesData.reduce((sum, service) => sum + (covered.has(service.madv) ? 0 : parseFloat(service.gia)), 0);
        const formattedTotal = formatPrice(total);
        summaryTotal.textContent = formattedTotal;
        // changeLang()/translateDOM restores data-orig-vi for existing nodes.
        // Keep it in sync so the calculated total is not reset to the initial "0đ".
        summaryTotal.setAttribute('data-orig-vi', formattedTotal);

        // Tóm tắt ngay trên nút xác nhận (mobile: phần tóm tắt bên cạnh nằm dưới form).
        const recap = document.getElementById('confirmRecap');
        if (recap) {
            const usedSessions = selectedServicesData.filter(service => covered.has(service.madv)).length;
            const date = document.getElementById('appointmentDate')?.value;
            const time = document.getElementById('appointmentTime')?.value;
            recap.innerHTML = selectedServicesData.length ? `
                <p><strong>${selectedServicesData.length} dịch vụ</strong>${usedSessions ? ` · dùng ${usedSessions} buổi gói/quà` : ''}${date && time ? ` · ${formatViDate(date)} ${time}` : ''}</p>
                <p>Còn phải trả: <strong>${formattedTotal}</strong></p>` : '';
        }
    }

    if (typeof window.changeLang === 'function') {
        window.changeLang(localStorage.getItem('spa_lang') || 'vi');
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

    if (!autoAssign && !selectedStaff) {
        Toast.warning('Vui lòng chọn một nhân viên hoặc bật tự động sắp xếp!');
        return;
    }

    const datetime = `${date}T${time}`;
    const manv = autoAssign ? null : selectedStaff;

    if (manv) {
        try {
            // === SỬA LỖI 2: Sửa URL check lịch rảnh ===
            const checkResponse = await customerAuthFetch('/api/appointments/check-availability', {
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
        const response = await customerAuthFetch('/api/appointments/create', {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({
                madv_list: selectedServices,
                package_usages: window.PackageCare?.getUsages() || [],
                ngaygio: datetime,
                manv: manv,
                ghichu: ''
            })
        });

        const data = await response.json();

        if (response.status === 401 || response.status === 422) {
            Toast.warning('Phiên đăng nhập đã hết hạn. Đang chuyển đến trang đăng nhập...');
            setTimeout(() => {
                window.CustomerAuth.redirectToLogin(
                    'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
                    `${window.location.pathname}${window.location.search}`
                );
            }, 1200);
            return;
        }

        if (data.success) {
            Toast.success('Đặt lịch hẹn thành công! Chúng tôi đã gửi email xác nhận đến bạn.', 'Thành công!', 5000);

            setTimeout(() => {
                window.location.href = '/profile#appointments';
            }, 2000);
        } else {
            Toast.error(data.message || data.msg || 'Đặt lịch thất bại!');
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
window.refreshBookingSummary = updateSummary;
window.selectStaff = selectStaff;
window.goToStep = goToStep;
window.filterServicesInForm = filterServicesInForm;
window.changePage = changePage;
window.showAllServices = showAllServices;
window.loadAvailableStaff = loadAvailableStaff; // <-- SỬA LỖI 4: Thêm dòng này
window.loadTimeSlots = loadTimeSlots;

})();
