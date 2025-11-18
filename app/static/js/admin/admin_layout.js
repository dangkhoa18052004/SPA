// ====== ADMIN LAYOUT - BIN SPA ======
// Quản lý sidebar, authentication và layout chung

// ====== CONSTANTS ======
const AUTH_TOKEN_KEY = 'admin_token';
const AUTH_ROLE_KEY = 'admin_role';
const AUTH_USER_KEY = 'admin_user';
const LOGIN_PATH = '/admin/login';

// ====== AUTHENTICATION FUNCTIONS ======

/**
 * Lấy token xác thực từ localStorage
 * @returns {string|null} Token hoặc null nếu không có
 */
function getAdminAuthToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
}

/**
 * Tạo headers cho API request
 * @param {boolean} includeContentType - Có thêm Content-Type header không
 * @returns {Object|null} Headers object hoặc null nếu không có token
 */
function getAuthHeaders(includeContentType = true) {
    const token = getAdminAuthToken();
    
    if (!token) {
        console.warn('⚠️ No auth token found, redirecting to login...');
        logout();
        return null;
    }
    
    const headers = {
        'Authorization': `Bearer ${token}`
    };

    if (includeContentType) {
        headers['Content-Type'] = 'application/json';
        headers['Accept'] = 'application/json';
    }
    
    return headers;
}

/**
 * Kiểm tra token có hợp lệ không (không expired)
 * @returns {boolean} True nếu token hợp lệ
 */
function isTokenValid() {
    const token = getAdminAuthToken();
    if (!token) return false;
    
    try {
        // Parse JWT token (phần payload)
        const payload = JSON.parse(atob(token.split('.')[1]));
        const exp = payload.exp * 1000; // Convert to milliseconds
        
        // Kiểm tra expiration
        if (Date.now() >= exp) {
            console.warn('⚠️ Token expired');
            return false;
        }
        
        return true;
    } catch (error) {
        console.error('❌ Error parsing token:', error);
        return false;
    }
}

/**
 * Đăng xuất và redirect về trang login
 */
function logout() {
    console.log('🚪 Logging out...');
    
    // Clear all auth data
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_ROLE_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    
    // Redirect to login if not already there
    if (!window.location.pathname.includes(LOGIN_PATH)) {
        window.location.href = LOGIN_PATH;
    }
}

/**
 * Kiểm tra user có role được phép không
 * @param {string|string[]} allowedRoles - Role hoặc danh sách roles
 * @returns {boolean} True nếu có quyền
 */
function hasRole(allowedRoles) {
    const userRole = localStorage.getItem(AUTH_ROLE_KEY);
    
    if (!userRole) return false;
    
    // Convert to array nếu là string
    const rolesArray = Array.isArray(allowedRoles) ? allowedRoles : [allowedRoles];
    
    return rolesArray.includes(userRole);
}

// ====== SIDEBAR MANAGEMENT ======

/**
 * Cấu hình menu items cho từng role
 */
