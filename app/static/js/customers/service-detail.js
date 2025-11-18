// Get service ID from URL
const urlParts = window.location.pathname.split('/');
const serviceId = urlParts[urlParts.length - 1];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadServiceDetail();
    loadRelatedServices();
});

// ==================== LOAD SERVICE DETAIL ====================
async function loadServiceDetail() {
    try {
        showDetailSkeleton();
        
        const response = await fetch(`/api/services/${serviceId}`);
        const data = await response.json();
        
        if (data.success) {
            displayServiceDetail(data.service);
        } else {
            showError('Không tìm thấy dịch vụ');
        }
    } catch (error) {
        console.error('Error loading service detail:', error);
        showError('Có lỗi xảy ra khi tải thông tin dịch vụ');
    }
}

// ==================== DISPLAY SERVICE DETAIL ====================
function displayServiceDetail(service) {
    // Update breadcrumb
    document.getElementById('serviceName').textContent = service.tendv;
    
    // Update page title
    document.title = `${service.tendv} - Sà Spa`;
    
    const container = document.getElementById('serviceDetailContainer');
    
    // Detect category
    const category = detectServiceCategory(service.tendv, service.mota);
    const categoryLabel = getCategoryLabel(category);
    
    // Create features list from description
    const features = generateFeaturesList(service.mota);
    
    container.innerHTML = `
        <div class="service-detail-grid">
            <div class="service-image-section">
                <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                     alt="${service.tendv}" 
                     class="service-main-image"
                     onerror="this.src='/static/images/default-service.jpg'">
                ${service.thoiluong ? `
                    <div class="service-badge-detail">
                        <i class="fas fa-clock"></i>
                        ${service.thoiluong} phút
                    </div>
                ` : ''}
            </div>
            
            <div class="service-info-section">
                <span class="service-category-badge">${categoryLabel}</span>
                <h1 class="service-detail-name">${service.tendv}</h1>
                <div class="service-detail-price">${formatPrice(service.gia)}</div>
                
                <div class="service-meta-info">
                    ${service.thoiluong ? `
                        <div class="meta-item">
                            <i class="fas fa-clock"></i>
                            <span>${service.thoiluong} phút</span>
                        </div>
                    ` : ''}
                    ${service.donvitinh ? `
                        <div class="meta-item">
                            <i class="fas fa-tag"></i>
                            <span>${service.donvitinh}</span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="service-detail-description">
                    <p>${service.mota || 'Trải nghiệm dịch vụ chăm sóc sức khỏe và sắc đẹp cao cấp tại Sà Spa. Đội ngũ kỹ thuật viên chuyên nghiệp với nhiều năm kinh nghiệm sẽ mang đến cho bạn những phút giây thư giãn tuyệt vời nhất.'}</p>
                </div>
                
                ${features.length > 0 ? `
                    <div class="service-features">
                        <h3><i class="fas fa-check-circle" style="color: #C9A961; margin-right: 10px;"></i>Lợi ích dịch vụ</h3>
                        <ul class="feature-list">
                            ${features.map(feature => `
                                <li><i class="fas fa-check"></i><span>${feature}</span></li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                <div class="service-note">
                    <h4><i class="fas fa-info-circle"></i> Lưu ý</h4>
                    <p>Vui lòng đặt lịch trước để đảm bảo có chỗ. Quý khách nên đến trước 10 phút để làm thủ tục và chuẩn bị.</p>
                </div>
                
                <div class="service-actions-detail">
                    <a href="/appointments/create?service=${service.madv}" class="btn btn-outline" style="padding: 15px 30px; font-size: 16px;">
                        <i class="fas fa-calendar-check"></i> Đặt lịch ngay
                    </a>
                    <button class="btn btn-outline" onclick="openChatWithService('${service.tendv}')">
                        <i class="fas fa-comments"></i> Liên hệ
                    </button>
                </div>
            </div>
        </div>
    `;
}

// ==================== LOAD RELATED SERVICES ====================
async function loadRelatedServices() {
    try {
        const response = await fetch('/api/services');
        const data = await response.json();
        
        if (data.success) {
            // Filter out current service and get 3 random services
            const relatedServices = data.services
                .filter(s => s.madv != serviceId)
                .sort(() => Math.random() - 0.5)
                .slice(0, 3);
            
            displayRelatedServices(relatedServices);
        }
    } catch (error) {
        console.error('Error loading related services:', error);
    }
}

// ==================== DISPLAY RELATED SERVICES ====================
function displayRelatedServices(services) {
    const grid = document.getElementById('relatedServicesGrid');
    
    if (services.length === 0) {
        grid.innerHTML = '<p style="text-align: center; color: #999;">Không có dịch vụ liên quan</p>';
        return;
    }
    
    grid.innerHTML = services.map(service => `
        <div class="service-card" onclick="window.location.href='/services/${service.madv}'">
            <div class="service-image-container">
                <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                     alt="${service.tendv}" 
                     class="service-image"
                     onerror="this.src='/static/images/default-service.jpg'">
            </div>
            <div class="service-content">
                <h3 class="service-name">${service.tendv}</h3>
                <p class="service-description">${service.mota || 'Dịch vụ chất lượng cao'}</p>
                <div class="service-meta">
                    <div class="service-price">${formatPrice(service.gia)}</div>
                    ${service.thoiluong ? `
                        <div class="service-duration">
                            <i class="fas fa-clock"></i>
                            <span>${service.thoiluong}p</span>
                        </div>
                    ` : ''}
                </div>
                <div class="service-actions">
                    <a href="/appointments/create?service=${service.madv}" class="btn btn-outline" onclick="event.stopPropagation()">
                        Đặt lịch
                    </a>
                    <button class="btn btn-outline" onclick="event.stopPropagation(); window.location.href='/services/${service.madv}'">
                        Chi tiết
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// ==================== UTILITY FUNCTIONS ====================
function formatPrice(price) {
    return new Intl.NumberFormat('vi-VN', { 
        style: 'currency', 
        currency: 'VND' 
    }).format(price);
}

function detectServiceCategory(name, description) {
    const text = (name + ' ' + (description || '')).toLowerCase();
    
    const serviceCategories = {
        'massage': ['massage', 'thư giãn', 'body massage', 'foot massage'],
        'facial': ['da mặt', 'facial', 'chăm sóc da', 'mặt nạ', 'tẩy da chết'],
        'nail': ['nail', 'móng', 'manicure', 'pedicure'],
        'hair': ['tóc', 'gội đầu', 'hair', 'chăm sóc tóc', 'duỗi', 'nhuộm'],
        'body': ['tắm trắng', 'body', 'wax', 'triệt lông', 'điều trị']
    };
    
    for (const [category, keywords] of Object.entries(serviceCategories)) {
        for (const keyword of keywords) {
            if (text.includes(keyword)) {
                return category;
            }
        }
    }
    
    return 'other';
}

function getCategoryLabel(category) {
    const labels = {
        'massage': 'Massage',
        'facial': 'Chăm sóc da',
        'nail': 'Nail & Móng',
        'hair': 'Tóc & Đầu',
        'body': 'Điều trị cơ thể',
        'other': 'Dịch vụ spa'
    };
    return labels[category] || 'Dịch vụ spa';
}

function generateFeaturesList(description) {

    
    return [];
}

function showDetailSkeleton() {
    const container = document.getElementById('serviceDetailContainer');
    container.innerHTML = `
        <div class="detail-skeleton">
            <div class="skeleton-image-section"></div>
            <div class="skeleton-info-section">
                <div class="skeleton-line" style="width: 30%; height: 30px;"></div>
                <div class="skeleton-line title"></div>
                <div class="skeleton-line price"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line"></div>
            </div>
        </div>
    `;
}

function showError(message) {
    const container = document.getElementById('serviceDetailContainer');
    container.innerHTML = `
        <div style="text-align: center; padding: 60px 20px;">
            <i class="fas fa-exclamation-circle" style="font-size: 64px; color: #ddd; margin-bottom: 20px;"></i>
            <h2 style="color: #999; margin-bottom: 20px;">${message}</h2>
            <a href="/services" class="btn btn-outline">
                <i class="fas fa-arrow-left"></i> Quay lại danh sách dịch vụ
            </a>
        </div>
    `;
}

function openChatWithService(serviceName) {
    openChat();
    setTimeout(() => {
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.value = `Tôi muốn hỏi về dịch vụ: ${serviceName}`;
        }
    }, 500);
}