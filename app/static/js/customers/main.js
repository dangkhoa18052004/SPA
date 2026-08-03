// ==================== TOAST NOTIFICATION SYSTEM ====================
const Toast = {
    container: null,
    
    // Initialize toast container
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    
    // Show toast notification
    show(type, title, message, duration = 4000) {
        this.init();
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        // Icon based on type
        const icons = {
            success: '<i class="fas fa-check"></i>',
            error: '<i class="fas fa-times"></i>',
            warning: '<i class="fas fa-exclamation"></i>',
            info: '<i class="fas fa-info"></i>'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${this.escapeHtml(title)}</div>` : ''}
                <div class="toast-message">${this.escapeHtml(message)}</div>
            </div>
            <button class="toast-close" onclick="Toast.remove(this.parentElement)">
                <i class="fas fa-times"></i>
            </button>
            ${duration > 0 ? `<div class="toast-progress" style="animation-duration: ${duration}ms;"></div>` : ''}
        `;
        
        // Add to container
        this.container.appendChild(toast);
        
        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(toast);
            }, duration);
        }
        
        return toast;
    },
    
    // Remove toast
    remove(toast) {
        if (!toast || !toast.parentElement) return;
        
        toast.classList.add('removing');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    },
    
    // Helper to escape HTML
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    // Shortcut methods
    success(message, title = 'Thành công!', duration = 4000) {
        return this.show('success', title, message, duration);
    },
    
    error(message, title = 'Lỗi!', duration = 5000) {
        return this.show('error', title, message, duration);
    },
    
    warning(message, title = 'Cảnh báo!', duration = 4500) {
        return this.show('warning', title, message, duration);
    },
    
    info(message, title = 'Thông tin', duration = 4000) {
        return this.show('info', title, message, duration);
    },
    
    // Clear all toasts
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
};

// ==================== USAGE EXAMPLES ====================
/*
// Success toast
Toast.success('Đặt lịch hẹn thành công!');

// Error toast
Toast.error('Vui lòng chọn ít nhất một dịch vụ!');

// Warning toast
Toast.warning('Token sắp hết hạn, vui lòng đăng nhập lại!');

// Info toast
Toast.info('Đang tải dữ liệu...');

// Custom duration (in milliseconds)
Toast.success('Đã lưu!', 'Thành công!', 2000);

// No auto-dismiss (duration = 0)
Toast.error('Lỗi nghiêm trọng!', 'Lỗi!', 0);

// With custom title
Toast.success('Thông tin đã được cập nhật', 'Cập nhật thành công!');
*/
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
let currentLang = 'vi';
let currentConversationId = null;
let unreadCount = 0; // Số tin nhắn chưa đọc
let chatRefreshInterval = null; // Interval để refresh tin nhắn

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', function() {
    initTheme(); // Khởi tạo chế độ Night Spa Dark Mode nếu được lưu
    initLang(); // Khởi tạo ngôn ngữ đã lưu (VI/EN)
    initNavbar();
    initDropdowns();
    loadServices();
    loadServicePicker();
    initSmoothScroll();
    checkLoginStatus(); // Kiểm tra đăng nhập và load unread count
    setupChatRefresh(); // Setup auto-refresh cho chat
    setupChatInput(); // Setup input handler
    initSpaMusic(); // Khởi tạo âm thanh Spa thư giãn duy trì giữa các trang
});


// ==================== NAVBAR ====================
function initNavbar() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;
    
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// ==================== DROPDOWNS ====================
function initDropdowns() {
    const langBtn = document.getElementById('langBtn');
    const langDropdown = document.getElementById('langDropdown');
    
    if (langBtn && langDropdown) {
        langBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            langDropdown.classList.toggle('show');
            const userDropdown = document.getElementById('userDropdown');
            if (userDropdown) userDropdown.classList.remove('show');
        });
    }
    
    const userBtn = document.getElementById('userBtn');
    const userDropdown = document.getElementById('userDropdown');
    
    if (userBtn && userDropdown) {
        userBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdown.classList.toggle('show');
            if (langDropdown) langDropdown.classList.remove('show');
        });
    }
    
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const navMenu = document.getElementById('navMenu');
    
    if (mobileMenuBtn && navMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            navMenu.classList.toggle('show');
        });
    }
    
    document.addEventListener('click', function() {
        if (langDropdown) langDropdown.classList.remove('show');
        if (userDropdown) userDropdown.classList.remove('show');
    });
}

