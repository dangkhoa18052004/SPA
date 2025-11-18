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