const MENU_CONFIG = {
    admin: [
        { key: 'profile', title: 'Trang cá nhân', href: '/admin/profile', icon: 'fa-user-cog' },
        { key: 'dashboard', title: 'Dashboard', href: '/admin/dashboard', icon: 'fa-tachometer-alt' },
        { key: 'appointments', title: 'Quản lý Lịch hẹn', href: '/admin/appointments', icon: 'fa-calendar-alt' },
        { key: 'invoices', title: 'Quản lý Hóa đơn', href: '/admin/invoices', icon: 'fa-file-invoice-dollar' },
        { key: 'customers', title: 'Quản lý Khách hàng', href: '/admin/customers', icon: 'fa-user-friends' },
        { key: 'staff', title: 'Quản lý Nhân viên', href: '/admin/staff', icon: 'fa-users-cog' },
        { key: 'shifts', title: 'Quản lý Ca làm', href: '/admin/shifts', icon: 'fa-clock' },
        { key: 'approve_shifts', title: 'Duyệt đăng ký ca', href: '/admin/approve-shifts', icon: 'fa-calendar-check' },
        { key: 'salary', title: 'Quản lý Lương', href: '/admin/salary', icon: 'fa-money-bill-wave' },
        { key: 'services', title: 'Quản lý Dịch vụ', href: '/admin/services', icon: 'fa-spa' },
        { key: 'roles', title: 'Quản lý Chức vụ', href: '/admin/roles', icon: 'fa-user-tag' },
        { key: 'chat', title: 'Tin nhắn', href: '/admin/chat', icon: 'fa-comments' }
    ],
    
    manager: [
        { key: 'profile', title: 'Trang cá nhân', href: '/admin/profile', icon: 'fa-user-cog' },
        { key: 'dashboard', title: 'Dashboard', href: '/admin/dashboard', icon: 'fa-tachometer-alt' },
        { key: 'my_salary', title: 'Lương của tôi', href: '/admin/my-salary', icon: 'fa-money-bill-wave' },
        { key: 'appointments', title: 'Quản lý Lịch hẹn', href: '/admin/appointments', icon: 'fa-calendar-alt' },
        { key: 'invoices', title: 'Quản lý Hóa đơn', href: '/admin/invoices', icon: 'fa-file-invoice-dollar' },
        { key: 'customers', title: 'Quản lý Khách hàng', href: '/admin/customers', icon: 'fa-user-friends' },
        { key: 'shifts', title: 'Quản lý Ca làm', href: '/admin/shifts', icon: 'fa-clock' },
        { key: 'approve_shifts', title: 'Duyệt đăng ký ca', href: '/admin/approve-shifts', icon: 'fa-calendar-check' },
        { key: 'chat', title: 'Tin nhắn', href: '/admin/chat', icon: 'fa-comments' }
    ],
    
    letan: [
        { key: 'profile', title: 'Trang cá nhân', href: '/admin/profile', icon: 'fa-user-cog' },
        { key: 'appointments', title: 'Quản lý Lịch hẹn', href: '/admin/appointments', icon: 'fa-calendar-alt' },
        { key: 'invoices', title: 'Quản lý Hóa đơn', href: '/admin/invoices', icon: 'fa-file-invoice-dollar' },
        { key: 'customers', title: 'Quản lý Khách hàng', href: '/admin/customers', icon: 'fa-user-friends' },
        { key: 'my_schedule', title: 'Lịch làm của tôi', href: '/admin/my-schedule', icon: 'fa-calendar-check' },
        { key: 'register_shift', title: 'Đăng ký ca', href: '/admin/register-shift', icon: 'fa-calendar-plus' },
        { key: 'my_salary', title: 'Lương của tôi', href: '/admin/my-salary', icon: 'fa-money-bill-wave' },
        { key: 'chat', title: 'Tin nhắn', href: '/admin/chat', icon: 'fa-comments' }
    ],
    
    staff: [
        { key: 'profile', title: 'Trang cá nhân', href: '/admin/profile', icon: 'fa-user-cog' },
        { key: 'my_schedule', title: 'Lịch làm của tôi', href: '/admin/my-schedule', icon: 'fa-calendar-check' },
        { key: 'register_shift', title: 'Đăng ký ca', href: '/admin/register-shift', icon: 'fa-calendar-plus' },
        { key: 'my_salary', title: 'Lương của tôi', href: '/admin/my-salary', icon: 'fa-money-bill-wave' },
    ]
};

/**
 * Xây dựng sidebar menu theo role
 */
function buildSidebar() {
    const role = localStorage.getItem(AUTH_ROLE_KEY);
    const menu = document.getElementById('sidebar-menu');
    
    if (!role) {
        console.error('❌ No role found');
        logout();
        return;
    }
    
    if (!menu) {
        console.error('❌ Sidebar menu element not found');
        return;
    }
    
    // Lấy menu items cho role
    const menuItems = MENU_CONFIG[role] || [];
    
    if (menuItems.length === 0) {
        console.warn(`⚠️ No menu items defined for role: ${role}`);
        menu.innerHTML = '<li><a href="#"><i class="fas fa-exclamation-triangle"></i> <span>Không có menu</span></a></li>';
        return;
    }
    
    const currentPath = window.location.pathname;
    
    // Build HTML
    const menuHTML = menuItems.map(item => {
        const isActive = currentPath === item.href ? 'active' : '';
        return `
            <li>
                <a href="${item.href}" class="${isActive}">
                    <i class="fas ${item.icon}"></i>
                    <span>${item.title}</span>
                </a>
            </li>
        `;
    }).join('');
    
    menu.innerHTML = menuHTML;
    
    console.log(`✅ Sidebar built for role: ${role} (${menuItems.length} items)`);
}

// ====== USER INFO DISPLAY ======

/**
 * Cập nhật thông tin user trong header
 */
function updateHeaderInfo() {
    try {
        const userStr = localStorage.getItem(AUTH_USER_KEY);
        const role = localStorage.getItem(AUTH_ROLE_KEY);
        
        if (!userStr || !role) {
            console.warn('⚠️ Missing user info or role');
            return;
        }
        
        const user = JSON.parse(userStr);
        
        // Update username
        const usernameEl = document.getElementById('admin-username');
        if (usernameEl) {
            usernameEl.textContent = user.hoten || user.taikhoan || 'User';
        }
        
        // Update role
        const roleEl = document.getElementById('admin-role');
        if (roleEl) {
            const roleLabels = {
                'admin': 'Quản trị viên',
                'manager': 'Quản lý',
                'letan': 'Lễ tân',
                'staff': 'Nhân viên'
            };
            roleEl.textContent = roleLabels[role] || role;
        }
        
        console.log('✅ Header info updated:', user.hoten, role);
        
    } catch (error) {
        console.error('❌ Error updating header info:', error);
    }
}

