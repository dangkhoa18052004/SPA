// Global variables
let servicesPageAllServices = [];  
let servicesPageFilteredServices = [];
const servicesPageDefaultOrder = new Map();
let currentCategory = 'all';

// Service categories mapping - Đã đặt ở GLOBAL SCOPE
const serviceCategories = {
    'massage': ['massage', 'thư giãn', 'body massage', 'foot massage', 'bấm huyệt', 'đá nóng', 'cổ vai gáy'],
    'facial': ['da mặt', 'facial', 'chăm sóc da', 'mặt nạ', 'tẩy da chết', 'làm sạch da', 'trẻ hóa', 'lão hóa', 'da mụn', 'phục hồi da'],
    'nail': ['nail', 'móng', 'manicure', 'pedicure', 'sơn gel', 'sơn móng', 'vẽ móng', '3d nail', 'đắp móng', 'làm nail', 'chăm sóc móng'],
    'hair': ['tóc', 'gội đầu', 'hair', 'chăm sóc tóc', 'duỗi', 'nhuộm', 'hấp dầu', 'gội dưỡng sinh', 'ủ tóc', 'phục hồi tóc'],
    'body': ['tắm trắng', 'body', 'wax', 'triệt lông', 'điều trị', 'detox', 'săn chắc', 'tẩy tế bào chết toàn thân', 'giảm béo']
};

// ==================== HÀM PHÂN LOẠI DỊCH VỤ (ĐÃ SỬA LỖI LOGIC) ====================
function detectServiceCategory(name, description) {
    const text = (name + ' ' + (description || '')).toLowerCase();
    
    const matchScores = {}; 
    let bestCategory = 'other';
    let maxScore = 0;

    // 1. Tính điểm số khớp cho mỗi danh mục
    for (const [category, keywords] of Object.entries(serviceCategories)) {
        matchScores[category] = 0;
        for (const keyword of keywords) {
            if (text.includes(keyword)) {
                // Cho điểm cao hơn cho từ khóa dài (> 5 ký tự)
                matchScores[category] += (keyword.length > 5 ? 2 : 1); 
            }
        }
    }

    // 2. Áp dụng quy tắc ưu tiên cứng cho Nail và Hair (để tránh nhầm với Massage/Facial)
    if (matchScores['nail'] > 0) return 'nail';
    if (matchScores['hair'] > 0) return 'hair';
    
    // 3. Chọn danh mục có điểm số cao nhất trong các danh mục còn lại
    for (const category in matchScores) {
        if (matchScores[category] > maxScore) {
            maxScore = matchScores[category];
            bestCategory = category;
        }
    }

    if (maxScore === 0) {
        return 'other';
    }
    return bestCategory;
}

// =================================================================================

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    console.log('Services page loaded');
    restoreCatalogFilters();
    loadAllServices();
});

function restoreCatalogFilters() {
    if (!window.CustomerCatalog) return;
    const params = new URLSearchParams(location.search);
    const category = params.get('category') || 'all';
    currentCategory = ['all', ...Object.keys(serviceCategories), 'other'].includes(category) ? category : 'all';
    document.getElementById('searchInput').value = params.get('search') || '';
    const sort = document.getElementById('sortSelect');
    sort.value = [...sort.options].some(o => o.value === params.get('sort')) ? params.get('sort') : 'default';
    markCatalogCategory();
}
window.addEventListener?.('popstate', () => { restoreCatalogFilters(); filterServices(); });

function markCatalogCategory() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        const active = btn.getAttribute('onclick') === `filterByCategory('${currentCategory}')`;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', String(active));
    });
}

function clearServiceFilters() {
    currentCategory = 'all';
    document.getElementById('searchInput').value = '';
    document.getElementById('sortSelect').value = 'default';
    markCatalogCategory();
    filterServices();
}

// ==================== LOAD SERVICES ====================
async function loadAllServices() {
    try {
        showSkeletonLoading();
        
        const response = await (window.CustomerAuth ? window.CustomerAuth.fetch('/api/services') : fetch('/api/services'));
        if (!response.ok) throw new Error('Services unavailable');
        const data = await response.json();
        
        
        if (data.success && data.services) {
            servicesPageAllServices = data.services;
            servicesPageDefaultOrder.clear();
            servicesPageAllServices.forEach((s, index) => servicesPageDefaultOrder.set(s.madv, index));
            
            console.log(`Loaded ${servicesPageAllServices.length} services`);
            filterServices();
        } else {
            showError('Không thể tải danh sách dịch vụ');
        }
    } catch (error) {
        console.error('Error loading services:', error);
        showError('Có lỗi xảy ra khi tải dịch vụ');
    }
}