// ==================== LANGUAGE (i18n) ====================
const i18nDict = {
    // Navigation & Common
    'Trang chủ': 'Home',
    'Dịch vụ': 'Services',
    'Về Bin Spa': 'About Bin Spa',
    'Địa chỉ': 'Address',
    'Địa chỉ & Liên hệ': 'Address & Contact',
    'Thông tin cá nhân': 'Profile',
    'Chỉnh sửa thông tin': 'Edit Profile',
    'Đổi mật khẩu': 'Change Password',
    'Lịch hẹn của tôi': 'My Appointments',
    'Hóa đơn của tôi': 'My Invoices',
    'Đăng xuất': 'Logout',
    'Đăng nhập': 'Login',
    'Đăng ký': 'Register',

    // Buttons & CTAs
    'Đặt lịch ngay': 'Book Now',
    'XEM DỊCH VỤ': 'VIEW SERVICES',
    'ĐẶT LỊCH NGAY': 'BOOK NOW',
    'ĐẶT LỊCH HẸN NGAY': 'BOOK APPOINTMENT NOW',
    'LIÊN HỆ VỚI SPA': 'CONTACT SPA',
    'XEM TOÀN BỘ DỊCH VỤ': 'VIEW ALL SERVICES',
    'Liên hệ': 'Contact Us',
    'Xem nhanh': 'Quick View',
    'Chi tiết': 'Details',
    'Tất cả': 'All',
    'Lưu thay đổi': 'Save Changes',
    'Hủy': 'Cancel',
    'Tiếp theo': 'Next',
    'Quay lại': 'Back',
    'Xem tất cả dịch vụ': 'View All Services',
    'Đang kết nối...': 'Connecting...',
    'Nhập tin nhắn...': 'Type a message...',
    'Chọn dịch vụ': 'Select Service',

    // Filter Chips & Categories
    'Cổ Vai Gáy': 'Neck & Shoulder',
    'Chăm Sóc Da': 'Skincare',
    'Thư Giãn Stress': 'Stress Relief',
    'Combo Spa VIP': 'VIP Combo Spa',
    'Massage': 'Massage',
    'Nail & Móng': 'Nail Care',
    'Tóc & Đầu': 'Hair & Head',
    'Điều trị cơ thể': 'Body Treatment',

    // Service Titles
    'Massage body thư giãn': 'Relaxing Body Massage',
    'Spa chân': 'Foot Spa',
    'Làm nail': 'Nail Care',
    'Gội đầu dưỡng sinh': 'Herbal Hair Wash',
    'Chăm sóc da mặt': 'Facial Skincare',
    'Tắm trắng thảo dược': 'Herbal Body Bath',
    'Chăm sóc cơ thể': 'Body Care',

    // Profile & Form Labels
    'Họ và tên': 'Full Name',
    'Email': 'Email',
    'Số điện thoại': 'Phone Number',
    'Địa chỉ': 'Address',
    'Chưa cập nhật': 'Not updated',
    'Chưa phân công': 'Not assigned',
    'Mật khẩu cũ': 'Current Password',
    'Mật khẩu mới': 'New Password',
    'Xác nhận mật khẩu mới': 'Confirm New Password',
    'Đang tải...': 'Loading...',
    'Chờ xác nhận': 'Pending Confirmation',
    'Đã xác nhận': 'Confirmed',
    'Hoàn thành': 'Completed',
    'Đã hủy': 'Cancelled',
    'Hủy lịch': 'Cancel Booking',
    'Bạn chưa có lịch hẹn nào': 'You have no appointments',
    'Bạn chưa có hóa đơn nào': 'You have no invoices',
    'Tạo mới': 'Create New',

    // Quick View Modal & Features
    'Dịch Vụ Cao Cấp Bin Spa': 'Bin Spa Premium Service',
    'DỊCH VỤ CAO CẤP BIN SPA': 'BIN SPA PREMIUM SERVICE',
    'Kỹ thuật viên lành nghề': 'Expert Therapists',
    '100% thảo dược thiên nhiên': '100% Natural Herbs',
    'Trà thảo mộc đón tiếp miễn phí': 'Free Herbal Tea',
    'Trải nghiệm liệu trình thư giãn và chăm sóc sức khỏe toàn diện với công nghệ tự nhiên tại Bin Spa & Wellness.': 'Experience comprehensive relaxation and healthcare treatments with natural technology at Bin Spa & Wellness.',
    'Trải nghiệm dịch vụ chăm sóc sức khỏe và sắc đẹp cao cấp tại Sà Spa. Đội ngũ kỹ thuật viên chuyên nghiệp với nhiều năm kinh nghiệm sẽ mang đến cho bạn những phút giây thư giãn tuyệt vời nhất.': 'Experience luxury health and beauty services at Bin Spa. Professional therapist team with years of experience.',

    // Headings & Text
    'Dịch vụ của chúng tôi': 'Our Services',
    'Trải nghiệm các dịch vụ chăm sóc sắc đẹp và sức khỏe cao cấp': 'Experience our luxury health and beauty services',
    'Tại sao chọn Bin Spa?': 'Why Choose Bin Spa?',
    'Khách hàng nói về Bin Spa': 'What Customers Say',
    'Các dịch vụ liên quan': 'Related Services',
    'Lợi ích dịch vụ': 'Service Benefits',
    'Lưu ý': 'Notice',
    'phút': 'mins',
    'Vui lòng đặt lịch trước để đảm bảo có chỗ. Quý khách nên đến trước 10 phút để làm thủ tục và chuẩn bị.': 'Please book in advance to secure your spot. We recommend arriving 10 minutes early.',
    'Chưa chọn dịch vụ nào': 'No service selected',
    'Vui lòng điền đầy đủ thông tin để hoàn tất đặt lịch': 'Please fill in details to complete booking',
    '1. Dịch vụ': '1. Services',
    '2. Khung giờ': '2. Time Slot',
    '3. Chuyên viên': '3. Therapist',
    'Thông tin đặt lịch': 'Booking Information',
    'Dịch vụ đã chọn': 'Selected Services',
    'Thời gian': 'Time & Date',
    'Nhân viên': 'Therapist',
    'Tự động sắp xếp': 'Auto Assigned',
    'Chưa chọn thời gian': 'Time not selected',
    'Tổng cộng:': 'Total:',
    '100% Thảo dược tự nhiên': '100% Natural Herbs',
    'Kỹ thuật viên lành nghề': 'Expert Therapists',
    'Trà thảo mộc đón tiếp miễn phí': 'Free Herbal Tea',
    '4.9/5 (1,200+ Đánh giá)': '4.9/5 (1,200+ Reviews)',
    '+5,000 Khách hài lòng': '+5,000 Happy Clients',
    'Đến Bin, tìm về một nhịp nghỉ vừa vặn': 'Come to Bin, find your perfect rhythm',
    'Tìm kiếm dịch vụ...': 'Search services...',
    'Tìm dịch vụ...': 'Search services...',
    'Sắp xếp mặc định': 'Default Sorting',
    'Giá: Thấp đến Cao': 'Price: Low to High',
    'Giá: Cao đến Thấp': 'Price: High to Low',
    'Tên: A-Z': 'Name: A-Z',
    'Tên: Z-A': 'Name: Z-A'
};

