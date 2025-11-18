let conversations = [];
let currentConversation = null;
let messages = [];
let refreshInterval = null;
let isSending = false; 

// ===================================
// ======= KHỞI TẠO & SỰ KIỆN =========
// ===================================

// ====== KHỞI TẠO ======
document.addEventListener('DOMContentLoaded', function() {
    
    // Đặt trạng thái ban đầu: Dashboard và vô hiệu hóa input
    closeConversation(); 
    
    loadConversations();
    setupEventListeners();
    
    // Thiết lập làm mới định kỳ
    refreshInterval = setInterval(() => {

        loadConversations(false); 
        if (currentConversation) {
            loadMessages(currentConversation.maht, false); 
        }
    }, 5000); // 5 giây 1 lần
});

// ====== SETUP EVENT LISTENERS ======
function setupEventListeners() {
    const sendBtn = document.getElementById('send-message-btn');
    const messageInput = document.getElementById('message-input');
    const closeBtn = document.getElementById('close-conversation-btn'); // Nút đóng
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closeConversation); 
    }
    
    if (messageInput) {
        // 1. Ngăn chặn Enter tạo dòng mới và gửi tin nhắn
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();
                sendMessage();
            }
        });

        // 2. Ngăn chặn sự kiện submit mặc định của form (khắc phục lỗi ReferenceError)
        // Lấy form chứa messageInput
        const form = messageInput.closest('form'); 
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
            });
        }
        
        // **LƯU Ý: Đã xóa khối if (form) bị lặp lại ở cuối hàm.**
    }
}


// Cleanup khi rời trang
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});


// ===================================
// ========== CHỨC NĂNG CHAT ==========
// ===================================

// ====== ĐÓNG HỘI THOẠI ======
function closeConversation() {
    currentConversation = null;
    messages = [];

    const container = document.getElementById('messages-container');
    const nameHeader = document.getElementById('chat-customer-name');
    const closeBtn = document.getElementById('close-conversation-btn');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-message-btn');

    // Cập nhật tiêu đề và trạng thái bên phải
    if (nameHeader) nameHeader.textContent = 'Tin nhắn'; 
    if (container) container.innerHTML = '<div class="no-conversation-selected"></div>'; // Thêm thông báo mặc định
    
    // Ẩn nút đóng và vô hiệu hóa input
    if (closeBtn) closeBtn.style.display = 'none';
    if (messageInput) {
        messageInput.value = '';
        messageInput.disabled = true;
    }
    if (sendBtn) sendBtn.disabled = true;

    // Cập nhật danh sách để loại bỏ trạng thái active
    renderConversationsList();
}

// ====== CHỌN HỘI THOẠI ======
async function selectConversation(maht) {

    if (currentConversation && currentConversation.maht === maht) {
        return;
    }
    
    currentConversation = conversations.find(c => c.maht === maht);
    if (!currentConversation) return;
    
    const nameHeader = document.getElementById('chat-customer-name');
    const closeBtn = document.getElementById('close-conversation-btn');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-message-btn');
    
    // Cập nhật tiêu đề và bật nút đóng, input
    if (nameHeader) nameHeader.textContent = escapeHtml(currentConversation.customer_name || 'Khách hàng');
    if (closeBtn) closeBtn.style.display = 'block'; 
    if (messageInput) messageInput.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
    
    renderConversationsList(); // Cập nhật trạng thái active
    await loadMessages(maht, true); 
    loadConversations(false); // Xóa số đếm tin nhắn chưa đọc
}

// ====== GỬI TIN NHẮN ====== 
async function sendMessage() {
    if (isSending) return;
    if (!currentConversation) {
        showError('Vui lòng chọn một hội thoại');
        return;
    }
    
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message) {
        showError('Vui lòng nhập nội dung tin nhắn');
        return;
    }
    isSending = true;
    const messageBackup = message;
    input.value = ''; 
    input.disabled = true;
    
    try {
        const response = await fetch(`/api/chat/conversations/${currentConversation.maht}/messages`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ noidung: message })
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadMessages(currentConversation.maht, false); 
            loadConversations(false); 
        } else {
            showError(data.message || 'Không thể gửi tin nhắn');
            input.value = messageBackup;
        }
    } catch (error) {
        console.error('Lỗi gửi tin nhắn:', error);
        showError('Không thể gửi tin nhắn');
        input.value = message;
    } finally {
        isSending = false;
        input.disabled = false;
        input.focus(); 
    }
}


// ===================================
// ======= TẢI & RENDER DỮ LIỆU ========
// ===================================

// ====== TẢI DANH SÁCH HỘI THOẠI ======
async function loadConversations(showLoading = true) {
    if (showLoading) {
        const container = document.getElementById('conversations-list');
        if (container) container.innerHTML = '<div class="loading-messages"><i class="fas fa-spinner fa-spin"></i> Đang tải...</div>';
    }
    
    try {
        const response = await fetch('/api/chat/conversations', {
            headers: getAuthHeaders(false)
        });
        const data = await response.json();
        
        if (data.success) {
            conversations = data.conversations || [];
            renderConversationsList();
        } else {
            if (showLoading) showError(data.message || 'Không thể tải danh sách hội thoại');
        }
    } catch (error) {
        console.error('Lỗi tải hội thoại:', error);
        if (showLoading) showError('Không thể tải danh sách hội thoại');
    }
}

