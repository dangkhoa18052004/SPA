document.getElementById('adminLoginForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const taikhoan = document.getElementById('taikhoan').value;
    const matkhau = document.getElementById('matkhau').value;
    const errorMessage = document.getElementById('error-message');
    
    try {
        const response = await fetch('/api/auth/login/staff', { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ taikhoan, matkhau })
        });
        
        const result = await response.json();
        
        console.log('Login response:', result);
        
        if (result.success && result.access_token && result.user) {
            console.log('Saving to localStorage...');
            
            localStorage.setItem('admin_token', result.access_token);
            localStorage.setItem('admin_role', result.user.role);
            localStorage.setItem('admin_user', JSON.stringify(result.user));
            
            const savedToken = localStorage.getItem('admin_token');
            const savedRole = localStorage.getItem('admin_role');
            
            console.log('Token saved:', savedToken);
            console.log('Role saved:', savedRole);
            
            if (savedToken && savedRole) {
                console.log('Redirecting to dashboard...');
                window.location.href = '/admin/profile';
            } else {
                console.error('Failed to save to localStorage!');
                errorMessage.textContent = 'Lỗi lưu thông tin đăng nhập. Vui lòng thử lại.';
                errorMessage.style.display = 'block';
            }
            
        } else {
            errorMessage.textContent = result.message || 'Tài khoản hoặc mật khẩu không đúng.';
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        console.error('Lỗi đăng nhập admin:', error);
        errorMessage.textContent = 'Có lỗi xảy ra. Vui lòng thử lại.';
        errorMessage.style.display = 'block';
    }
});