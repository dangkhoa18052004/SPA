/* Trợ lý AI đặt lịch (Gemini) cho trang khách.
   - Ẩn hoàn toàn nếu server chưa cấu hình AI (/api/ai/status).
   - AI chỉ tạo BẢN NHÁP; lịch hẹn chỉ được tạo khi khách bấm "Xác nhận đặt lịch".
   - Lịch sử hội thoại chỉ giữ trong tab hiện tại (sessionStorage), tối đa 10 lượt gửi lên server. */
(() => {
    'use strict';
    const KEY = 'binspa.ai.history';
    const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const money = v => new Intl.NumberFormat('vi-VN').format(Number(v) || 0) + 'đ';
    // Markdown tối giản và an toàn: escape trước, rồi **đậm** và gạch đầu dòng.
    const format = text => esc(text)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\s*[*-]\s+(.*)$/gm, '<span class="ai-bullet">• $1</span>')
        .replace(/\n/g, '<br>');
    const store = {
        load() { try { return JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { return []; } },
        save(items) { try { sessionStorage.setItem(KEY, JSON.stringify(items.slice(-20))); } catch (e) { /* bỏ qua */ } },
    };
    let history = store.load();
    let busy = false;

    function token() {
        return window.CustomerAuth ? window.CustomerAuth.getAccessToken() : localStorage.getItem('access_token');
    }

    async function post(url, body, auth) {
        const headers = { 'Content-Type': 'application/json' };
        const t = token();
        if (t) headers.Authorization = `Bearer ${t}`;
        const options = { method: 'POST', headers, body: JSON.stringify(body) };
        const response = auth && window.CustomerAuth ? await window.CustomerAuth.fetch(url, options) : await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.success === false) {
            const error = new Error(data.msg || data.message || 'Có lỗi xảy ra, vui lòng thử lại.');
            error.status = response.status;
            throw error;
        }
        return data;
    }

    function build() {
        const root = document.createElement('div');
        root.className = 'ai-widget';
        root.innerHTML = `
            <button type="button" class="ai-fab" aria-expanded="false" aria-controls="aiPanel" aria-label="Mở trợ lý AI đặt lịch">
                <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i><span>Trợ lý AI</span></button>
            <section class="ai-panel" id="aiPanel" role="dialog" aria-label="Trợ lý AI đặt lịch" hidden>
                <header class="ai-head"><div><strong>Trợ lý đặt lịch AI</strong><small>Tư vấn dịch vụ & đặt lịch Bin Spa</small></div>
                    <button type="button" class="ai-icon-btn" data-reset title="Cuộc trò chuyện mới" aria-label="Cuộc trò chuyện mới"><i class="fas fa-rotate-right" aria-hidden="true"></i></button>
                    <button type="button" class="ai-icon-btn" data-close aria-label="Đóng trợ lý"><i class="fas fa-xmark" aria-hidden="true"></i></button></header>
                <div class="ai-log" data-log aria-live="polite"></div>
                <div class="ai-quick" data-quick>
                    <button type="button">Spa có dịch vụ chăm sóc da nào?</button>
                    <button type="button">Đặt massage chiều mai</button>
                    <button type="button">Giá gội đầu dưỡng sinh?</button>
                </div>
                <form class="ai-input" data-form>
                    <input type="text" maxlength="1000" placeholder="Hỏi về dịch vụ hoặc đặt lịch..." aria-label="Tin nhắn cho trợ lý AI" required>
                    <button type="submit" aria-label="Gửi"><i class="fas fa-paper-plane" aria-hidden="true"></i></button>
                </form>
                <p class="ai-note">AI có thể nhầm lẫn. Giá và giờ trống lấy từ hệ thống; lịch chỉ được đặt khi bạn bấm xác nhận.</p>
            </section>`;
        document.body.appendChild(root);
        return root;
    }

    function message(log, role, html) {
        const el = document.createElement('div');
        el.className = `ai-msg ai-${role}`;
        el.innerHTML = html;
        log.appendChild(el);
        log.scrollTop = log.scrollHeight;
        return el;
    }

    function draftCard(log, draft) {
        const card = message(log, 'model', `
            <div class="ai-draft">
                <p class="ai-draft-title"><i class="fas fa-calendar-check" aria-hidden="true"></i> Bản nháp đặt lịch (chưa đặt)</p>
                <ul>${draft.dich_vu.map(s => `<li><span>${esc(s.tendv)}</span><span>${money(s.gia_vnd)}</span></li>`).join('')}</ul>
                <p>🕒 ${esc(draft.ngaygio.replace('T', ' '))} → ${esc(draft.ket_thuc)} · ${esc(draft.ky_thuat_vien)}</p>
                <p class="ai-draft-total">Tổng: <strong>${money(draft.tong_tien_vnd)}</strong></p>
                <div class="ai-draft-actions">
                    <button type="button" class="ai-btn ai-btn-primary" data-confirm>Xác nhận đặt lịch</button>
                    <button type="button" class="ai-btn" data-dismiss>Không đặt</button>
                </div>
                <p class="ai-draft-status" role="status"></p>
            </div>`);
        const confirm = card.querySelector('[data-confirm]');
        const status = card.querySelector('.ai-draft-status');
        confirm.onclick = async () => {
            confirm.disabled = true;
            status.textContent = 'Đang đặt lịch...';
            try {
                const data = await post('/api/ai/booking/confirm', { draft_id: draft.draft_id }, true);
                const malh = data.draft?.malh || data.appointment?.malh;
                status.innerHTML = `✅ ${esc(data.msg)} Mã lịch #${esc(malh)}. <a href="/profile#appointments">Xem lịch hẹn</a>`;
                card.querySelector('[data-dismiss]').remove();
                confirm.remove();
            } catch (error) {
                status.textContent = error.message;
                confirm.disabled = error.status === 410 || error.status === 403;
            }
        };
        card.querySelector('[data-dismiss]').onclick = () => {
            card.querySelector('.ai-draft-actions').remove();
            status.textContent = 'Đã bỏ bản nháp. Bạn có thể nhờ trợ lý chọn giờ khác.';
        };
    }

    function init(status) {
        const root = build();
        const fab = root.querySelector('.ai-fab');
        const panel = root.querySelector('.ai-panel');
        const log = root.querySelector('[data-log]');
        const form = root.querySelector('[data-form]');
        const input = form.querySelector('input');

        const greet = () => {
            log.innerHTML = '';
            message(log, 'model', 'Xin chào! Mình là trợ lý AI của Bin Spa. Mình có thể tư vấn dịch vụ, báo giá và giúp bạn đặt lịch. Bạn cần gì ạ?');
            history.forEach(h => message(log, h.role, h.role === 'user' ? esc(h.text) : format(h.text)));
        };
        const toggle = open => {
            panel.hidden = !open;
            fab.setAttribute('aria-expanded', String(open));
            root.classList.toggle('is-open', open);
            if (open) input.focus();
        };
        fab.onclick = () => toggle(panel.hidden);
        root.querySelector('[data-close]').onclick = () => toggle(false);
        root.querySelector('[data-reset]').onclick = () => { history = []; store.save(history); greet(); };
        document.addEventListener('keydown', e => { if (e.key === 'Escape' && !panel.hidden) toggle(false); });
        root.querySelectorAll('[data-quick] button').forEach(b => b.onclick = () => send(b.textContent));

        async function send(text) {
            text = String(text || '').trim();
            if (!text || busy) return;
            busy = true;
            input.value = '';
            message(log, 'user', esc(text));
            const typing = message(log, 'model', '<span class="ai-typing"><i></i><i></i><i></i></span>');
            try {
                const data = await post('/api/ai/chat', { message: text, history: history.slice(-10) });
                typing.innerHTML = format(data.reply);
                history.push({ role: 'user', text }, { role: 'model', text: data.reply });
                store.save(history);
                if (data.draft) {
                    if (!token()) message(log, 'model', 'Vui lòng <a href="/auth/login">đăng nhập</a> để xác nhận đặt lịch.');
                    else draftCard(log, data.draft);
                }
            } catch (error) {
                typing.innerHTML = `<span class="ai-error">${esc(error.message)}</span>`;
            } finally {
                busy = false;
                log.scrollTop = log.scrollHeight;
            }
        }
        form.onsubmit = e => { e.preventDefault(); send(input.value); };
        greet();
    }

    document.addEventListener('DOMContentLoaded', async () => {
        try {
            const status = await (await fetch('/api/ai/status')).json();
            if (status.configured) init(status);
        } catch (e) { /* AI tùy chọn: lỗi thì không hiện widget */ }
    });
})();