// ==================== DISPLAY SERVICES ====================
function displayServices(services) {
    const servicesGrid = document.getElementById('servicesGrid');
    const noResults = document.getElementById('noResults');
    
    if (!servicesGrid) {
        console.error('servicesGrid element not found');
        return;
    }
    
    console.log(`Displaying ${services.length} services`);
    
    if (services.length === 0) {
        servicesGrid.innerHTML = '';
        if (noResults) noResults.style.display = 'block';
        return;
    }
    
    if (noResults) noResults.style.display = 'none';
    
    servicesGrid.innerHTML = services.map(service => {
        const category = servicePageCategory(service);
        const categoryLabel = getCategoryLabel(category);
        if (window.CustomerCatalog) return window.CustomerCatalog.serviceCard(service, categoryLabel);
        
        console.log(`Service: ${service.tendv} -> Category: ${category}`);
        
        return `
            <div class="service-card" data-service-id="${service.madv}" onclick="viewServiceDetail(${service.madv})">
                <div class="service-image-container">
                    <img src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" 
                            alt="${service.tendv}" 
                            class="service-image"
                            onerror="this.src='/static/images/default-service.jpg'">
                    ${service.thoiluong ? `<div class="service-badge">${service.thoiluong} phút</div>` : ''}
                </div>
                <div class="service-content">
                    <span class="service-category">${categoryLabel}</span>
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

    if (typeof changeLang === 'function') {
        changeLang(localStorage.getItem('spa_lang') || 'vi');
    }
}

// ==================== FILTER BY CATEGORY ====================
function servicePageCategory(service) {
    const slug = service.category_slug;
    if (slug) return ({acne: 'facial', 'body-care': 'body'})[slug] || slug;
    // Preserve the existing visual filter for legacy rows without a category FK.
    // Recommendation scoring itself always uses the persisted category.
    return detectServiceCategory(service.tendv, service.mota);
}

function filterByCategory(category) {
    currentCategory = category;
    markCatalogCategory();
    filterServices();
}

// Get category label
function getCategoryLabel(category) {
    const labels = {
        'massage': 'Massage',
        'facial': 'Chăm sóc da',
        'nail': 'Nail & Móng',
        'hair': 'Tóc & Đầu',
        'body': 'Điều trị cơ thể',
        'other': 'Khác'
    };
    return labels[category] || 'Khác';
}

// ==================== SEARCH FILTER ====================
function filterServices() {
    const searchTerm = (document.getElementById('searchInput')?.value || '').toLowerCase().trim();
    // Filter candidates first. Scores are independent of candidate membership, so
    // restricting the server order produces exactly the same personalized ranking.
    servicesPageFilteredServices = servicesPageAllServices.filter(service =>
        (currentCategory === 'all' || servicePageCategory(service) === currentCategory) &&
        (!searchTerm || service.tendv.toLowerCase().includes(searchTerm) ||
            (service.mota || '').toLowerCase().includes(searchTerm)));
    const sort = document.getElementById('sortSelect')?.value || 'default';
    const comparators = {
        'name-asc': (a, b) => a.tendv.localeCompare(b.tendv, 'vi'),
        'name-desc': (a, b) => b.tendv.localeCompare(a.tendv, 'vi'),
        'price-asc': (a, b) => Number(a.gia) - Number(b.gia),
        'price-desc': (a, b) => Number(b.gia) - Number(a.gia),
        'default': (a, b) => servicesPageDefaultOrder.get(a.madv) - servicesPageDefaultOrder.get(b.madv)
    };
    servicesPageFilteredServices.sort(comparators[sort] || comparators.default);
    displayServices(servicesPageFilteredServices);
    const result = document.getElementById('catalogResultCount');
    if (result) result.textContent = `${servicesPageFilteredServices.length} dịch vụ`;
    if (window.CustomerCatalog) {
        const url = new URL(location.href);
        for (const [key, value, fallback] of [['search', searchTerm, ''], ['category', currentCategory, 'all'], ['sort', sort, 'default']]) {
            value === fallback ? url.searchParams.delete(key) : url.searchParams.set(key, value);
        }
        history.replaceState(null, '', url.pathname + url.search + url.hash);
    }
}

function sortServices() {
    filterServices();
}

// ==================== VIEW SERVICE DETAIL ====================
function viewServiceDetail(serviceId) {
    window.location.href = `/services/${serviceId}`;
}

// ==================== UTILITY FUNCTIONS ====================
function formatPrice(price) {
    return new Intl.NumberFormat('vi-VN', { 
        style: 'currency', 
        currency: 'VND' 
    }).format(parseFloat(price));
}

function showSkeletonLoading() {
    const servicesGrid = document.getElementById('servicesGrid');
    if (!servicesGrid) return;
    
    servicesGrid.innerHTML = Array(6).fill(0).map(() => `
        <div class="service-skeleton">
            <div class="skeleton-image"></div>
            <div class="skeleton-content">
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line"></div>
            </div>
        </div>
    `).join('');
}

function showError(message) {
    const servicesGrid = document.getElementById('servicesGrid');
    if (!servicesGrid) return;
    
    servicesGrid.innerHTML = `
        <div role="alert" style="grid-column: 1/-1; text-align: center; padding: 60px 20px;">
            <i class="fas fa-exclamation-circle" style="font-size: 64px; color: #ddd; margin-bottom: 20px; display: block;"></i>
            <p style="font-size: 18px; color: #999;">${message}</p>
            <button onclick="loadAllServices()" class="btn btn-primary" style="margin-top: 20px;">
                <i class="fas fa-redo"></i> Thử lại
            </button>
        </div>
    `;
}
