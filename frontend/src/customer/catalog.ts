export type PublicService = { madv: number; tendv: string; mota?: string; gia: number | string | null; thoiluong?: number; anhdichvu?: string };
export const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function price(value: PublicService['gia']) {
  return value === null || value === undefined || value === '' || !Number.isFinite(Number(value))
    ? 'Liên hệ' : new Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'}).format(Number(value));
}
export function serviceCard(service: PublicService, category = '') {
  const id = Number(service.madv), name = escapeHtml(service.tendv);
  const image = service.anhdichvu ? `data:image/jpeg;base64,${escapeHtml(service.anhdichvu)}` : '/static/images/default-service.jpg';
  return `<article class="service-card" data-service-id="${id}">
    <a href="/services/${id}" class="service-image-container" tabindex="-1" aria-hidden="true"><img class="service-image" src="${image}" alt="" width="640" height="480" loading="lazy" onerror="this.onerror=null;this.src='/static/images/default-service.jpg'"></a>
    <div class="service-content">${category ? `<span class="service-category">${escapeHtml(category)}</span>` : ''}
    <h3 class="service-name"><a href="/services/${id}">${name}</a></h3>
    <p class="service-description">${escapeHtml(service.mota || '')}</p>
    <div class="service-meta"><span class="service-price">${price(service.gia)}</span>${service.thoiluong ? `<span class="service-duration">${Number(service.thoiluong)} phút</span>` : ''}</div>
    <div class="service-actions"><a class="btn btn-primary" href="/appointments/create?service=${id}" aria-label="Đặt lịch ${name}">Đặt lịch</a><a class="btn btn-outline" href="/services/${id}" aria-label="Chi tiết ${name}">Chi tiết</a></div>
    </div></article>`;
}

declare global {
  interface Window { CustomerCatalog?: { serviceCard: typeof serviceCard; escapeHtml: typeof escapeHtml; price: typeof price } }
}