function initLang() {
    const savedLang = localStorage.getItem('spa_lang') || 'vi';
    changeLang(savedLang);
}

function changeLang(lang) {
    currentLang = lang;
    localStorage.setItem('spa_lang', lang);
    
    const currentLangEl = document.getElementById('currentLang');
    if (currentLangEl) {
        currentLangEl.textContent = lang.toUpperCase();
    }

    // Update data-lang-en elements
    const elements = document.querySelectorAll('[data-lang-' + lang + ']');
    elements.forEach(el => {
        const text = el.getAttribute('data-lang-' + lang);
        if (el.tagName === 'INPUT') {
            el.placeholder = el.getAttribute('data-lang-' + lang + '-placeholder') || text;
        } else {
            el.textContent = text;
        }
    });

    // Translate DOM text nodes & buttons
    translateDOM(lang);

    const langDropdown = document.getElementById('langDropdown');
    if (langDropdown) langDropdown.classList.remove('show');
}

function translateDOM(lang) {
    const selector = 'h1, h2, h3, h4, h5, p, span, a, button, label, option, .info-label, .service-category-badge, .service-badge-detail, .service-name, .service-description, .quick-view-tag, .quick-view-title, .quick-view-desc';
    document.querySelectorAll(selector).forEach(el => {
        const nonIconChildren = Array.from(el.children).filter(child => child.tagName !== 'I');
        if (nonIconChildren.length > 0) return;
        
        let text = el.getAttribute('data-orig-vi');
        if (!text) {
            text = el.textContent.trim();
            if (text) el.setAttribute('data-orig-vi', text);
        }

        if (lang === 'en') {
            if (i18nDict[text]) {
                if (el.querySelector('i')) {
                    const icon = el.querySelector('i').outerHTML;
                    el.innerHTML = icon + ' ' + i18nDict[text];
                } else {
                    el.textContent = i18nDict[text];
                }
            } else if (text.startsWith('Dịch vụ Massage body')) {
                el.textContent = 'Relaxing body massage session helps relieve stress, fatigue and brings deep relaxation to your entire body.';
            } else if (text.startsWith('Dịch vụ Spa chân')) {
                el.textContent = 'Foot spa experience with herbal soaking, exfoliation and soothing essential oil massage.';
            } else if (text.startsWith('Dịch vụ Làm nail')) {
                el.textContent = 'Professional nail care including trimming, cuticle care, gel polish and artistic nail designs.';
            } else if (text.startsWith('Dịch vụ chăm sóc cơ thể')) {
                el.textContent = 'Body care treatment providing deep relaxation, skin softening, detoxing and energy renewal.';
            } else if (text.includes('Dịch vụ chất lượng cao')) {
                el.textContent = 'High quality spa treatment service at Bin Spa.';
            } else if (text.endsWith('phút')) {
                const num = text.replace(/[^0-9]/g, '');
                if (num) {
                    if (el.querySelector('i')) {
                        const icon = el.querySelector('i').outerHTML;
                        el.innerHTML = icon + ' ' + num + ' mins';
                    } else {
                        el.textContent = num + ' mins';
                    }
                }
            }
        } else {
            if (text) {
                if (el.querySelector('i')) {
                    const icon = el.querySelector('i').outerHTML;
                    el.innerHTML = icon + ' ' + text;
                } else {
                    el.textContent = text;
                }
            }
        }
    });

    // Translate Placeholders
    document.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(input => {
        let ph = input.getAttribute('data-orig-ph');
        if (!ph) {
            ph = input.placeholder;
            if (ph) input.setAttribute('data-orig-ph', ph);
        }
        if (lang === 'en' && i18nDict[ph]) {
            input.placeholder = i18nDict[ph];
        } else if (ph) {
            input.placeholder = ph;
        }
    });
}

