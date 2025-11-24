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
    initNavbar();
    initDropdowns();
    loadServices();
    loadServicePicker();
    initSmoothScroll();
    checkLoginStatus(); // Kiểm tra đăng nhập và load unread count
    setupChatRefresh(); // Setup auto-refresh cho chat
    setupChatInput(); // Setup input handler
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

// ==================== LANGUAGE ====================
function changeLang(lang) {
    currentLang = lang;
    const currentLangEl = document.getElementById('currentLang');
    if (currentLangEl) {
        currentLangEl.textContent = lang.toUpperCase();
    }
    
    const elements = document.querySelectorAll('[data-lang-' + lang + ']');
    elements.forEach(el => {
        const text = el.getAttribute('data-lang-' + lang);
        if (el.tagName === 'INPUT') {
            el.placeholder = el.getAttribute('data-lang-' + lang + '-placeholder');
        } else {
            el.textContent = text;
        }
    });
    
    const langDropdown = document.getElementById('langDropdown');
    if (langDropdown) langDropdown.classList.remove('show');
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
                        <button class="btn btn-outline" onclick="event.stopPropagation(); viewServiceDetail(${service.madv})">
                            Chi tiết
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function viewServiceDetail(serviceId) {
    window.location.href = `/services/${serviceId}`;
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
        if (!token) {
            const chatMessages = document.getElementById('chatMessages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="chat-login-prompt">
                        <p>Vui lòng đăng nhập để sử dụng tính năng chat</p>
                        <a href="/login" class="btn btn-primary btn-sm">Đăng nhập</a>
                    </div>
                `;
            }
            return;
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
                
                return `
                    <div class="chat-message ${messageClass}">
                        <div class="message-content">
                            <p>${escapeHtml(msg.noidung)}</p>
                            <span class="message-time">${formatMessageTime(msg.thoigiangui || msg.thoigian)}</span>
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

function showChatMessage(type, message) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const messageClass = type === 'user' ? 'user-message' : 'bot-message';
    const messageHtml = `
        <div class="chat-message ${messageClass}">
            <div class="message-content">
                <p>${escapeHtml(message)}</p>
                <span class="message-time">${new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
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
        // Không cần reload messages vì đã hiển thị tin nhắn rồi
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
            
            servicePickerList.innerHTML = data.services.map(service => `
                <div class="service-picker-item" onclick="selectService(${service.madv}, '${service.tendv}')">
                    <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                         alt="${service.tendv}" 
                         class="service-picker-image"
                         onerror="this.src='/static/images/default-service.jpg'">
                    <div class="service-picker-info">
                        <div class="service-picker-name">${service.tendv}</div>
                        <div class="service-picker-price">${formatPrice(service.gia)}</div>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading service picker:', error);
    }
}

function selectService(serviceId, serviceName) {
    const input = document.getElementById('chatInput');
    if (input) {
        input.value = `Tôi muốn đặt lịch dịch vụ: ${serviceName}`;
    }
    toggleServicePicker();
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
                        `<img src="/api/profile/avatar/${data.user.anhdaidien}" alt="Avatar" class="user-avatar">` : 
                        '<i class="fas fa-user-circle"></i>'}
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
    return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}