// ====== RENDER DANH SÁCH HỘI THOẠI ======
function renderConversationsList() {
    const container = document.getElementById('conversations-list');
    if (!container) return;
    
    const currentSelectedId = currentConversation ? currentConversation.maht : null;
    
    if (conversations.length === 0) {
        container.innerHTML = '<div class="no-conversations">Chưa có hội thoại nào</div>';
        return;
    }
    
    container.innerHTML = conversations.map(conv => {
        
        let avatarHtml = '';
        if (conv.customer_avatar) {
            const imageSrc = `/api/profile/avatar/${escapeHtml(conv.customer_avatar)}`;
            avatarHtml = `<img src="${imageSrc}" alt="Avatar" onerror="this.onerror=null; this.src='/static/img/user-default.png';">`;
        } else {
            avatarHtml = `<i class="fas fa-user-circle"></i>`;
        }

        const customerName = conv.customer_name || 'Khách hàng';

        const unreadBadge = conv.unread_count > 0 
            ? `<div class="unread-badge">${conv.unread_count}</div>` 
            : '';
            
        return `
            <div class="conversation-item ${currentSelectedId && currentSelectedId === conv.maht ? 'active' : ''}" 
                 onclick="selectConversation(${conv.maht})">
                
                <div class="conversation-avatar">
                    ${avatarHtml}
                </div>
                
                <div class="conversation-info">
                    <div class="conversation-name">${escapeHtml(customerName)}</div>
                    <div class="conversation-preview">${escapeHtml(conv.last_message) || 'Chưa có tin nhắn'}</div>
                </div>
                
                <div class="conversation-time">
                    ${conv.last_message_time ? formatTime(conv.last_message_time) : ''}
                </div>
                
                ${unreadBadge} </div>
        `;
    }).join('');
}

// ====== TẢI TIN NHẮN ======
async function loadMessages(maht, showLoadingIndicator = true) {
    try {
        if (showLoadingIndicator) {
            const container = document.getElementById('messages-container');
            if (container) {
                container.innerHTML = '<div class="loading-messages"><i class="fas fa-spinner fa-spin"></i> Đang tải...</div>';
            }
        }
        
        const response = await fetch(`/api/chat/conversations/${maht}/messages`, {
            headers: getAuthHeaders(false)
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Chỉ render nếu tin nhắn thực sự thay đổi (tránh giật)
            if (JSON.stringify(messages) !== JSON.stringify(data.messages)) {
                messages = data.messages || [];
                renderMessages();
            }
        } else {
            if (showLoadingIndicator) showError(data.message || 'Không thể tải tin nhắn');
        }
    } catch (error) {
        console.error('Lỗi tải tin nhắn:', error);
        if (showLoadingIndicator) showError('Không thể tải tin nhắn');
    }
}

// ====== RENDER TIN NHẮN ======
function renderMessages() {
    const container = document.getElementById('messages-container');
    if (!container) return;
    
    if (messages.length === 0) {
        container.innerHTML = '<div class="no-messages">Chưa có tin nhắn nào</div>';
        return;
    }
    
    container.innerHTML = messages.map(msg => {
        const isMyMessage = msg.is_from_staff; 
        return `
            <div class="message ${isMyMessage ? 'message-sent' : 'message-received'}">
                <div class="message-content">
                    <div class="message-text">${escapeHtml(msg.noidung)}</div>
                    <div class="message-time">${formatDateTime(msg.thoigian)}</div>
                </div>
            </div>
        `;
    }).join('');
    
    // Scroll xuống cuối
    scrollToBottom();
}


// ===================================
// ========== CHỨC NĂNG ADMIN =========
// ===================================

// ====== GÁN HỘI THOẠI CHO NHÂN VIÊN ======
async function assignConversation(maht, manv) {
    try {
        const response = await fetch(`/admin/conversations/${maht}/assign`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ manv: manv })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(data.msg || 'Gán hội thoại thành công');
            loadConversations();
        } else {
            showError(data.msg || 'Có lỗi xảy ra');
        }
    } catch (error) {
        console.error('Lỗi:', error);
        showError('Có lỗi xảy ra');
    }
}


// ===================================
// ========== HELPER FUNCTIONS =========
// ===================================

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function formatTime(timeStr) {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    const now = new Date();
    
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
}

function formatDateTime(timeStr) {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    return date.toLocaleString('vi-VN', {
        hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit'
    });
}

function escapeHtml(text) {
    if (text === null || typeof text === 'undefined') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(message) { alert('✅ ' + message); }
function showError(message) { alert('❌ ' + message); }