// ==================== SERVICES ====================
async function loadServices() {
    try {
        const response = await fetch('/api/services', {
            headers: getAuthHeaders(false)
        });
        const data = await response.json();
        
        if (data.success && data.services) {
            allServices = data.services;
            displayServices(allServices.slice(0, 6));
        }
    } catch (error) {
        console.error('Error loading services:', error);
    }
}

function displayServices(services) {
    const servicesGrid = document.getElementById('servicesGrid');
    if (!servicesGrid) return;
    
    servicesGrid.innerHTML = services.map(service => {
        return `
            <div class="service-card" data-service-id="${service.madv}" onclick="viewServiceDetail(${service.madv})">
                <div class="service-image-container">
                    <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                         alt="${service.tendv}" 
                         class="service-image"
                         onerror="this.src='/static/images/default-service.jpg'">
                </div>
                <div class="service-content">
                    <h3 class="service-name">${service.tendv}</h3>
                    <p class="service-description">${service.mota || 'Dịch vụ chất lượng cao tại Bin Spa'}</p>
                    
                    <div class="service-meta">
                        <div class="service-price">${formatPrice(service.gia)}</div>
                        ${service.thoiluong ? `
                            <div class="service-duration">
                                <i class="fas fa-clock"></i>
                                <span>${service.thoiluong} phút</span>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div class="service-actions">
                        <a href="/appointments/create?service=${service.madv}" class="btn btn-primary" onclick="event.stopPropagation()">
                            <i class="fas fa-calendar-check"></i> Đặt lịch
                        </a>
                        <button class="btn btn-outline" onclick="event.stopPropagation(); openQuickView(${service.madv})">
                            <i class="fas fa-eye"></i> Xem nhanh
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    if (typeof currentLang !== 'undefined' && currentLang === 'en') {
        translateDOM('en');
    }
}

function viewServiceDetail(serviceId) {
    window.location.href = `/services/${serviceId}`;
}

// ==================== QUICK VIEW MODAL ====================
function openQuickView(serviceId) {
    let service = allServices.find(s => s.madv === serviceId);
    if (!service && pickerServicesMap[serviceId]) {
        service = pickerServicesMap[serviceId];
    }
    if (!service) return;

    const modal = document.getElementById('quickViewModal');
    const body = document.getElementById('quickViewBody');
    if (!modal || !body) return;

    const imgSrc = service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg';
    
    body.innerHTML = `
        <div class="quick-view-grid">
            <div class="quick-view-img-box">
                <img src="${imgSrc}" alt="${escapeHtml(service.tendv)}" onerror="this.src='/static/images/default-service.jpg'">
            </div>
            <div class="quick-view-info">
                <span class="quick-view-tag"><i class="fas fa-spa"></i> Dịch Vụ Cao Cấp Bin Spa</span>
                <h2 class="quick-view-title">${escapeHtml(service.tendv)}</h2>
                <div class="quick-view-meta">
                    <span class="quick-view-price">${formatPrice(service.gia)}</span>
                    <span class="quick-view-duration"><i class="far fa-clock"></i> ${service.thoiluong || 60} phút</span>
                </div>
                <p class="quick-view-desc">${escapeHtml(service.mota || 'Trải nghiệm liệu trình thư giãn và chăm sóc sức khỏe toàn diện với công nghệ tự nhiên tại Bin Spa & Wellness.')}</p>
                <div class="quick-view-features">
                    <div><i class="fas fa-check-circle"></i> Kỹ thuật viên lành nghề</div>
                    <div><i class="fas fa-check-circle"></i> 100% thảo dược thiên nhiên</div>
                    <div><i class="fas fa-check-circle"></i> Trà thảo mộc đón tiếp miễn phí</div>
                </div>
                <div class="quick-view-cta">
                    <a href="/appointments/create?service=${service.madv}" class="btn btn-primary btn-block">
                        <i class="fas fa-calendar-check"></i> ĐẶT LỊCH HẸN NGAY
                    </a>
                </div>
            </div>
        </div>
    `;
    
    modal.classList.add('show');

    if (typeof currentLang !== 'undefined' && currentLang === 'en') {
        translateDOM('en');
    }
}

function closeQuickView(e) {
    if (e && e.target && e.target.closest('.quick-view-content')) return;
    const modal = document.getElementById('quickViewModal');
    if (modal) modal.classList.remove('show');
}

// ==================== NIGHT SPA DARK MODE ====================
function initTheme() {
    const savedTheme = localStorage.getItem('spa_theme');
    const themeIcon = document.getElementById('themeIcon');
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        if (themeIcon) themeIcon.className = 'fas fa-sun';
    } else {
        document.body.classList.remove('dark-theme');
        if (themeIcon) themeIcon.className = 'fas fa-moon';
    }
}

function toggleTheme() {
    const themeIcon = document.getElementById('themeIcon');
    if (document.body.classList.contains('dark-theme')) {
        document.body.classList.remove('dark-theme');
        localStorage.setItem('spa_theme', 'light');
        if (themeIcon) themeIcon.className = 'fas fa-moon';
        if (window.Toast) Toast.show('info', 'Giao diện', 'Đã chuyển sang chế độ Ban Ngày ☀️');
    } else {
        document.body.classList.add('dark-theme');
        localStorage.setItem('spa_theme', 'dark');
        if (themeIcon) themeIcon.className = 'fas fa-sun';
        if (window.Toast) Toast.show('info', 'Giao diện', 'Đã bật chế độ Đêm Spa thư giãn 🌙');
    }
}

function formatPrice(price) {
    return new Intl.NumberFormat('vi-VN', { 
        style: 'currency', 
        currency: 'VND' 
    }).format(parseFloat(price));
}

// ==================== SMOOTH SCROLL ====================
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

function toggleChat() {
    const chatBox = document.getElementById('chatBox');
    if (!chatBox) return;
    
    chatBox.classList.toggle('show');
    
    if (chatBox.classList.contains('show')) {
        loadOrCreateConversation();
        unreadCount = 0;
        updateUnreadBadge();
    }
}

function openChat() {
    const chatBox = document.getElementById('chatBox');
    if (!chatBox) return;
    
    chatBox.classList.add('show');
    loadOrCreateConversation();
    unreadCount = 0;
    updateUnreadBadge();
}

async function loadOrCreateConversation() {
    try {
        const token = getAuthToken();
        const chatInputArea = document.querySelector('.chat-input-area');

        if (!token) {
            const chatMessages = document.getElementById('chatMessages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="chat-login-prompt">
                        <i class="fas fa-lock" style="font-size: 36px; color: #D4AF37; margin-bottom: 12px;"></i>
                        <p>Vui lòng đăng nhập để sử dụng tính năng chat</p>
                        <a href="/auth/login" class="btn btn-primary">Đăng nhập</a>
                    </div>
                `;
            }
            if (chatInputArea) {
                chatInputArea.style.display = 'none';
            }
            return;
        }

        if (chatInputArea) {
            chatInputArea.style.display = 'flex';
        }

        // Gọi API để lấy hoặc tạo conversation
        const response = await fetch('/api/chat/conversations', {
            method: 'POST',
            headers: getAuthHeaders(true)
        });
        
        const data = await response.json();
        
        if (data.success && data.conversation) {
            currentConversationId = data.conversation.maht;
            await loadMessages(currentConversationId);
        } else {
            showChatMessage('bot', 'Không thể kết nối. Vui lòng thử lại!');
        }
    } catch (error) {
        console.error('Error loading/creating conversation:', error);
        showChatMessage('bot', 'Có lỗi xảy ra. Vui lòng thử lại!');
    }
}

async function sendQuickReply(text) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = text;
        await sendMessage();
    }
}

async function loadMessages(conversationId) {
    try {
        const response = await fetch(`/api/chat/conversations/${conversationId}/messages`, {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (data.success && data.messages) {
            const chatMessages = document.getElementById('chatMessages');
            if (!chatMessages) return;
            
            chatMessages.innerHTML = data.messages.map(msg => {
                const isCustomer = msg.is_customer || msg.nguoigui_makh !== undefined;
                const messageClass = isCustomer ? 'user-message' : 'bot-message';
                const timeStr = formatMessageTime(msg.thoigiangui || msg.thoigian);
                
                return `
                    <div class="chat-message ${messageClass}">
                        <div class="message-content">
                            <div class="message-text">
                                ${renderMessageHTML(msg.noidung)}
                            </div>
                            <span class="message-time">${timeStr}</span>
                        </div>
                    </div>
                `;
            }).join('');
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

function renderMessageHTML(content) {
    if (!content) return '';
    
    // Kiểm tra tin nhắn Rich Card dạng [SERVICE_CARD:madv|tendv|gia|thoiluong|imgUrl]
    const cardMatch = content.match(/^\[SERVICE_CARD:(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\]\s*([\s\S]*)$/);
    if (cardMatch) {
        const madv = cardMatch[1];
        const tendv = cardMatch[2];
        const gia = cardMatch[3];
        const thoiluong = cardMatch[4];
        const imgUrl = cardMatch[5];
        const textMsg = cardMatch[6];
        return `
            <div class="chat-service-card">
                <img src="${imgUrl}" class="chat-card-img" alt="${escapeHtml(tendv)}" onerror="this.src='/static/images/default-service.jpg'">
                <div class="chat-card-body">
                    <div class="chat-card-title">${escapeHtml(tendv)}</div>
                    <div class="chat-card-meta">
                        <span class="chat-card-price">${formatPrice(gia)}</span>
                        <span class="chat-card-duration"><i class="far fa-clock"></i> ${thoiluong} phút</span>
                    </div>
                    <a href="/appointments/create?service_id=${madv}" class="chat-card-book-btn">
                        <i class="fas fa-calendar-check"></i> Đặt lịch ngay
                    </a>
                </div>
            </div>
            ${textMsg ? `<p>${escapeHtml(textMsg)}</p>` : ''}
        `;
    }

    // Kiểm tra tin nhắn có chứa thẻ ảnh [IMG:url]
    const imgMatch = content.match(/^\[IMG:(.+?)\]\s*([\s\S]*)$/);
    if (imgMatch) {
        const imgUrl = imgMatch[1];
        const textMsg = imgMatch[2];
        return `
            <div class="message-image-wrapper">
                <img src="${imgUrl}" class="chat-message-image" alt="Dịch vụ" onerror="this.parentElement.style.display='none'">
            </div>
            ${textMsg ? `<p>${escapeHtml(textMsg)}</p>` : ''}
        `;
    }
    
    return `<p>${escapeHtml(content)}</p>`;
}

function showTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages || document.getElementById('typingIndicator')) return;
    
    const html = `
        <div class="chat-message bot-message" id="typingIndicator">
            <div class="message-content typing-bubble">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', html);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTypingIndicator() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

function showChatMessage(type, message) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const messageClass = type === 'user' ? 'user-message' : 'bot-message';
    const timeStr = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const messageHtml = `
        <div class="chat-message ${messageClass}">
            <div class="message-content">
                <div class="message-text">
                    ${renderMessageHTML(message)}
                </div>
                <span class="message-time">${timeStr}</span>
            </div>
        </div>
    `;
    
    chatMessages.insertAdjacentHTML('beforeend', messageHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    if (!chatInput) return;
    
    const message = chatInput.value.trim();
    if (!message) return;
    
    if (!currentConversationId) {
        showChatMessage('bot', 'Đang kết nối...');
        await loadOrCreateConversation();
        if (!currentConversationId) return;
    }
    
    // Hiển thị tin nhắn ngay lập tức
    showChatMessage('user', message);
    chatInput.value = '';
    
    try {
        const response = await fetch(`/api/chat/conversations/${currentConversationId}/messages`, {
            method: 'POST',
            headers: getAuthHeaders(true),
            body: JSON.stringify({ noidung: message })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showChatMessage('bot', 'Có lỗi xảy ra. Vui lòng thử lại!');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        showChatMessage('bot', 'Không thể gửi tin nhắn. Vui lòng thử lại!');
    }
}

// ✅ FIX: Cập nhật số tin nhắn chưa đọc
async function updateUnreadCount() {
    try {
        const token = getAuthToken();
        if (!token) {
            unreadCount = 0;
            updateUnreadBadge();
            return;
        }

        const response = await fetch('/api/chat/conversations', {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (data.success && data.conversations) {
            // Tính tổng số tin nhắn chưa đọc từ tất cả conversations
            unreadCount = data.conversations.reduce((total, conv) => {
                return total + (conv.unread_count || 0);
            }, 0);
            
            console.log('Unread count updated:', unreadCount); // Debug log
            updateUnreadBadge();
        }
    } catch (error) {
        console.error('Error updating unread count:', error);
    }
}

function updateUnreadBadge() {
    const chatButton = document.getElementById('chatFloat');
    if (!chatButton) {
        console.warn('❌ Chat button not found!');
        return;
    }
    
    let badge = chatButton.querySelector('.chat-unread-badge');
    
    if (unreadCount > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'chat-unread-badge';
            chatButton.appendChild(badge);
        }
        
        badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        badge.style.display = 'flex';
        badge.style.animation = 'badgeBounceIn 0.5s ease';
        
        console.log('✅ Badge displayed:', unreadCount);
    } else {
        if (badge) {
            badge.style.display = 'none';
        }
        console.log('✅ Badge hidden (no unread)');
    }
}


// ✅ FIX: Setup auto-refresh cho chat và unread count
function setupChatRefresh() {
    // Cập nhật unread count ngay lập tức
    updateUnreadCount();
    
    // Cập nhật unread count mỗi 10 giây
    chatRefreshInterval = setInterval(async () => {
        await updateUnreadCount();
        
        // Nếu chat đang mở và có conversation, refresh tin nhắn
        const chatBox = document.getElementById('chatBox');
        if (chatBox && chatBox.classList.contains('show') && currentConversationId) {
            await loadMessages(currentConversationId);
        }
    }, 10000); // 10 giây
}

// Setup chat input handler
function setupChatInput() {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
}

// Cleanup khi rời trang
window.addEventListener('beforeunload', function() {
    if (chatRefreshInterval) {
        clearInterval(chatRefreshInterval);
    }
});

// ==================== SERVICE PICKER ====================
let pickerServicesMap = {};

function toggleServicePicker() {
    const servicePicker = document.getElementById('servicePicker');
    if (!servicePicker) return;
    
    servicePicker.classList.toggle('show');
}

async function loadServicePicker() {
    try {
        const response = await fetch('/api/services');
        const data = await response.json();
        
        if (data.success && data.services) {
            const servicePickerList = document.getElementById('servicePickerList');
            if (!servicePickerList) return;
            
            pickerServicesMap = {};
            servicePickerList.innerHTML = data.services.map(service => {
                pickerServicesMap[service.madv] = service;
                const imgSrc = service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg';
                const safeName = escapeHtml(service.tendv);
                return `
                    <div class="service-picker-item" onclick="selectService(${service.madv})">
                        <img src="${imgSrc}" 
                             alt="${safeName}" 
                             class="service-picker-image"
                             onerror="this.src='/static/images/default-service.jpg'">
                        <div class="service-picker-info">
                            <div class="service-picker-name">${safeName}</div>
                            <div class="service-picker-price">${formatPrice(service.gia)}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('Error loading service picker:', error);
    }
}

function selectService(serviceId) {
    const service = pickerServicesMap[serviceId];
    const input = document.getElementById('chatInput');
    if (input) {
        if (service) {
            const imgSrc = service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg';
            const duration = service.thoiluong || 60;
            input.value = `[SERVICE_CARD:${service.madv}|${service.tendv}|${service.gia}|${duration}|${imgSrc}] Tôi muốn đặt lịch dịch vụ: ${service.tendv}`;
        } else {
            input.value = `Tôi muốn đặt lịch dịch vụ`;
        }
        toggleServicePicker();
        sendMessage();
    }
}

// ==================== SPA MUSIC PLAYER ====================
function initSpaMusic() {
    const audio = document.getElementById('spaAudio');
    const musicBtn = document.getElementById('musicFloat');
    const musicIcon = document.getElementById('musicIcon');
    if (!audio || !musicBtn) return;

    // Mặc định phát nhạc ngoại trừ khi người dùng chủ động TẮT ('false')
    const musicState = localStorage.getItem('spa_music_enabled');
    const shouldPlay = musicState === null || musicState === 'true';

    if (shouldPlay) {
        audio.volume = 0.35; // Âm lượng 35% vừa phải
        audio.play().then(() => {
            musicBtn.classList.add('playing');
            if (musicIcon) musicIcon.className = 'fas fa-volume-up';
        }).catch(() => {
            // Khi trình duyệt chặn autoplay, tự động phát nhạc ngay khi người dùng chạm/click bất kỳ đâu
            const startOnInteraction = () => {
                if (audio.paused && (localStorage.getItem('spa_music_enabled') !== 'false')) {
                    audio.play().then(() => {
                        musicBtn.classList.add('playing');
                        if (musicIcon) musicIcon.className = 'fas fa-volume-up';
                    }).catch(() => {});
                }
                document.removeEventListener('click', startOnInteraction);
                document.removeEventListener('touchstart', startOnInteraction);
            };
            document.addEventListener('click', startOnInteraction);
            document.addEventListener('touchstart', startOnInteraction);
        });
    } else {
        audio.pause();
        musicBtn.classList.remove('playing');
        if (musicIcon) musicIcon.className = 'fas fa-music';
    }
}

function toggleSpaMusic() {
    const audio = document.getElementById('spaAudio');
    const musicBtn = document.getElementById('musicFloat');
    const musicIcon = document.getElementById('musicIcon');
    if (!audio || !musicBtn) return;
    
    if (audio.paused) {
        audio.volume = 0.35;
        audio.play().then(() => {
            localStorage.setItem('spa_music_enabled', 'true');
            musicBtn.classList.add('playing');
            if (musicIcon) musicIcon.className = 'fas fa-volume-up';
            if (window.Toast) Toast.show('info', 'Âm thanh Spa', 'Đã bật nhạc thiền thư giãn 🌿');
        }).catch(err => {
            console.log('Audio playback error:', err);
        });
    } else {
        audio.pause();
        localStorage.setItem('spa_music_enabled', 'false');
        musicBtn.classList.remove('playing');
        if (musicIcon) musicIcon.className = 'fas fa-music';
        if (window.Toast) Toast.show('info', 'Âm thanh Spa', 'Đã tắt nhạc thư giãn');
    }
}

// ==================== SMART NEED-BASED SERVICE FILTERING ====================
function filterServices(keyword, btn) {
    const buttons = document.querySelectorAll('.smart-filters .filter-chip');
    buttons.forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const serviceItems = document.querySelectorAll('#servicesGrid .service-card, .services-grid .service-card');
    const term = keyword.toLowerCase();
    
    serviceItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (keyword === 'all' || text.includes(term)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// ==================== LOGOUT ====================
async function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: getAuthHeaders(false)
        });
    } catch (error) {
        console.error('Error logging out on server:', error);
    }
    
    window.location.href = '/';
}

// ==================== CHECK LOGIN STATUS ====================
async function checkLoginStatus() {
    try {
        const token = getAuthToken();
        
        if (!token) {
            console.log('Chưa đăng nhập');
            return; 
        }

        const response = await fetch('/api/profile', {
            headers: getAuthHeaders(false)
        });
        
        if (!response.ok) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_info');
            console.log('Token không hợp lệ');
            return;
        }
        
        const data = await response.json();
        
        if (data.success && data.user) {
            // Cập nhật UI khi đã đăng nhập
            const userBtn = document.getElementById('userBtn');
            const userDropdown = document.getElementById('userDropdown');
            
            if (userBtn) {
                userBtn.innerHTML = `
                    ${data.user.anhdaidien ? 
                        `<img src="/api/profile/avatar/${data.user.anhdaidien}" alt="Avatar" class="user-avatar" onerror="this.onerror=null; this.src='/static/images/default-avatar.svg';">` : 
                        '<img src="/static/images/default-avatar.svg" alt="Avatar" class="user-avatar">'}
                    <i class="fas fa-chevron-down"></i>
                `;
            }
            if (userDropdown) {
                userDropdown.innerHTML = `
                    <a href="/profile" data-lang-vi="Thông tin cá nhân" data-lang-en="Profile">
                        <i class="fas fa-user"></i> Thông tin cá nhân
                    </a>
                    <a href="#" onclick="logout()" data-lang-vi="Đăng xuất" data-lang-en="Logout">
                        <i class="fas fa-sign-out-alt"></i> Đăng xuất
                    </a>
                `;
            }
            
            localStorage.setItem('user_info', JSON.stringify(data.user));
            
            // ✅ FIX: Load unread count ngay sau khi đăng nhập
            await updateUnreadCount();
        } else {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_info');
        }
        
    } catch (error) {
        console.error('Error checking login status:', error);
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_info');
    }
}

// ==================== HELPER FUNCTIONS ====================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMessageTime(timeStr) {
    if (!timeStr) return '';
    
    const date = new Date(timeStr);
    if (!timeStr.includes('Z') && !timeStr.includes('+')) {
        const utcDate = new Date(timeStr.replace(' ', 'T') + 'Z');
        return utcDate.toLocaleTimeString('vi-VN', { 
            hour: '2-digit', 
            minute: '2-digit',
            timeZone: 'Asia/Ho_Chi_Minh' 
        });
    }
    
    return date.toLocaleTimeString('vi-VN', { 
        hour: '2-digit', 
        minute: '2-digit',
        timeZone: 'Asia/Ho_Chi_Minh'
    });
}
