(() => {
    'use strict';
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const sent = new Map();
    async function track(action, target) {
        const auth = window.CustomerAuth;
        if (!auth) return;
        const key = action + ':' + JSON.stringify(target);
        if (Date.now() - (sent.get(key) || 0) < 600000) return;
        try {
            const token = auth.getAccessToken() || await auth.restoreAccessToken();
            if (!token) return;
            sent.set(key, Date.now());
            const response = await auth.fetch('/api/recommendations/events', {
                method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action, ...target})
            });
            if (!response.ok) sent.delete(key);
        } catch (_) { sent.delete(key); }
    }
    const price = value => new Intl.NumberFormat('vi-VN', {style:'currency', currency:'VND'}).format(Number(value));
    function serviceCard(service) {
        return `<article class="service-card" data-service-id="${service.madv}">
            <a class="service-image-container" style="display:block" href="/services/${service.madv}"><img class="service-image" loading="lazy"
                src="${service.anhdichvu ? 'data:image/jpeg;base64,' + service.anhdichvu : '/static/images/default-service.jpg'}" alt="${escape(service.tendv)}"></a>
            <div class="service-content"><span class="recommendation-type">Dịch vụ</span><h3 class="service-name">${escape(service.tendv)}</h3>
                <p class="service-description">${escape(service.reason)}</p><div class="service-meta"><span class="service-price">${price(service.gia)}</span>
                ${service.thoiluong ? `<span class="service-duration">${Number(service.thoiluong)} phút</span>` : ''}</div>
                <div class="service-actions"><a class="btn btn-primary" href="/appointments/create?service=${service.madv}">Đặt lịch</a>
                <a class="btn btn-outline" href="/services/${service.madv}">Chi tiết</a></div></div></article>`;
    }
    async function load() {
        const root = document.getElementById('relatedRecommendations');
        if (!root) return;
        const serviceId = Number(window.location.pathname.match(/^\/services\/(\d+)\/?$/)?.[1]);
        if (!serviceId) return;
        try {
            const url = `/api/recommendations/related/${serviceId}`;
            const response = await (window.CustomerAuth ? window.CustomerAuth.fetch(url) : fetch(url));
            if (!response.ok) throw new Error('Recommendations unavailable');
            const data = await response.json();
            if (!data.success) throw new Error('Recommendations unavailable');
            const items = data.items.filter(item => item.type === 'service' ? Number(item.madv) !== serviceId : item.type === 'package' && window.PackageCare);
            root.querySelector('[data-related-items]').innerHTML = items.map(item => item.type === 'service' ? serviceCard(item) :
                window.PackageCare.packageHtml(item, '<span class="recommendation-type">Gói</span>').replace('<article ', `<article data-package-id="${Number(item.magoi)}" `) +
                `<div class="package-card-actions"><p>${escape(item.reason)}</p><a class="btn btn-primary" href="/packages/${item.magoi}">Xem gói</a></div></article>`).join('');
            root.hidden = !items.length;
        } catch (_) { root.hidden = true; }
    }
    // Capture runs before inline navigation handlers. keepalive retains tracking on page exit.
    document.addEventListener('click', event => {
        const card = event.target.closest('.service-card[data-service-id]');
        const link = event.target.closest('a[href]');
        const detail = link?.getAttribute('href')?.match(/^\/services\/(\d+)(?:[?#]|$)/);
        const id = card ? Number(card.dataset.serviceId) : Number(detail?.[1]);
        if (id > 0) track('click_service', {madv: id});
    }, true);
    document.addEventListener('DOMContentLoaded', load);
    window.CustomerRecommendations = {track, refresh: load};
})();