// ====== PAGE INITIALIZATION ======

/**
 * Khởi tạo layout khi trang load
 */
function initializeLayout() {
    const currentPath = window.location.pathname;
    
    console.log('📍 Current path:', currentPath);
    
    // Bỏ qua kiểm tra nếu đang ở trang login
    if (currentPath.includes(LOGIN_PATH)) {
        console.log('✅ On login page, skipping auth check');
        return;
    }
    
    // Kiểm tra authentication
    const token = getAdminAuthToken();
    const role = localStorage.getItem(AUTH_ROLE_KEY);
    const user = localStorage.getItem(AUTH_USER_KEY);
    
    console.log('🔐 Auth check:', {
        token: token ? '✅ Found' : '❌ Not found',
        role: role || '❌ Not found',
        user: user ? '✅ Found' : '❌ Not found'
    });
    
    // Redirect nếu thiếu thông tin auth
    if (!token || !role) {
        console.log('❌ Missing auth data, redirecting to login...');
        logout();
        return;
    }
    
    // Kiểm tra token có hợp lệ không
    if (!isTokenValid()) {
        console.log('❌ Invalid or expired token, redirecting to login...');
        logout();
        return;
    }
    
    console.log('✅ Auth valid, building UI...');
    
    // Build UI
    buildSidebar();
    updateHeaderInfo();
    
    // Setup auto-refresh token (optional)
    setupTokenRefresh();
}

/**
 * Setup auto-refresh token trước khi hết hạn
 */
function setupTokenRefresh() {
    // Refresh token mỗi 25 phút (nếu token hết hạn sau 30 phút)
    const REFRESH_INTERVAL = 25 * 60 * 1000; // 25 minutes
    
    setInterval(async () => {
        if (!isTokenValid()) {
            console.warn('⚠️ Token expired during session');
            logout();
            return;
        }
        
        // Call API để refresh token (nếu backend hỗ trợ)
        // await refreshAuthToken();
        
    }, REFRESH_INTERVAL);
}

// ====== EVENT LISTENERS ======

/**
 * Setup các event listeners
 */
function setupEventListeners() {
    // Logout button
    const logoutBtns = document.querySelectorAll('.logout-btn, [data-action="logout"]');
    logoutBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (confirm('Bạn có chắc muốn đăng xuất?')) {
                logout();
            }
        });
    });
    
    // Handle unauthorized API responses globally
    window.addEventListener('unhandledrejection', (event) => {
        if (event.reason && event.reason.status === 401) {
            console.warn('⚠️ Received 401 Unauthorized, logging out...');
            logout();
        }
    });
}

// ====== UTILITY FUNCTIONS ======

/**
 * Format role name thành tiếng Việt
 * @param {string} role - Role key
 * @returns {string} Tên role tiếng Việt
 */
function formatRoleName(role) {
    const roleNames = {
        'admin': 'Quản trị viên',
        'manager': 'Quản lý',
        'letan': 'Lễ tân',
        'staff': 'Nhân viên'
    };
    return roleNames[role] || role;
}

/**
 * Kiểm tra user có quyền truy cập trang hiện tại không
 * @returns {boolean} True nếu có quyền
 */
function checkPageAccess() {
    const currentPath = window.location.pathname;
    const role = localStorage.getItem(AUTH_ROLE_KEY);
    
    // Define restricted pages
    const restrictions = {
        '/admin/staff': ['admin', 'manager'],
        '/admin/salary': ['admin', 'manager'],
        '/admin/roles': ['admin'],
        '/admin/approve-shifts': ['admin', 'manager']
    };
    
    for (const [path, allowedRoles] of Object.entries(restrictions)) {
        if (currentPath.includes(path)) {
            if (!allowedRoles.includes(role)) {
                console.warn(`⚠️ Access denied to ${path} for role ${role}`);
                return false;
            }
        }
    }
    
    return true;
}

// ====== DOM READY ======

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Admin layout initializing...');
    
    // Small delay để đảm bảo DOM đã sẵn sàng
    setTimeout(() => {
        initializeLayout();
        setupEventListeners();
        
        // Check page access
        if (!checkPageAccess()) {
            alert('Bạn không có quyền truy cập trang này!');
            window.location.href = '/admin/dashboard';
        }
        
        console.log('✅ Admin layout initialized successfully');
    }, 100);
});

// ====== EXPORT (nếu cần) ======
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAuthHeaders,
        hasRole,
        logout,
        isTokenValid
    };
}