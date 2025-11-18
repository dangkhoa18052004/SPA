// Toggle Password Visibility
function togglePassword() {
    const passwordInput = document.getElementById('matkhau');
    const eyeIcon = document.getElementById('eyeIcon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.classList.remove('fa-eye');
        eyeIcon.classList.add('fa-eye-slash');
    } else {
        passwordInput.type = 'password';
        eyeIcon.classList.remove('fa-eye-slash');
        eyeIcon.classList.add('fa-eye');
    }
}

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// ==================== LOGIN ====================
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(loginForm);
        const data = Object.fromEntries(formData);
        
        try {
            const response = await fetch('/api/auth/login/customer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.access_token) { // Kiểm tra access_token
                showAlert('success', 'Đăng nhập thành công! Đang chuyển hướng...');
                
                // Lưu token và user info
                localStorage.setItem('access_token', result.access_token);
                if (result.user) {
                    localStorage.setItem('user_info', JSON.stringify(result.user));
                }
                
                setTimeout(() => {
                    const redirectUrl = new URLSearchParams(window.location.search).get('redirect') || '/';
                    window.location.href = redirectUrl;
                }, 1000);
            } else {
                showAlert('error', result.message || 'Tài khoản hoặc mật khẩu không đúng!');
            }
        } catch (error) {
            console.error('Login error:', error);
            showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
        }
    });
}

// ==================== REGISTRATION ====================
const registerForm = document.getElementById('registerForm');
if (registerForm) {
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(registerForm);
        const data = Object.fromEntries(formData);
        
        // ... (Validate passwords, phone, email)
        if (data.matkhau !== data.confirm_password) {
            showAlert('error', 'Mật khẩu xác nhận không khớp!');
            return;
        }
        if (!/^[0-9]{10}$/.test(data.sdt)) {
            showAlert('error', 'Số điện thoại phải có 10 chữ số!');
            return;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
            showAlert('error', 'Email không hợp lệ!');
            return;
        }
        
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // ✅ SỬA LỖI 2: Lưu email để trang OTP có thể gửi lại
                sessionStorage.setItem('otp_email', data.email);
                
                showAlert('success', 'Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản.');
                setTimeout(() => {
                    window.location.href = '/auth/verify-otp';
                }, 2000);
            } else {
                showAlert('error', result.message || 'Đăng ký thất bại!');
            }
        } catch (error) {
            console.error('Registration error:', error);
            showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
        }
    });
}

// ==================== OTP VERIFICATION ====================
const otpInputs = document.querySelectorAll('.otp-input');
if (otpInputs.length > 0) {
    // ... (Code xử lý input OTP của bạn đã đúng, giữ nguyên)
    otpInputs.forEach((input, index) => {
        input.addEventListener('input', function(e) {
            if (e.target.value.length === 1) {
                if (index < otpInputs.length - 1) {
                    otpInputs[index + 1].focus();
                }
            }
        });
        
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && !e.target.value) {
                if (index > 0) {
                    otpInputs[index - 1].focus();
                }
            }
        });
    });
}

async function verifyOTP() {
    // ... (Code verifyOTP của bạn đã đúng, giữ nguyên)
    const otpInputs = document.querySelectorAll('.otp-input');
    const otp = Array.from(otpInputs).map(input => input.value).join('');
    
    if (otp.length !== 6) {
        showAlert('error', 'Vui lòng nhập đầy đủ mã OTP!');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/verify-otp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ otp_code: otp })
        });
        
        const result = await response.json();
        
        if (result.success) {
            sessionStorage.removeItem('otp_email'); // Dọn dẹp
            showAlert('success', 'Xác thực thành công! Đang chuyển hướng...');
            setTimeout(() => {
                window.location.href = '/auth/login';
            }, 1500);
        } else {
            showAlert('error', result.message || 'Mã OTP không đúng!');
        }
    } catch (error) {
        console.error('OTP verification error:', error);
        showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
    }
}

// Resend OTP
let resendTimer;
let resendCountdown = 60;

function startResendTimer() {
    // ... (Code timer của bạn đã đúng, giữ nguyên)
    const resendBtn = document.getElementById('resendBtn');
    const timerSpan = document.getElementById('resendTimer');
    
    if (!resendBtn || !timerSpan) return;
    
    resendBtn.disabled = true;
    resendCountdown = 60;
    
    resendTimer = setInterval(() => {
        resendCountdown--;
        timerSpan.textContent = `(${resendCountdown}s)`;
        
        if (resendCountdown <= 0) {
            clearInterval(resendTimer);
            resendBtn.disabled = false;
            timerSpan.textContent = '';
        }
    }, 1000);
}

