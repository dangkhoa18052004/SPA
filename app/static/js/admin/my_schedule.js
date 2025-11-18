let mySchedule = [];

let currentWeekStart = null;



document.addEventListener('DOMContentLoaded', function() {

    const today = new Date();

    currentWeekStart = getMonday(today);

   

    loadMySchedule();

    setupNavigation();

});



function setupNavigation() {

    const prevBtn = document.getElementById('prev-week');

    const nextBtn = document.getElementById('next-week');

   

    if (prevBtn) {

        prevBtn.addEventListener('click', () => {

            currentWeekStart.setDate(currentWeekStart.getDate() - 7);

            loadMySchedule();

        });

    }

   

    if (nextBtn) {

        nextBtn.addEventListener('click', () => {

            currentWeekStart.setDate(currentWeekStart.getDate() + 7);

            loadMySchedule();

        });

    }

}



async function loadMySchedule() {

    try {

        showScheduleLoading(true);

        updateWeekLabel();

       

        const weekEnd = new Date(currentWeekStart);

        weekEnd.setDate(weekEnd.getDate() + 6);

       

        const startDate = formatDateForAPI(currentWeekStart);

        const endDate = formatDateForAPI(weekEnd);



        const response = await fetch(`/api/admin/my-schedule-list?start_date=${startDate}&end_date=${endDate}`, {

            headers: getAuthHeaders(false)

        });

       

        const data = await response.json();

       

        if (data.success) {

            mySchedule = data.schedule || [];

            renderScheduleTable(mySchedule);

        } else {

            showScheduleError(data.message || 'Không thể tải lịch làm');

        }

    } catch (error) {

        console.error('Lỗi tải lịch làm:', error);

        showScheduleError('Không thể tải lịch làm');

    } finally {

        showScheduleLoading(false);

    }

}



function renderScheduleTable(scheduleList) {

    const tbody = document.querySelector('#my-schedule-table tbody');

   

    if (scheduleList.length === 0) {

        tbody.innerHTML = '<tr><td colspan="6" class="text-center">Bạn không có lịch làm trong tuần này</td></tr>';

        return;

    }

   

    tbody.innerHTML = scheduleList.map(item => {

        let statusClass = '';

        if (item.trangthai_code === 'approved') {

            statusClass = 'badge-success';

        } else if (item.trangthai_code === 'pending') {

            statusClass = 'badge-warning';

        } else {

            statusClass = 'badge-danger';

        }



        return `

            <tr>

                <td>${formatDateDisplay(item.ngay)}</td>

                <td class='d-none'>${item.ten_ca}</td>

                <td>${item.giobatdau}</td>

                <td>${item.gioketthuc}</td>

                <td><span class="badge ${statusClass}">${item.trangthai_text}</span></td>

                <td>

                    <button class="btn btn-info btn-sm" onclick="showColleagueModal('${item.ten_ca}')" title="Xem đồng nghiệp">

                        <i class="fas fa-users"></i> Xem

                    </button>

                </td>

            </tr>

        `;

    }).join('');

}



function showColleagueModal(ten_ca) {

    const shift = mySchedule.find(item => item.ten_ca === ten_ca);

    if (!shift) return;

    const colleagues = shift.colleagues || [];

    let colleagueListHtml = '';

    if (colleagues.length === 0) {

        colleagueListHtml = '<li>Không có đồng nghiệp nào khác trong ca này.</li>';

    } else {

        colleagueListHtml = colleagues.map(nv =>

            `<li><i class="fas fa-user-circle"></i> ${nv.hoten} (${nv.chucvu})</li>`

        ).join('');

    }

    const modalHtml = `

        <div id="colleagueModal" class="modal" style="display: flex;">

            <div class="modal-content" style="max-width: 450px;">

                <div class="modal-header">

                    <h3>Đồng nghiệp ${shift.ten_ca}</h3>

                    <span class="close" onclick="closeColleagueModal()">&times;</span>

                </div>

                <div class="modal-body">

                    <p>Những nhân viên sau cũng làm ${shift.trangthai_code === 'pending' ? 'trong ca bạn đăng ký' : 'cùng ca với bạn'}:</p>

                    <ul class="staff-list-detail" style="list-style-type: none; padding-left: 0;">

                        ${colleagueListHtml}

                    </ul>

                </div>

                <div class="form-actions">

                    <button type="button" class="btn btn-secondary" onclick="closeColleagueModal()">Đóng</button>

                </div>

            </div>

        </div>

    `;

    closeColleagueModal();

    document.body.insertAdjacentHTML('beforeend', modalHtml);

}

function closeColleagueModal() {

    const modal = document.getElementById('colleagueModal');

    if (modal) {

        modal.remove();

    }

}





function getMonday(date) {

    const d = new Date(date);

    const day = d.getDay();

    const diff = d.getDate() - day + (day === 0 ? -6 : 1);

    return new Date(d.setDate(diff));

}



function formatDateForAPI(date) {

    return date.toISOString().split('T')[0];

}



function updateWeekLabel() {

    const label = document.getElementById('current-week');

    if (!label) return;

   

    const weekEnd = new Date(currentWeekStart);

    weekEnd.setDate(weekEnd.getDate() + 6);

   

    label.textContent = `${formatDateForAPI(currentWeekStart)} - ${formatDateForAPI(weekEnd)}`;

}



function formatDateDisplay(dateStr) {

    const date = new Date(dateStr);

    date.setDate(date.getDate() + 1);

    return date.toLocaleDateString('vi-VN', {

        weekday: 'long',

        month: '2-digit',

        day: '2-digit',

        year: 'numeric'

    });

}

function showScheduleLoading(show) {

    const tbody = document.querySelector('#my-schedule-table tbody');

    if (show) {

        tbody.innerHTML = '<tr><td colspan="6" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';

    }

}

function showScheduleError(message) {

    const tbody = document.querySelector('#my-schedule-table tbody');

    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${message}</td></tr>`;

}

function getAuthHeaders(includeContentType = true) {

    const token = localStorage.getItem('admin_token');

    if (!token) {

        window.location.href = '/admin/login';

        return null;

    }

    const headers = { 'Authorization': `Bearer ${token}` };

    if (includeContentType) {

        headers['Content-Type'] = 'application/json';

        headers['Accept'] = 'application/json';

    }

    return headers;

}