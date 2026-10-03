(() => {
    'use strict';

    const root = document.querySelector('[data-admin-packages-page]');
    if (!root) return;

    const page = root.dataset.adminPackagesPage;
    const fallbackImage = '/static/images/default-package.svg';
    let services = [];
    let packages = [];

    const escapeHtml = (value) => String(value ?? '')
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    const money = (value) => new Intl.NumberFormat('vi-VN', {
        style: 'currency', currency: 'VND', maximumFractionDigits: 0
    }).format(Number(value) || 0);
    const formatDate = (value) => value
        ? new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value))
        : 'Không giới hạn';

    function headers(json = false) {
        if (typeof window.getAuthHeaders === 'function') return window.getAuthHeaders(json);
        const token = localStorage.getItem('admin_token');
        const result = token ? { Authorization: `Bearer ${token}` } : {};
        if (json) result['Content-Type'] = 'application/json';
        return result;
    }

    async function api(url, options = {}) {
        const isForm = options.body instanceof FormData;
        const response = await fetch(url, {
            ...options,
            headers: { ...headers(Boolean(options.body) && !isForm), ...(options.headers || {}) }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            if (response.status === 401) {
                localStorage.removeItem('admin_token');
                window.location.href = '/admin/login';
            }
            throw new Error(data.message || data.msg || `Không thể xử lý yêu cầu (${response.status})`);
        }
        return data;
    }

    function showMessage(text, type = 'success') {
        const element = document.getElementById('packageMessage');
        if (!element) return;
        element.textContent = text;
        element.className = `package-message visible${type === 'error' ? ' error' : ''}`;
        element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function statusBadge(status) {
        const labels = { active: 'Đang hoạt động', used_up: 'Đã dùng hết', expired: 'Hết hạn', cancelled: 'Đã hủy' };
        return `<span class="package-status ${escapeHtml(status)}">${escapeHtml(labels[status] || status || 'Không xác định')}</span>`;
    }

    function packageValidity(value) {
        return value == null ? 'Không giới hạn' : `${value} tháng`;
    }

    function serviceSummary(items) {
        return (items || []).map((item) => `${escapeHtml(item.tendv)} <strong>× ${item.total_sessions} buổi</strong>`).join('<br>');
    }

    function totalProgress(treatment) {
        return (treatment.items || []).reduce((sum, item) => ({
            used: sum.used + Number(item.consumed || 0),
            total: sum.total + Number(item.total_sessions || 0)
        }), { used: 0, total: 0 });
    }

    async function initList() {
        const notice = sessionStorage.getItem('admin_package_notice');
        if (notice) {
            sessionStorage.removeItem('admin_package_notice');
            showMessage(notice);
        }

        const tabButtons = [...document.querySelectorAll('[data-package-tab]')];
        const activateTab = (name, updateHash = true) => {
            document.querySelectorAll('[data-package-panel]').forEach((panel) => {
                panel.hidden = panel.dataset.packagePanel !== name;
            });
            tabButtons.forEach((button) => {
                const active = button.dataset.packageTab === name;
                button.classList.toggle('active', active);
                button.setAttribute('aria-selected', String(active));
            });
            if (updateHash) history.replaceState(null, '', name === 'treatments' ? '#treatments' : window.location.pathname);
            if (name === 'treatments' && !document.getElementById('adminTreatmentRows').dataset.loaded) loadTreatments();
        };
        tabButtons.forEach((button) => button.addEventListener('click', () => activateTab(button.dataset.packageTab)));
        activateTab(location.hash === '#treatments' ? 'treatments' : 'packages', false);

        document.getElementById('packageSearch').addEventListener('input', renderPackages);
        document.getElementById('packageStatusFilter').addEventListener('change', renderPackages);
        document.getElementById('treatmentStatusFilter').addEventListener('change', loadTreatments);
        let searchTimer;
        document.getElementById('treatmentSearch').addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(loadTreatments, 300);
        });

        const dialog = document.getElementById('treatmentDetailDialog');
        dialog.querySelector('[data-close-treatment]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('click', (event) => {
            if (event.target !== dialog) return;
            const bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
        });
        document.addEventListener('click', (event) => {
            const button = event.target.closest('[data-treatment-id]');
            if (button) openTreatment(button.dataset.treatmentId);
        });

        try {
            const result = await api('/api/admin/packages');
            packages = result.packages || [];
            services = result.services || [];
            renderPackages();
        } catch (error) {
            showMessage(error.message, 'error');
            renderPackages();
        }
    }

    function getFilteredPackages() {
        const term = document.getElementById('packageSearch').value.trim().toLocaleLowerCase('vi');
        const status = document.getElementById('packageStatusFilter').value;
        return packages.filter((pkg) => {
            const matchesStatus = status === 'all' || (status === 'active' ? pkg.active : !pkg.active);
            const haystack = [pkg.tengoi, ...(pkg.items || []).map((item) => item.tendv)].join(' ').toLocaleLowerCase('vi');
            return matchesStatus && (!term || haystack.includes(term));
        });
    }

    function renderPackages() {
        const rows = document.getElementById('adminPackageRows');
        const cards = document.getElementById('adminPackageCards');
        const data = getFilteredPackages();
        if (!data.length) {
            rows.innerHTML = '<tr><td colspan="6" class="package-empty">Không tìm thấy gói dịch vụ phù hợp.</td></tr>';
            cards.innerHTML = '<div class="package-empty">Không tìm thấy gói dịch vụ phù hợp.</div>';
            return;
        }
        rows.innerHTML = data.map((pkg) => `<tr>
            <td><div class="package-name-cell"><img class="package-thumb" src="${escapeHtml(pkg.image_url || fallbackImage)}" alt=""><div><strong>${escapeHtml(pkg.tengoi)}</strong><small>Mã gói #${pkg.magoi}</small></div></div></td>
            <td class="package-service-list">${serviceSummary(pkg.items)}</td>
            <td class="package-price">${money(pkg.giagoi)}</td>
            <td>${packageValidity(pkg.validity_months)}</td>
            <td><span class="package-status ${pkg.active ? 'active' : 'inactive'}">${pkg.active ? 'Đang bán' : 'Ngừng bán'}</span></td>
            <td><div class="package-actions"><a class="package-action-link" href="/admin/packages/${pkg.magoi}"><i class="fas fa-eye"></i> Xem</a><a class="package-action-link" href="/admin/packages/${pkg.magoi}/edit"><i class="fas fa-edit"></i> Sửa</a></div></td>
        </tr>`).join('');
        cards.innerHTML = data.map((pkg) => `<article class="package-mobile-card">
            <div class="package-mobile-card-head"><div class="package-name-cell"><img class="package-thumb" src="${escapeHtml(pkg.image_url || fallbackImage)}" alt=""><div><strong>${escapeHtml(pkg.tengoi)}</strong><small>#${pkg.magoi}</small></div></div><span class="package-status ${pkg.active ? 'active' : 'inactive'}">${pkg.active ? 'Đang bán' : 'Ngừng bán'}</span></div>
            <dl><dt>Dịch vụ</dt><dd>${serviceSummary(pkg.items)}</dd><dt>Giá gói</dt><dd class="package-price">${money(pkg.giagoi)}</dd><dt>Hiệu lực</dt><dd>${packageValidity(pkg.validity_months)}</dd></dl>
            <div class="package-actions"><a class="package-action-link" href="/admin/packages/${pkg.magoi}">Xem chi tiết</a><a class="package-action-link" href="/admin/packages/${pkg.magoi}/edit">Chỉnh sửa</a></div>
        </article>`).join('');
    }

    async function loadTreatments() {
        const rows = document.getElementById('adminTreatmentRows');
        const cards = document.getElementById('adminTreatmentCards');
        rows.dataset.loaded = 'true';
        rows.innerHTML = '<tr><td colspan="8" class="package-loading"><i class="fas fa-spinner fa-spin"></i> Đang tải liệu trình...</td></tr>';
        cards.innerHTML = '<div class="package-loading">Đang tải liệu trình...</div>';
        const params = new URLSearchParams();
        const search = document.getElementById('treatmentSearch').value.trim();
        const status = document.getElementById('treatmentStatusFilter').value;
        if (search) params.set('search', search);
        if (status) params.set('status', status);
        try {
            const result = await api(`/api/admin/packages/treatments?${params}`);
            renderTreatments(result.treatments || []);
        } catch (error) {
            rows.innerHTML = `<tr><td colspan="8" class="package-empty">${escapeHtml(error.message)}</td></tr>`;
            cards.innerHTML = `<div class="package-empty">${escapeHtml(error.message)}</div>`;
        }
    }

    function renderTreatments(data) {
        const rows = document.getElementById('adminTreatmentRows');
        const cards = document.getElementById('adminTreatmentCards');
        if (!data.length) {
            rows.innerHTML = '<tr><td colspan="8" class="package-empty">Không tìm thấy liệu trình phù hợp.</td></tr>';
            cards.innerHTML = '<div class="package-empty">Không tìm thấy liệu trình phù hợp.</div>';
            return;
        }
        rows.innerHTML = data.map((item) => {
            const progress = totalProgress(item);
            const percent = progress.total ? Math.min(100, progress.used / progress.total * 100) : 0;
            return `<tr><td><strong>#${item.mathe}</strong></td><td><strong>${escapeHtml(item.customer_name)}</strong><br><small class="package-muted">${escapeHtml(item.phone)}</small></td><td>${escapeHtml(item.tengoi)}</td><td><div class="treatment-progress">${progress.used}/${progress.total} buổi<div class="treatment-progress-bar"><span style="width:${percent}%"></span></div></div></td><td>${formatDate(item.activated_at)}</td><td>${formatDate(item.expires_at)}</td><td>${statusBadge(item.status)}</td><td><button class="package-action-link" type="button" data-treatment-id="${item.mathe}"><i class="fas fa-eye"></i> Chi tiết</button></td></tr>`;
        }).join('');
        cards.innerHTML = data.map((item) => {
            const progress = totalProgress(item);
            return `<article class="package-mobile-card"><div class="package-mobile-card-head"><div><strong>#${item.mathe} · ${escapeHtml(item.customer_name)}</strong><div class="package-muted">${escapeHtml(item.phone)}</div></div>${statusBadge(item.status)}</div><dl><dt>Gói</dt><dd>${escapeHtml(item.tengoi)}</dd><dt>Tiến độ</dt><dd>${progress.used}/${progress.total} buổi</dd><dt>Hạn dùng</dt><dd>${formatDate(item.expires_at)}</dd></dl><button class="package-action-link" type="button" data-treatment-id="${item.mathe}">Xem chi tiết</button></article>`;
        }).join('');
    }

    async function openTreatment(id) {
        const dialog = document.getElementById('treatmentDetailDialog');
        const content = document.getElementById('treatmentDetailContent');
        content.innerHTML = '<div class="package-loading"><i class="fas fa-spinner fa-spin"></i> Đang tải chi tiết...</div>';
        dialog.showModal();
        try {
            const { treatment } = await api(`/api/admin/packages/treatments/${id}`);
            const names = new Map((treatment.items || []).map((item) => [Number(item.madv), item.tendv]));
            const itemRows = (treatment.items || []).map((item) => { const percent = item.total_sessions ? Math.min(100, Number(item.consumed || 0) / Number(item.total_sessions) * 100) : 0; return `<tr><td>${escapeHtml(item.tendv)}</td><td>${item.total_sessions}</td><td>${item.consumed}</td><td>${item.reserved}</td><td>${item.available_sessions}</td><td><div class="treatment-progress-bar"><span style="width:${percent}%"></span></div></td></tr>`; }).join('');
            const historyRows = (treatment.history || []).map((entry) => `<tr><td>#${entry.malh}</td><td>${escapeHtml(names.get(Number(entry.madv)) || `Dịch vụ #${entry.madv}`)}</td><td>${escapeHtml({ reserved: 'Đã giữ buổi', consumed: 'Đã sử dụng', released: 'Đã hoàn buổi' }[entry.state] || entry.state)}</td><td>${formatDate(entry.consumed_at || entry.released_at || entry.reserved_at)}</td></tr>`).join('');
            content.innerHTML = `<div class="treatment-detail-header"><p class="package-eyebrow">Liệu trình #${treatment.mathe}</p><h2 id="treatmentDetailTitle">${escapeHtml(treatment.tengoi)}</h2><p><strong>${escapeHtml(treatment.customer_name)}</strong> · ${escapeHtml(treatment.phone)}</p><div class="package-detail-meta"><span>Ngày mua: ${formatDate(treatment.purchased_at)}</span><span>Kích hoạt: ${formatDate(treatment.activated_at)}</span><span>Hạn dùng: ${formatDate(treatment.expires_at)}</span>${statusBadge(treatment.status)}</div></div><div class="package-table-wrap treatment-history"><h3>Tiến độ dịch vụ</h3><table class="package-table"><thead><tr><th>Dịch vụ</th><th>Tổng buổi</th><th>Đã dùng</th><th>Đang giữ</th><th>Còn khả dụng</th><th>Tiến độ</th></tr></thead><tbody>${itemRows || '<tr><td colspan="6">Chưa có dịch vụ.</td></tr>'}</tbody></table></div><div class="package-table-wrap treatment-history"><h3>Lịch sử sử dụng</h3><table class="package-table"><thead><tr><th>Lịch hẹn</th><th>Dịch vụ</th><th>Trạng thái</th><th>Ngày</th></tr></thead><tbody>${historyRows || '<tr><td colspan="4" class="package-empty">Chưa có lịch sử sử dụng.</td></tr>'}</tbody></table></div>`;
        } catch (error) {
            content.innerHTML = `<div class="package-empty">${escapeHtml(error.message)}</div>`;
        }
    }

    async function initForm() {
        const form = document.getElementById('packageForm');
        const mode = root.dataset.formMode;
        const packageId = root.dataset.packageId;
        try {
            const listRequest = api('/api/admin/packages');
            const detailRequest = mode === 'edit' ? api(`/api/admin/packages/${packageId}`) : Promise.resolve(null);
            const [listResult, detailResult] = await Promise.all([listRequest, detailRequest]);
            services = listResult.services || [];
            if (!services.length) showMessage('Cần có ít nhất một dịch vụ đang hoạt động trước khi tạo gói.', 'error');
            if (detailResult) populateForm(detailResult.package);
            else addItem();
        } catch (error) {
            showMessage(error.message, 'error');
        }

        document.getElementById('addPackageItem').addEventListener('click', () => addItem());
        form.addEventListener('input', refreshSummary);
        form.addEventListener('change', refreshSummary);
        form.elements.unlimited.addEventListener('change', syncUnlimited);
        document.getElementById('packageImage').addEventListener('change', previewImage);
        form.addEventListener('submit', submitForm);

        function populateForm(pkg) {
            form.elements.tengoi.value = pkg.tengoi || '';
            form.elements.giagoi.value = Number(pkg.giagoi) || '';
            form.elements.mota.value = pkg.mota || '';
            form.elements.validity_months.value = pkg.validity_months || 6;
            form.elements.unlimited.checked = pkg.validity_months == null;
            form.elements.active.checked = Boolean(pkg.active);
            // Load post_care_instructions neu co
            const postCareEl = document.getElementById('packagePostCare');
            if (postCareEl) postCareEl.value = pkg.post_care_instructions || '';
            document.getElementById('packageImagePreview').src = pkg.image_url || fallbackImage;
            (pkg.items || []).forEach((item) => addItem(item.madv, item.total_sessions));
            if (!(pkg.items || []).length) addItem();
            syncUnlimited();
            refreshSummary();
        }

        function addItem(serviceId = '', sessions = 1) {
            const container = document.getElementById('packageItems');
            const row = document.createElement('div');
            row.className = 'package-item';
            const options = services.map((service) => `<option value="${service.madv}" data-price="${escapeHtml(service.gia)}" ${Number(serviceId) === Number(service.madv) ? 'selected' : ''}>${escapeHtml(service.tendv)}</option>`).join('');
            row.innerHTML = `<select class="package-item-service" required aria-label="Dịch vụ"><option value="">Chọn dịch vụ</option>${options}</select><input class="package-item-sessions" type="number" min="1" max="10000" step="1" value="${Number(sessions) || 1}" required aria-label="Số buổi"><span class="package-item-unit">0 ₫</span><span class="package-item-total">0 ₫</span><button class="package-item-remove" type="button" aria-label="Xóa dịch vụ"><i class="fas fa-trash"></i></button>`;
            row.querySelector('.package-item-remove').addEventListener('click', () => { row.remove(); refreshSummary(); });
            container.appendChild(row);
            refreshSummary();
        }

        function syncUnlimited() {
            const field = form.elements.validity_months;
            field.disabled = form.elements.unlimited.checked;
            field.required = !form.elements.unlimited.checked;
        }

        function previewImage(event) {
            const file = event.target.files[0];
            if (!file) return;
            if (file.size > 5 * 1024 * 1024) {
                event.target.value = '';
                showMessage('Ảnh gói không được lớn hơn 5 MB.', 'error');
                return;
            }
            if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
                event.target.value = '';
                showMessage('Ảnh gói phải có định dạng JPG, PNG hoặc WEBP.', 'error');
                return;
            }
            const reader = new FileReader();
            reader.onload = () => { document.getElementById('packageImagePreview').src = reader.result; };
            reader.readAsDataURL(file);
        }

        function refreshSummary() {
            let retail = 0;
            document.querySelectorAll('.package-item').forEach((row) => {
                const selected = row.querySelector('option:checked');
                const unit = Number(selected?.dataset.price || 0);
                const count = Number(row.querySelector('.package-item-sessions').value || 0);
                row.querySelector('.package-item-unit').textContent = money(unit);
                row.querySelector('.package-item-total').textContent = money(unit * count);
                retail += unit * count;
            });
            const price = Number(form.elements.giagoi.value || 0);
            document.getElementById('summaryRetail').textContent = money(retail);
            document.getElementById('summaryPackagePrice').textContent = money(price);
            document.getElementById('summarySavings').textContent = money(Math.max(0, retail - price));
            const warning = document.getElementById('packagePriceWarning');
            warning.hidden = !(price > retail && retail > 0);
            warning.textContent = 'Giá gói đang cao hơn tổng giá lẻ của các dịch vụ. Vui lòng kiểm tra lại.';
        }

        async function submitForm(event) {
            event.preventDefault();
            syncUnlimited();
            if (!form.reportValidity()) return;
            const itemRows = [...document.querySelectorAll('.package-item')];
            if (!itemRows.length) return showMessage('Gói phải có ít nhất một dịch vụ.', 'error');
            const items = itemRows.map((row) => ({
                madv: Number(row.querySelector('.package-item-service').value),
                total_sessions: Number(row.querySelector('.package-item-sessions').value)
            }));
            if (items.some((item) => !item.madv || !Number.isInteger(item.total_sessions) || item.total_sessions < 1)) return showMessage('Vui lòng chọn dịch vụ và nhập số buổi hợp lệ.', 'error');
            if (new Set(items.map((item) => item.madv)).size !== items.length) return showMessage('Một dịch vụ không thể xuất hiện nhiều lần trong cùng gói.', 'error');
            const postCareEl = document.getElementById('packagePostCare');
            const payload = {
                tengoi: form.elements.tengoi.value.trim(),
                giagoi: Number(form.elements.giagoi.value),
                mota: form.elements.mota.value.trim(),
                validity_months: form.elements.unlimited.checked ? null : Number(form.elements.validity_months.value),
                active: form.elements.active.checked,
                post_care_instructions: postCareEl ? postCareEl.value.trim() : '',
                items
            };
            const body = new FormData();
            body.append('data', JSON.stringify(payload));
            const image = document.getElementById('packageImage').files[0];
            if (image) body.append('anhgoi', image);
            const button = document.getElementById('savePackage');
            button.disabled = true;
            try {
                await api(mode === 'edit' ? `/api/admin/packages/${packageId}` : '/api/admin/packages', { method: mode === 'edit' ? 'PUT' : 'POST', body });
                sessionStorage.setItem('admin_package_notice', mode === 'edit' ? 'Cập nhật gói dịch vụ thành công.' : 'Tạo gói dịch vụ thành công.');
                window.location.href = '/admin/packages';
            } catch (error) {
                showMessage(error.message, 'error');
                button.disabled = false;
            }
        }
    }

    async function initDetail() {
        const id = root.dataset.packageId;
        const shell = document.getElementById('packageDetail');
        try {
            const { package: pkg } = await api(`/api/admin/packages/${id}`);
            const postCareSection = pkg.post_care_instructions
                ? `<section class="package-detail-card"><h3>&#128204; D&#7863;n d&#242; li&#7879;u tr&#236;nh</h3><p style="white-space:pre-wrap;">${escapeHtml(pkg.post_care_instructions)}</p></section>`
                : '';
            shell.innerHTML = `<section class="package-detail-card package-detail-hero"><img class="package-detail-image" src="${escapeHtml(pkg.image_url || fallbackImage)}" alt="${escapeHtml(pkg.tengoi)}"><div><p class="package-eyebrow">G&oacute;i d&#7883;ch v&#7909; #${pkg.magoi}</p><h2>${escapeHtml(pkg.tengoi)}</h2><div class="package-detail-meta"><span class="package-price">${money(pkg.giagoi)}</span><span>${packageValidity(pkg.validity_months)}</span><span class="package-status ${pkg.active ? 'active' : 'inactive'}">${pkg.active ? '&#272;ang b&aacute;n' : 'Ng&#432;ng b&aacute;n'}</span></div></div><div class="package-actions"><a class="btn btn-secondary" href="/admin/packages">Quay l&#7841;i</a><a class="btn btn-primary" href="/admin/packages/${pkg.magoi}/edit"><i class="fas fa-edit"></i> Ch&#7881;nh s&#7917;a</a></div></section><section class="package-detail-card"><h3>M&ocirc; t&#7843;</h3><p>${escapeHtml(pkg.mota || 'Ch&#432;a c&oacute; m&ocirc; t&#7843;.')}</p></section>${postCareSection}<section class="package-detail-card"><h3>D&#7883;ch v&#7909; trong g&oacute;i</h3><div class="package-detail-services">${(pkg.items || []).map((item) => `<div class="package-detail-service"><strong>${escapeHtml(item.tendv)}</strong><span>${item.total_sessions} bu&#7893;i &times; ${money(item.regular_unit_price_snapshot)}</span><span>${money(Number(item.regular_unit_price_snapshot) * item.total_sessions)}</span></div>`).join('') || '<p>Ch&#432;a c&oacute; d&#7883;ch v&#7909;.</p>'}</div></section><section class="package-detail-card"><h3>T&#7893;ng quan gi&aacute;</h3><div class="package-detail-meta"><span>Gi&aacute; l&#7867;: <strong>${money(pkg.regular_total)}</strong></span><span>Gi&aacute; g&oacute;i: <strong>${money(pkg.giagoi)}</strong></span><span>Ti&#7871;t ki&#7879;m: <strong>${money(Math.max(0, Number(pkg.savings)))}</strong></span></div></section>`;
        } catch (error) {
            shell.innerHTML = `<div class="package-detail-card package-empty">${escapeHtml(error.message)}<br><br><a class="btn btn-secondary" href="/admin/packages">Quay l&#7841;i danh s&aacute;ch</a></div>`;
        }
    }

    if (page === 'list') initList();
    else if (page === 'form') initForm();
    else if (page === 'detail') initDetail();
})();
