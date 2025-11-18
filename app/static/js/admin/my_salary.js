// ====== BIẾN GLOBAL ======
let mySalaries = [];
let currentMonthSalary = null;

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    loadMySalaries();
});

// ====== TẢI LỊCH SỬ LƯƠNG CỦA TÔI ======
async function loadMySalaries() {
    try {
        showLoading(true);
        
        const response = await fetch('/api/profile/my-salary', {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (data.success) {
            mySalaries = data.salaries || [];
            renderSalariesTable();
            updateCurrentMonthSalary();
        } else {
            showError(data.message || 'Không thể tải lịch sử lương');
        }
    } catch (error) {
        console.error('Lỗi tải lương:', error);
        showError('Không thể tải lịch sử lương');
    } finally {
        showLoading(false);
    }
}

// ====== CẬP NHẬT LƯƠNG THÁNG HIỆN TẠI ======
function updateCurrentMonthSalary() {
    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const currentYear = now.getFullYear();
    
    currentMonthSalary = mySalaries.find(s => 
        s.thang === currentMonth && s.nam === currentYear
    );
    
    // Cập nhật stat card
    const statNumber = document.querySelector('.stat-number');
    if (statNumber) {
        if (currentMonthSalary) {
            statNumber.textContent = formatCurrency(currentMonthSalary.tongluong);
        } else {
            statNumber.textContent = 'Chưa có dữ liệu';
        }
    }
}

// ====== RENDER BẢNG LƯƠNG ======
function renderSalariesTable() {
    const tbody = document.querySelector('#salary-table tbody');
    
    if (mySalaries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">Chưa có lịch sử lương</td></tr>';
        return;
    }
    
    tbody.innerHTML = mySalaries.map(salary => `
        <tr>
            <td>${salary.thang}/${salary.nam}</td>
            <td>${formatCurrency(salary.luongcoban)}</td>
            <td>${formatCurrency(salary.thuong || 0)}</td>
            <td>${formatCurrency(salary.khautru || 0)}</td>
            <td><strong>${formatCurrency(salary.tongluong)}</strong></td>
        </tr>
    `).join('');
}

// ====== HELPER FUNCTIONS ======
function formatCurrency(amount) {
    if (!amount) return '0₫';
    return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND'
    }).format(parseFloat(amount));
}

function showLoading(show) {
    const tbody = document.querySelector('#salary-table tbody');
    if (show) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center"><i class="fas fa-spinner fa-spin"></i> Đang tải...</td></tr>';
    }
}

function showSuccess(message) {
    alert('✅ ' + message);
}

function showError(message) {
    alert('❌ ' + message);
}