async function resendOTP() {
    // ✅ SỬA LỖI 2: Lấy email từ sessionStorage
    const email = sessionStorage.getItem('otp_email');
    if (!email) {
        showAlert('error', 'Không tìm thấy email. Vui lòng thử đăng ký lại.');
        return;
    }

    try {
        const response = await fetch('/api/auth/resend-otp', {
            method: 'POST',
            // ✅ SỬA LỖI 2: Gửi email đi
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('success', 'Đã gửi lại mã OTP. Vui lòng kiểm tra email!');
            startResendTimer();
        } else {
            showAlert('error', result.message || 'Không thể gửi lại mã OTP!');
        }
    } catch (error) {
        console.error('Resend OTP error:', error);
        showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('resendBtn')) {
        startResendTimer();
    }
});

// ==================== FORGOT PASSWORD ====================
const forgotPasswordForm = document.getElementById('forgotPasswordForm');
if (forgotPasswordForm) {
    forgotPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const identifier = document.getElementById('identifier').value;
        
        if (!identifier) {
            showAlert('error', 'Vui lòng nhập Email hoặc SĐT.');
            return;
        }

        try {
            const response = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ identifier: identifier }) 
            });
            const result = await response.json();
            
            if (response.ok) {
                if (identifier.includes('@')) {
                    sessionStorage.setItem('reset_email', identifier);
                }
                
                showAlert('success', 'Đã gửi mã khôi phục về email của bạn!');
                setTimeout(() => {
                    window.location.href = '/auth/reset-password';
                }, 2000);
            } else {                
                if (response.status === 400 && result.message.includes("email. Vui lòng đăng nhập bằng SĐT")) {
                    showAlert('warning', result.message);
                } else {
                    showAlert('error', result.message || 'Email hoặc SĐT không tồn tại!');
                }
            }
        } catch (error) {
            console.error('Forgot password error:', error);
            showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
        }
    });
}

// ==================== RESET PASSWORD ====================
const resetPasswordForm = document.getElementById('resetPasswordForm');
if (resetPasswordForm) {
    resetPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(resetPasswordForm);
        const data = Object.fromEntries(formData);
        
        // ... (Validate passwords)
        if (data.matkhau !== data.confirm_password) {
            showAlert('error', 'Mật khẩu xác nhận không khớp!');
            return;
        }
        if (data.matkhau.length < 6) {
            showAlert('error', 'Mật khẩu phải có ít nhất 6 ký tự!');
            return;
        }
        
        const email = sessionStorage.getItem('reset_email');
        if (!email) {
            showAlert('error', 'Phiên khôi phục đã hết hạn. Vui lòng thử lại từ trang Quên mật khẩu.');
            return;
        }
        data.email = email;

        // ✅ SỬA LỖI 1: Đổi tên key từ 'token' thành 'reset_code'
        data.reset_code = data.token; // Copy giá trị
        delete data.token; // Xóa key 'token' cũ
        
        try {
            const response = await fetch('/api/auth/reset-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data) // data giờ đã có 'reset_code'
            });
            
            const result = await response.json();
            
            if (result.success) {
                sessionStorage.removeItem('reset_email'); // Dọn dẹp
                showAlert('success', 'Đặt lại mật khẩu thành công!');
                setTimeout(() => {
                    window.location.href = '/auth/login';
                }, 2000);
            } else {
                showAlert('error', result.message || 'Mã khôi phục không đúng!');
            }
        } catch (error) {
            console.error('Reset password error:', error);
            showAlert('error', 'Có lỗi xảy ra. Vui lòng thử lại!');
        }
    });
}

// ==================== UTILITY FUNCTIONS ====================
function showAlert(type, message) {
    // ... (Code của bạn đã đúng, giữ nguyên)
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const form = document.querySelector('form');
    if (form) {
        form.insertAdjacentElement('beforebegin', alertDiv);
        
        setTimeout(() => {
            alertDiv.style.opacity = '0';
            setTimeout(() => alertDiv.remove(), 300);
        }, 5000);
    }
}