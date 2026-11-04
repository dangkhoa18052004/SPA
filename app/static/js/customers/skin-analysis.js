// Soi da bằng AI: chụp/chọn ảnh -> /api/me/skin-analyses -> điểm nổi bật trên ảnh, chi tiết sắp theo độ tin cậy,
// dịch vụ gợi ý (Gemini, sau khi khách đồng ý), lịch sử, xóa. Hàm thuần nằm ở skin-analysis-view.js.
(function () {
    const API = '/api/me/skin-analyses';
    const MAX_SIDE = 3000;      // thu nhỏ trước khi gửi (giới hạn upload 5 MB), vẫn đủ chi tiết cho AI
    const View = window.SkinAnalysisView;
    const detailId = Number(document.querySelector('.skin-page').dataset.analysisId) || null;
    const esc = View.escapeHtml;
    const $ = (id) => document.getElementById(id);
    const els = {
        capture: $('skinCapture'), form: $('skinForm'), file: $('skinFile'), consent: $('skinConsent'),
        submit: $('skinSubmit'), status: $('skinStatus'), preview: $('skinPreview'), dropText: $('skinDropText'),
        dropIcon: $('skinDropIcon'), result: $('skinResult'), banner: $('skinBanner'), body: $('skinResultBody'),
        again: $('skinAgain'), figure: $('skinFigure'), image: $('skinImage'), boxes: $('skinBoxes'),
        coverage: $('skinCoverage'), highlights: $('skinHighlights'), detailLink: $('skinDetailLink'),
        detail: $('skinDetail'), showAll: $('skinShowAll'), table: $('skinTable'), pageInfo: $('skinPageInfo'),
        more: $('skinMore'), recs: $('skinRecs'), recsBody: $('skinRecsBody'), history: $('skinHistory'),
        empty: $('skinEmpty'), historyToggle: $('skinHistoryToggle'), historyPanel: $('skinHistoryPanel'),
    };
    // Màu khung theo loại mụn, luôn kèm tên loại bằng chữ; nét đứt = độ tin cậy thấp hoặc chưa xác định loại.
    const COLORS = {
        closed_comedo: '#e8a33d', open_comedo: '#6b4f3a', papule: '#d64545', pustule: '#c03fbf', nodule: '#3274a1',
    };
    const UNKNOWN = '#ffffff';
    const motion = () => (window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');
    const pct = (p) => `${Math.round(p * 100)}%`;
    const price = (v) => `${Math.round(Number(v) || 0).toLocaleString('vi-VN')}đ`;
    const swatch = (type) => `<i class="sw${type ? '' : ' sw-unknown'}" style="border-color:${COLORS[type] || '#8a8f8c'}"></i>`;

    let current = null;         // kết quả đang xem
    let view = null;            // {showAll, selectedId, shown, expanded}
    let blobUrl = null;
    let viewSeq = 0;            // lần mở/phân tích mới nhất; phản hồi cũ hơn bị bỏ qua
    let recController = null;
    let recConsent = false;     // khách đã đồng ý gửi kết quả dẫn xuất tới Gemini trong lần mở trang này
    const REC_SNAPSHOT_KEY = 'skin-analysis-recommendation:v1';
    const REC_SNAPSHOT_TTL = 30 * 60 * 1000;

    function recommendationOwner() {
        try {
            const token = window.CustomerAuth?.getAccessToken();
            const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
            const subject = JSON.parse(atob(payload)).sub;
            return /^customer:\d+$/.test(subject) ? subject : null;
        } catch (_) { return null; }
    }

    function rememberRecommendations(data) {
        // Only a short-lived, tab-local display snapshot; never store the photo or an access token.
        const owner = recommendationOwner();
        if (!owner || data.status === 'consent_required') return;
        try {
            sessionStorage.setItem(REC_SNAPSHOT_KEY, JSON.stringify({ owner,
                consentVersion: els.recs.dataset.consentVersion,
                expires: Date.now() + REC_SNAPSHOT_TTL, data }));
        } catch (_) { /* Storage may be disabled; the normal authorized request still works. */ }
    }

    function restoredRecommendations(id) {
        try {
            const snapshot = JSON.parse(sessionStorage.getItem(REC_SNAPSHOT_KEY));
            if (!snapshot || !recommendationOwner() || snapshot.owner !== recommendationOwner()
                || snapshot.consentVersion !== els.recs.dataset.consentVersion
                || !Number.isFinite(snapshot.expires) || snapshot.expires <= Date.now()
                || snapshot.data?.analysis_id !== id
                || !['ok', 'no_matching_services', 'insufficient_evidence'].includes(snapshot.data.status)
                || !Array.isArray(snapshot.data.recommendations)) return null;
            // Called only after the result API has authorized this customer's analysis.
            return snapshot.data;
        } catch (_) { return null; }
    }

    function forgetRecommendations(id) {
        try {
            const snapshot = JSON.parse(sessionStorage.getItem(REC_SNAPSHOT_KEY));
            if (snapshot?.data?.analysis_id === id) sessionStorage.removeItem(REC_SNAPSHOT_KEY);
        } catch (_) { /* No snapshot to remove. */ }
    }

    function authFetch(url, options) {
        return window.CustomerAuth ? window.CustomerAuth.fetch(url, options) : fetch(url, options);
    }

    function setStatus(text, isError) {
        els.status.textContent = text || '';
        els.status.classList.toggle('is-error', !!isError);
    }

    function updateSubmit() {
        els.submit.disabled = !(els.file.files.length && els.consent.checked);
    }

    async function shrink(file) {
        // createImageBitmap áp dụng hướng xoay EXIF của ảnh điện thoại.
        const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
        const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(bitmap.width * scale);
        canvas.height = Math.round(bitmap.height * scale);
        canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();
        return new Promise((resolve, reject) =>
            canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('encode'))), 'image/jpeg', 0.92));
    }

    function formatDate(iso) {
        return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' });
    }

    function setBlob(url) {
        if (blobUrl && blobUrl !== url) URL.revokeObjectURL(blobUrl);
        blobUrl = url || null;
    }

    // ---- Ảnh và điểm nổi bật ----

    function drawBoxes() {
        const size = Array.isArray(current.image_size) ? current.image_size : [];
        const w = size[0] || els.image.naturalWidth, h = size[1] || els.image.naturalHeight;
        if (!w || !h) return;
        els.boxes.setAttribute('viewBox', `0 0 ${w} ${h}`);
        const stroke = Math.max(2, Math.round(Math.max(w, h) / 400));
        const font = Math.max(14, Math.round(Math.max(w, h) / 50));
        const points = View.visiblePoints(current, view);
        els.boxes.classList.toggle('has-selection', points.some((l) => l.id === view.selectedId));
        els.boxes.innerHTML = points.map((l) => {
            const [x1, y1, x2, y2] = l.bbox;
            const pad = Math.max(4, (x2 - x1) * 0.25);
            const color = COLORS[l.type] || UNKNOWN;
            const dash = !l.type || l.low_confidence ? ` stroke-dasharray="${stroke * 3} ${stroke * 2}"` : '';
            const cls = l.id === view.selectedId ? ' class="is-selected"' : '';
            return `<g${cls}><rect x="${x1 - pad}" y="${y1 - pad}" width="${x2 - x1 + 2 * pad}" height="${y2 - y1 + 2 * pad}" `
                + `rx="${pad}" stroke="${color}" stroke-width="${stroke}"${dash}><title>${l.id}. ${esc(l.label)}</title></rect>`
                + `<text x="${x1 - pad}" y="${y1 - pad - stroke}" fill="${color}" font-size="${font}">${l.id}</text></g>`;
        }).join('');
        const total = current.lesions.length;
        const hidden = total - points.length;
        els.coverage.textContent = total
            ? `Đang hiển thị ${points.length} / ${total} điểm.${hidden > 0 ? ' Các điểm khác được thu gọn.' : ''}`
            : '';
    }

    function renderHighlights() {
        const total = current.lesions.length;
        const items = View.topPoints(current.lesions);
        if (!total) {
            els.highlights.innerHTML = '<p class="skin-empty-state">Chưa phát hiện điểm trong ảnh này. '
                + 'Kết quả này không khẳng định da bạn không có mụn.</p>';
        } else {
            els.highlights.innerHTML = '<ol class="skin-types">' + items.map((l) => {
                const score = View.isProbability(l.probability) ? pct(l.probability) : 'Chưa có';
                return `<li><button type="button" class="skin-type" data-select="${l.id}" aria-pressed="${view.selectedId === l.id}" ${l.bbox ? '' : 'disabled'}>
                    <span class="skin-type-name">${swatch(l.type)}Điểm ${l.id} · ${esc(l.label)}</span>
                    <span class="skin-type-meta">Độ tin cậy của AI: <strong>${score}</strong>${l.low_confidence ? ' · Độ tin cậy thấp' : ''}</span>
                </button></li>`;
            }).join('') + '</ol>'
                + '<p class="skin-hint">Chọn một điểm để làm nổi bật vị trí trên ảnh.</p>';
        }
        els.detailLink.hidden = !!detailId || !total || !current.id;
        if (current.id) els.detailLink.href = `/skin-analysis/${Number(current.id)}`;
        els.detailLink.textContent = `Xem chi tiết toàn bộ ${total} điểm`;
    }

    // ---- Chi tiết ----

    function renderDetail() {
        const total = current.lesions.length;
        els.detail.hidden = !view.expanded;
        els.showAll.checked = view.showAll;
        if (!view.expanded) return;
        const rows = View.sortDetail(current.lesions).slice(0, view.shown);
        els.table.innerHTML = rows.map((l) => {
            const prob = View.isProbability(l.probability) ? pct(l.probability) : 'Chưa có';
            const alts = (l.alternatives || []).map((o) => `${esc(o.label)} ${pct(o.probability)}`).join(', ') || '–';
            const badge = l.low_confidence ? ' <span class="skin-badge">Độ tin cậy thấp</span>' : '';
            const selected = l.id === view.selectedId;
            const point = l.bbox
                ? `<button type="button" class="skin-point" data-select="${l.id}" aria-pressed="${selected}" `
                    + `aria-label="Làm nổi bật điểm ${l.id} trên ảnh">${swatch(l.type)}${l.id}</button>`
                : `<span class="skin-point is-static">${swatch(l.type)}${l.id}</span>`;
            return `<tr class="${l.reliable ? '' : 'is-low'}${selected ? ' is-selected' : ''}">
                <td data-label="Điểm">${point}</td>
                <td data-label="Loại">${esc(l.label)}${badge}${l.bbox ? '' : ' <small>(không có vị trí hợp lệ)</small>'}</td>
                <td data-label="Độ tin cậy của AI">${prob}</td>
                <td data-label="Khả năng khác">${alts}</td>
            </tr>`;
        }).join('');
        els.pageInfo.textContent = `Đang xem ${rows.length} / ${total} điểm`;
        els.more.hidden = rows.length >= total;
    }

    function render() {
        renderHighlights();
        drawBoxes();
        renderDetail();
    }

    function showResult(data, imageSrc) {
        current = data;
        view = { showAll: !!detailId, selectedId: null, shown: detailId ? data.lesions.length : View.PAGE_SIZE, expanded: !!detailId };
        els.result.hidden = false;
        const banner = {
            location_only: ['is-warn', data.message || 'Chỉ xác định được vị trí, chưa đủ độ tin cậy về loại mụn.'],
            retake_photo: ['is-error', 'Ảnh chưa đạt để phân tích, vui lòng chụp lại.'],
        }[data.status] || (['ok', 'demo'].includes(data.status) ? null : ['is-error', 'Không có kết quả.']);
        els.banner.hidden = !banner;
        if (banner) {
            const extra = data.reasons || [];
            els.banner.className = `skin-banner ${banner[0]}`;
            els.banner.innerHTML = `<strong>${esc(banner[1])}</strong>`
                + (extra.length ? `<ul>${extra.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : '');
        }
        hideRecommendations();
        if (data.status === 'retake_photo') {
            els.body.hidden = true;
            setBlob(imageSrc);
            els.result.scrollIntoView({ behavior: motion(), block: 'start' });
            return;
        }
        els.body.hidden = false;
        setBlob(imageSrc);
        els.image.onload = () => { if (current === data) drawBoxes(); };
        els.image.src = imageSrc || '';
        els.figure.hidden = !imageSrc;
        render();
        els.result.scrollIntoView({ behavior: motion(), block: 'start' });
        if (data.id && !detailId) {
            // Back must reopen this saved result even if the browser reloads instead of using its page cache.
            const url = new URL(location.href);
            url.searchParams.set('analysis', String(data.id));
            history.replaceState(history.state, '', url.pathname + url.search + url.hash);
            loadRecommendations(data.id);
        }
    }

    function selectPoint(id) {
        view.selectedId = view.selectedId === id ? null : id;
        render();
        const rect = els.figure.getBoundingClientRect();
        if (view.selectedId && (rect.bottom < 80 || rect.top > window.innerHeight)) {
            els.figure.scrollIntoView({ behavior: motion(), block: 'nearest' });
        }
    }

    els.highlights.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-select]');
        if (!btn || !current) return;
        selectPoint(Number(btn.dataset.select));
    });
    els.showAll.addEventListener('change', () => { view.showAll = els.showAll.checked; render(); });
    els.more.addEventListener('click', () => { view.shown += View.PAGE_SIZE; renderDetail(); });
    els.table.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-select]');
        if (btn) selectPoint(Number(btn.dataset.select));
    });
    els.again.addEventListener('click', () => {
        els.capture.scrollIntoView({ behavior: motion(), block: 'start' });
        els.file.click();
    });

    // ---- Dịch vụ gợi ý ----

    function hideRecommendations() {
        if (recController) recController.abort();
        recController = null;
        if (els.recs) { els.recs.hidden = true; els.recsBody.innerHTML = ''; }
    }

    const FALLBACK_CTA = '<div class="skin-recs-actions">'
        + '<a class="skin-btn" href="/appointments/create">Đặt lịch tư vấn</a>'
        + '<a class="skin-btn skin-btn-ghost" href="/services">Xem tất cả dịch vụ</a></div>';

    function renderRecommendations(data) {
        if (data.status === 'consent_required') {
            els.recsBody.innerHTML = `<div class="skin-recs-consent">
                <p>Để gợi ý dịch vụ, Bin Spa sẽ gửi <strong>kết quả đã tổng hợp</strong> của lần phân tích này tới Google Gemini:
                tên nhóm mụn, số điểm và độ tin cậy của AI, cùng danh sách dịch vụ của spa. Không gửi ảnh, vị trí trên khuôn mặt,
                họ tên hay thông tin liên hệ của bạn.</p>
                <p>Nếu không đồng ý, bạn vẫn xem kết quả soi da như bình thường.</p>
                <div class="skin-recs-actions">
                    <button type="button" class="skin-btn" data-rec="accept">Đồng ý và xem gợi ý</button>
                    <button type="button" class="skin-btn skin-btn-ghost" data-rec="decline">Để sau</button>
                </div></div>`;
            return;
        }
        if (data.status !== 'ok' || !data.recommendations.length) {
            els.recsBody.innerHTML = `<p class="skin-recs-message">${esc(data.message || 'Chưa có dịch vụ phù hợp để gợi ý.')}</p>${FALLBACK_CTA}`;
            return;
        }
        els.recsBody.innerHTML = (data.demo ? '<p class="skin-recs-message">Dựa trên loại mụn '
                + 'AI phân loại ở chế độ thử nghiệm, chỉ để tham khảo. Hãy đặt lịch để chuyên viên tư vấn chính xác.</p>' : '')
            + (data.summary ? `<p class="skin-recs-message">${esc(data.summary)}</p>` : '')
            + '<ul class="skin-recs-list">' + data.recommendations.map((s) => `
                <li class="skin-rec">
                    <h3>${esc(s.tendv)}</h3>
                    <p class="skin-rec-meta">${price(s.gia)}${s.thoiluong ? ` · ${Number(s.thoiluong)} phút` : ''}${s.category_name ? ` · ${esc(s.category_name)}` : ''}</p>
                    <p class="skin-rec-tags">${s.matched_types.map((t) => `<span>${swatch(t.type)}${esc(t.label)}</span>`).join('')}</p>
                    <p class="skin-rec-reason">${esc(s.reason)}</p>
                    <div class="skin-recs-actions">
                        <a class="skin-btn skin-btn-ghost" href="/services/${Number(s.madv)}">Xem dịch vụ</a>
                        <a class="skin-btn" href="/appointments/create?service=${Number(s.madv)}">Đặt lịch</a>
                    </div>
                </li>`).join('') + '</ul>';
    }

    async function loadRecommendations(id) {
        if (!els.recs) return;
        if (recController) recController.abort();
        const controller = recController = new AbortController();
        els.recs.hidden = false;
        const restored = restoredRecommendations(id);
        if (restored) {
            renderRecommendations(restored);
            els.recs.setAttribute('aria-busy', 'false');
            return;
        }
        els.recs.setAttribute('aria-busy', 'true');
        els.recsBody.innerHTML = '<p class="skin-recs-message">Đang tìm dịch vụ phù hợp với kết quả này...</p>';
        const stale = () => controller !== recController || !current || current.id !== id;
        try {
            const res = await authFetch(`${API}/${id}/recommendations`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
                body: JSON.stringify({ consent: recConsent ? els.recs.dataset.consentVersion : null }),
            });
            const body = await res.json().catch(() => ({}));
            if (stale()) return;
            if (!res.ok || !body.data) throw new Error(body.message || 'Chưa lấy được gợi ý dịch vụ lúc này.');
            if (body.data.analysis_id !== id) return;
            rememberRecommendations(body.data);
            renderRecommendations(body.data);
        } catch (err) {
            if (err.name === 'AbortError' || stale()) return;
            els.recsBody.innerHTML = `<p class="skin-recs-message is-error">${esc(err.message)}</p>`
                + '<div class="skin-recs-actions"><button type="button" class="skin-btn skin-btn-ghost" data-rec="retry">Thử lại</button></div>';
        } finally {
            if (!stale()) els.recs.setAttribute('aria-busy', 'false');
        }
    }

    if (els.recs) {
        els.recsBody.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-rec]');
            if (!btn || !current || !current.id) return;
            const action = btn.dataset.rec;
            if (action === 'accept') recConsent = true;
            if (action === 'decline') {
                els.recsBody.innerHTML = '<p class="skin-recs-message">Bạn có thể đặt lịch để chuyên viên tư vấn trực tiếp, '
                    + 'hoặc xem gợi ý sau.</p>' + FALLBACK_CTA.replace('</div>',
                    '<button type="button" class="skin-btn skin-btn-ghost" data-rec="retry">Xem gợi ý</button></div>');
                return;
            }
            loadRecommendations(current.id);
        });
    }

    // ---- Mở, xóa, lịch sử ----

    async function loadImage(url) {
        const res = await authFetch(url);
        if (!res.ok) throw new Error('Không tải được ảnh.');
        return URL.createObjectURL(await res.blob());
    }

    async function openAnalysis(id) {
        const seq = ++viewSeq;
        setStatus('Đang mở kết quả...');
        try {
            const res = await authFetch(`${API}/${id}`);
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.message);
            const src = body.data.image_url ? await loadImage(body.data.image_url) : '';
            if (seq !== viewSeq) { if (src) URL.revokeObjectURL(src); return; }
            showResult(body.data, src);
            setStatus('');
        } catch (e) {
            if (seq === viewSeq) setStatus(e.message || 'Không mở được kết quả.', true);
        }
    }

    async function removeAnalysis(id) {
        if (!confirm('Xóa lần phân tích này và ảnh đi kèm? Không thể khôi phục.')) return;
        const res = await authFetch(`${API}/${id}`, { method: 'DELETE' });
        if (res.ok) {
            forgetRecommendations(id);
            if (current && current.id === id) {
                viewSeq++;
                hideRecommendations();
                current = null;
                els.result.hidden = true;
                els.image.removeAttribute('src');
                setBlob(null);
            }
            loadHistory();
        } else {
            setStatus('Không xóa được, vui lòng thử lại.', true);
        }
    }

    async function loadHistory() {
        const res = await authFetch(API);
        if (res.status === 401) return;
        const body = await res.json().catch(() => ({}));
        const items = (res.ok && body.data) || [];
        els.empty.hidden = items.length > 0;
        els.historyToggle.textContent = `${els.historyPanel.hidden ? 'Xem' : 'Ẩn'} lịch sử${items.length ? ` (${items.length})` : ''}`;
        const tags = { ok: ['is-ok', 'Đã phân loại'], demo: ['is-warn', 'Thử nghiệm'], location_only: ['is-warn', 'Chỉ vị trí'] };
        els.history.innerHTML = items.map((a) => {
            const tag = tags[a.status] || tags.location_only;
            return `<li>
                <div><strong>${formatDate(a.created_at)}</strong>
                    <span class="skin-tag ${tag[0]}">${tag[1]}</span>
                    <small>${Number(a.lesion_count) || 0} điểm</small></div>
                <div class="skin-history-actions">
                    <button type="button" class="skin-btn skin-btn-ghost" data-open="${Number(a.id)}">Xem</button>
                    <button type="button" class="skin-link is-danger" data-delete="${Number(a.id)}">Xóa</button>
                </div>
            </li>`;
        }).join('');
    }

    els.historyToggle.addEventListener('click', () => {
        const open = els.historyPanel.hidden;
        els.historyPanel.hidden = !open;
        els.historyToggle.setAttribute('aria-expanded', String(open));
        els.historyToggle.textContent = els.historyToggle.textContent.replace(open ? 'Xem' : 'Ẩn', open ? 'Ẩn' : 'Xem');
    });

    els.history.addEventListener('click', (e) => {
        const open = e.target.closest('[data-open]');
        const del = e.target.closest('[data-delete]');
        if (open) openAnalysis(Number(open.dataset.open));
        if (del) removeAnalysis(Number(del.dataset.delete));
    });

    // ---- Chụp và phân tích ----

    els.file.addEventListener('change', () => {
        const f = els.file.files[0];
        if (f) {
            if (els.preview.src) URL.revokeObjectURL(els.preview.src);
            els.preview.src = URL.createObjectURL(f);
            els.preview.hidden = false;
            els.dropIcon.hidden = true;
            els.dropText.textContent = 'Đổi ảnh khác';
        }
        updateSubmit();
    });
    els.consent.addEventListener('change', updateSubmit);

    els.form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (els.submit.disabled) return;
        const seq = ++viewSeq;
        els.submit.disabled = true;
        els.form.setAttribute('aria-busy', 'true');
        setStatus('Đang phân tích, thường mất vài giây...');
        try {
            const blob = await shrink(els.file.files[0]);
            const fd = new FormData();
            fd.append('image', blob, 'photo.jpg');
            fd.append('consent', els.consent.value);
            const res = await authFetch(API, { method: 'POST', body: fd });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.message || 'Không phân tích được ảnh.');
            const data = body.data;
            const src = data.image_url ? await loadImage(data.image_url) : '';
            if (data.saved) loadHistory();
            if (seq !== viewSeq) { if (src) URL.revokeObjectURL(src); return; }
            showResult(data, src);
            setStatus('');
        } catch (err) {
            if (seq === viewSeq) setStatus(err.message || 'Không phân tích được ảnh.', true);
        } finally {
            els.form.removeAttribute('aria-busy');
            updateSubmit();
        }
    });

    window.addEventListener('pagehide', (event) => {
        if (event.persisted) return;  // Keep object URLs usable when Back restores this document.
        setBlob(null);
        if (els.preview.src) URL.revokeObjectURL(els.preview.src);
    });

    window.addEventListener('pageshow', (event) => {
        if (!event.persisted || !current?.id) return;
        // A restored browser document must recheck access, including after an account change.
        els.result.hidden = true;
        hideRecommendations();
        recConsent = false;
        openAnalysis(current.id);
    });

    async function initialize() {
        const requested = detailId || Number(new URLSearchParams(location.search).get('analysis'));
        if (!detailId) loadHistory();
        if (Number.isSafeInteger(requested) && requested > 0) await openAnalysis(requested);
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (window.CustomerAuth && !window.CustomerAuth.getAccessToken()) {
            window.CustomerAuth.restoreAccessToken().then((token) => {
                if (!token) window.CustomerAuth.redirectToLogin('Vui lòng đăng nhập để dùng chức năng soi da.', location.pathname + location.search);
                else initialize();
            });
        } else {
            initialize();
        }
    });
})();
