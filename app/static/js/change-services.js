/* Hộp "Đổi dịch vụ" dùng chung cho hồ sơ khách và trang Lịch hẹn admin.
   - Tìm kiếm gõ tới đâu lọc tới đó (không phân biệt dấu/hoa thường, khớp mọi từ).
   - Thẻ dịch vụ có ảnh, thời lượng, giá; dịch vụ đang chọn luôn nằm trên cùng.
   - So sánh trước/sau: số tiền phải trả (trừ buổi gói/quà), thời lượng và giờ kết thúc dự kiến.
   ChangeServicesDialog.open({title, subtitle, services, current, packageOptions, startAt, submit}) */
(() => {
    const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    const money = value => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(Number(value) || 0);
    const fold = text => String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
    const image = s => s.image_url || (s.anhdichvu ? `data:image/jpeg;base64,${s.anhdichvu}` : '/static/images/default-service.jpg');
    const minutes = s => Number(s.thoiluong) > 0 ? Number(s.thoiluong) : 60;
    const clock = date => date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', hour12: false });

    function open({ title, subtitle = '', services, current, packageOptions = () => [], startAt, submit }) {
        document.getElementById('csDialog')?.remove();
        const byId = new Map(services.map(s => [Number(s.madv), s]));
        const selected = new Set(current.keys());
        const chosenPackage = new Map(); // madv -> "mathe:itemId" cho dịch vụ thêm mới
        const start = startAt ? new Date(startAt) : null;
        let query = '';

        const dialog = document.createElement('dialog');
        dialog.id = 'csDialog';
        dialog.className = 'cs-dialog';
        dialog.setAttribute('aria-labelledby', 'csTitle');
        dialog.innerHTML = `
            <header class="cs-header">
                <div><h2 id="csTitle">${esc(title)}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div>
                <button type="button" class="cs-close" data-close aria-label="Đóng">×</button>
            </header>
            <div class="cs-selected" data-selected aria-live="polite"></div>
            <label class="cs-search"><span class="cs-search-icon" aria-hidden="true">⌕</span>
                <input type="search" data-search placeholder="Tìm dịch vụ: tên, mô tả… (vd: da mun, massage)" autocomplete="off" aria-label="Tìm dịch vụ">
                <small data-count></small></label>
            <div class="cs-grid" data-grid role="list"></div>
            <footer class="cs-footer">
                <div class="cs-compare" data-compare></div>
                <p class="cs-message" data-message role="alert"></p>
                <div class="cs-actions"><button type="button" class="cs-btn cs-btn-ghost" data-close>Quay lại</button>
                    <button type="button" class="cs-btn cs-btn-primary" data-save disabled>Lưu thay đổi</button></div>
            </footer>`;
        document.body.appendChild(dialog);
        const $ = sel => dialog.querySelector(sel);
        dialog.querySelectorAll('[data-close]').forEach(b => b.onclick = () => dialog.close());
        dialog.addEventListener('close', () => dialog.remove());

        const beforeIds = [...current.keys()];
        const coveredBefore = madv => !!current.get(madv)?.package;
        const isCovered = madv => coveredBefore(madv) || chosenPackage.has(madv);
        // pay = số tiền phải trả tại spa (dịch vụ dùng buổi gói/quà không tính tiền).
        const totals = (ids, covered) => ids.reduce((acc, id) => {
            const s = byId.get(id); if (!s) return acc;
            acc.minutes += minutes(s);
            acc.list += Number(s.gia) || 0;
            if (!covered(id)) acc.pay += Number(s.gia) || 0;
            return acc;
        }, { minutes: 0, list: 0, pay: 0 });

        function renderSelected() {
            const ids = [...selected];
            $('[data-selected]').innerHTML = ids.length
                ? `<span class="cs-selected-label">Đã chọn ${ids.length}:</span>` + ids.map(id => {
                    const s = byId.get(id);
                    return `<button type="button" class="cs-chip ${current.has(id) ? '' : 'cs-chip-new'}" data-remove="${id}" aria-label="Bỏ ${esc(s?.tendv)}">${esc(s?.tendv || id)}${isCovered(id) ? ' · gói' : ''} <span aria-hidden="true">×</span></button>`;
                }).join('')
                : '<span class="cs-selected-label cs-warn">Chưa chọn dịch vụ nào</span>';
            dialog.querySelectorAll('[data-remove]').forEach(b => b.onclick = () => { toggle(Number(b.dataset.remove)); });
        }

        function renderGrid() {
            const tokens = fold(query).split(/\s+/).filter(Boolean);
            const match = s => !tokens.length || tokens.every(t => fold(`${s.tendv} ${s.mota || ''}`).includes(t));
            const list = services.filter(match).sort((a, b) =>
                Number(selected.has(Number(b.madv))) - Number(selected.has(Number(a.madv))) || String(a.tendv).localeCompare(String(b.tendv), 'vi'));
            $('[data-count]').textContent = tokens.length ? `${list.length} kết quả` : `${services.length} dịch vụ`;
            $('[data-grid]').innerHTML = list.length ? list.map(s => {
                const id = Number(s.madv), on = selected.has(id), mine = current.get(id);
                const options = mine ? [] : packageOptions(id);
                return `<div class="cs-card ${on ? 'is-on' : ''}" role="listitem">
                    <button type="button" class="cs-card-main" data-toggle="${id}" aria-pressed="${on}">
                        <img src="${esc(image(s))}" alt="" loading="lazy" onerror="this.onerror=null;this.src='/static/images/default-service.jpg'">
                        <span class="cs-card-body"><strong>${esc(s.tendv)}</strong>
                            <span class="cs-card-meta">${minutes(s)} phút · ${money(s.gia)}</span>
                            ${mine ? `<span class="cs-tag">${mine.package ? esc(mine.label || 'Đang dùng buổi gói') : 'Đang đặt'}</span>` : ''}
                            ${!mine && options.length ? '<span class="cs-tag cs-tag-pkg">Có buổi gói</span>' : ''}</span>
                        <span class="cs-check" aria-hidden="true">${on ? '✓' : '+'}</span>
                    </button>
                    ${on && options.length ? `<select class="cs-pay" data-pay="${id}" aria-label="Nguồn thanh toán cho ${esc(s.tendv)}">
                        <option value="">Thanh toán bình thường</option>
                        ${options.map(o => `<option value="${esc(o.value)}" ${chosenPackage.get(id) === o.value ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}
                    </select>` : ''}
                </div>`;
            }).join('') : `<p class="cs-empty">Không tìm thấy dịch vụ phù hợp với “${esc(query)}”.</p>`;
            dialog.querySelectorAll('[data-toggle]').forEach(b => b.onclick = () => toggle(Number(b.dataset.toggle)));
            dialog.querySelectorAll('[data-pay]').forEach(sel => sel.onchange = () => {
                const id = Number(sel.dataset.pay);
                sel.value ? chosenPackage.set(id, sel.value) : chosenPackage.delete(id);
                renderSelected(); renderCompare();
            });
        }

        function renderCompare() {
            const before = totals(beforeIds, coveredBefore), after = totals([...selected], isCovered);
            const diff = after.pay - before.pay;
            const end = m => start ? ` · xong khoảng ${clock(new Date(start.getTime() + m * 60000))}` : '';
            $('[data-compare]').innerHTML = `
                <div class="cs-col"><span>Trước</span><strong>${money(before.pay)}</strong><small>${before.minutes} phút${end(before.minutes)}</small></div>
                <div class="cs-arrow" aria-hidden="true">→</div>
                <div class="cs-col"><span>Sau</span><strong>${money(after.pay)}</strong><small>${after.minutes} phút${end(after.minutes)}</small></div>
                <div class="cs-diff ${diff > 0 ? 'up' : diff < 0 ? 'down' : ''}"><span>Chênh lệch</span><strong>${diff > 0 ? '+' : diff < 0 ? '−' : ''}${money(Math.abs(diff))}</strong>
                    <small>${after.list !== after.pay ? `Giá gốc ${money(after.list)}, buổi gói trừ ${money(after.list - after.pay)}` : 'Số tiền thanh toán tại spa'}</small></div>`;
            const ids = [...selected];
            const changed = ids.length !== current.size || ids.some(id => !current.has(id)) || chosenPackage.size > 0;
            $('[data-save]').disabled = !ids.length || !changed;
            $('[data-message]').textContent = ids.length ? '' : 'Cần giữ ít nhất một dịch vụ.';
        }

        function toggle(id) {
            if (selected.has(id)) { selected.delete(id); chosenPackage.delete(id); } else { selected.add(id); }
            renderSelected(); renderGrid(); renderCompare();
        }

        $('[data-search]').addEventListener('input', e => { query = e.target.value; renderGrid(); });
        $('[data-save]').onclick = async () => {
            const save = $('[data-save]');
            const madv_list = [...selected];
            const package_usages = [...chosenPackage].filter(([id]) => selected.has(id)).map(([madv, value]) => {
                const [mathe, item] = value.split(':').map(Number);
                return { mathe, the_item_id: item, madv, quantity: 1 };
            });
            save.disabled = true;
            $('[data-message]').textContent = 'Đang lưu...';
            try {
                await submit(madv_list, package_usages);
                dialog.close();
            } catch (error) {
                $('[data-message]').textContent = error.message || 'Không thể đổi dịch vụ';
                save.disabled = false;
            }
        };

        renderSelected(); renderGrid(); renderCompare();
        dialog.showModal();
        $('[data-search]').focus();
        return dialog;
    }

    window.ChangeServicesDialog = { open, fold };
})();
