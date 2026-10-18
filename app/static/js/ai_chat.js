/* Trợ lý AI đặt lịch (Gemini) cho trang khách.
   - Ẩn hoàn toàn nếu server chưa cấu hình AI (/api/ai/status).
   - AI chỉ tạo BẢN NHÁP; lịch hẹn chỉ được tạo khi khách bấm "Xác nhận đặt lịch".
   - Câu hỏi được xử lý nền; trang mới nối lại bằng mã yêu cầu, không gửi trùng cho AI.
   - Lịch sử trong sessionStorage được tách theo tài khoản/phiên khách. */
(() => {
    'use strict';
    const KEY = 'binspa.ai.history';
    let scopeKey = KEY;
    const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const money = v => new Intl.NumberFormat('vi-VN').format(Number(v) || 0) + 'đ';
    // Markdown tối giản và an toàn: escape trước, rồi **đậm** và gạch đầu dòng.
    const format = text => esc(text)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\s*[*-]\s+(.*)$/gm, '<span class="ai-bullet">• $1</span>')
        .replace(/\n/g, '<br>');
    const store = {
        load() { try { const items = JSON.parse(sessionStorage.getItem(scopeKey) || '[]'); return Array.isArray(items) ? items.filter(h => h && ['user', 'model'].includes(h.role) && typeof h.text === 'string').slice(-20) : []; } catch (e) { return []; } },
        save(items) { try { sessionStorage.setItem(scopeKey, JSON.stringify(items.slice(-20))); } catch (e) { /* bỏ qua */ } },
    };
    const readValue = key => { try { return sessionStorage.getItem(scopeKey + key); } catch { return null; } };
    const writeValue = (key, value) => { try { if (value === null) sessionStorage.removeItem(scopeKey + key); else sessionStorage.setItem(scopeKey + key, value); } catch { /* storage unavailable */ } };
    const readPending = () => { try { const p = JSON.parse(readValue('.pending') || 'null'); return p && typeof p.id === 'string' && /^[0-9a-f-]{36}$/.test(p.id) && typeof p.text === 'string' && Array.isArray(p.history) ? p : null; } catch { return null; } };
    const savePending = p => writeValue('.pending', p ? JSON.stringify(p) : null);
    let history = [];
    let busy = false;
    const newRequestId = () => {
        if (crypto.randomUUID) return crypto.randomUUID();
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
        const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    };

    function token() {
        return window.CustomerAuth ? window.CustomerAuth.getAccessToken() : localStorage.getItem('access_token');
    }

    async function post(url, body, auth, method = 'POST') {
        const headers = { 'Content-Type': 'application/json' };
        const t = token();
        if (t) headers.Authorization = `Bearer ${t}`;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), url.includes('/chat/jobs') ? 10000 : 45000);
        const options = { method, headers, ...(method === 'GET' ? {} : { body: JSON.stringify(body) }),
            ...(url === '/api/ai/chat/jobs' ? { keepalive: true } : {}), signal: controller.signal, credentials: 'same-origin' };
        let response, data;
        try {
            response = auth && window.CustomerAuth ? await window.CustomerAuth.fetch(url, options) : await fetch(url, options);
            data = await response.json();
            if (!data || typeof data !== 'object' || Array.isArray(data)) throw new SyntaxError('Invalid response');
        } catch (cause) {
            const error = new Error(cause.name === 'AbortError'
                ? 'Trợ lý phản hồi quá lâu. Vui lòng thử lại hoặc mở trang Đặt lịch.'
                : cause.name === 'SyntaxError' ? 'Máy chủ trả phản hồi chưa hợp lệ. Vui lòng tải lại trang hoặc thử lại sau.'
                : 'Mất kết nối tới Bin Spa. Vui lòng kiểm tra mạng và tải lại trang; nếu dùng HTTPS tại máy, hãy kiểm tra cảnh báo chứng chỉ của trình duyệt.');
            error.status = response?.status >= 400 ? response.status : 0;
            throw error;
        } finally { clearTimeout(timer); }
        if (!response.ok || data.success === false) {
            const error = new Error(data.msg || data.message || 'Có lỗi xảy ra, vui lòng thử lại.');
            error.status = response.status;
            error.configured = data.configured;
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
                for (const item of history) if (item.draft?.draft_id === draft.draft_id) item.draft.confirmed_appointment_id = malh;
                store.save(history);
            } catch (error) {
                status.textContent = error.message;
                confirm.disabled = error.status === 410 || error.status === 403;
            }
        };
        card.querySelector('[data-dismiss]').onclick = () => {
            card.querySelector('.ai-draft-actions').remove();
            status.textContent = 'Đã bỏ bản nháp. Bạn có thể nhờ trợ lý chọn giờ khác.';
            for (const item of history) if (item.draft?.draft_id === draft.draft_id) item.draft.dismissed = true;
            store.save(history);
        };
        if (draft.confirmed_appointment_id || draft.dismissed) {
            card.querySelector('.ai-draft-actions').remove();
            status.innerHTML = draft.confirmed_appointment_id
                ? `✅ Đã xác nhận lịch #${esc(draft.confirmed_appointment_id)}. <a href="/profile#appointments">Xem lịch hẹn</a>`
                : 'Đã bỏ bản nháp.';
        }
    }

    function init(status) {
        scopeKey = status.chat_jobs && status.conversation_scope ? KEY + '.' + status.conversation_scope : KEY;
        history = store.load();
        const root = build();
        const fab = root.querySelector('.ai-fab');
        const panel = root.querySelector('.ai-panel');
        const log = root.querySelector('[data-log]');
        const form = root.querySelector('[data-form]');
        const input = form.querySelector('input');

        const greet = () => {
            log.innerHTML = '';
            message(log, 'model', 'Xin chào! Mình là trợ lý AI của Bin Spa. Mình có thể tư vấn dịch vụ, báo giá và giúp bạn đặt lịch. Bạn cần gì ạ?');
            history.forEach(h => {
                message(log, h.role, h.role === 'user' ? esc(h.text) : format(h.text));
                if (h.role === 'model' && h.draft && token()) draftCard(log, h.draft);
            });
        };
        const toggle = (open, focus = true) => {
            panel.hidden = !open;
            fab.setAttribute('aria-expanded', String(open));
            root.classList.toggle('is-open', open);
            writeValue('.open', open ? '1' : '0');
            if (open) {
                fab.querySelector('span').textContent = 'Trợ lý AI';
                if (focus) input.focus();
                requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
            }
        };
        fab.onclick = () => toggle(panel.hidden);
        root.querySelector('[data-close]').onclick = () => toggle(false);
        root.querySelector('[data-reset]').onclick = () => { if (!busy) { history = []; store.save(history); savePending(null); greet(); } };
        document.addEventListener('keydown', e => { if (e.key === 'Escape' && !panel.hidden) toggle(false); });
        root.querySelectorAll('[data-quick] button').forEach(b => b.onclick = () => send(b.textContent));

        function controls(disabled) {
            root.querySelectorAll('[data-quick] button, [data-reset], [data-form] button').forEach(b => { b.disabled = disabled; });
        }
        function fail(typing, text, error, pending) {
            if (pending) { pending.failed = true; pending.error = error.message; savePending(pending); }
            typing.innerHTML = `<span class="ai-error">${esc(error.message)}</span><div class="ai-draft-actions"><button type="button" class="ai-btn" data-retry>Thử lại</button><a class="ai-btn" href="/appointments/create">Mở trang Đặt lịch</a></div>`;
            typing.querySelector('[data-retry]').onclick = () => send(text, typing);
            if (!input.value) input.value = text;
            busy = false; controls(false);
        }
        function completed(data, text, requestId, typing) {
            typing.innerHTML = format(data.reply);
            if (!requestId || !history.some(h => h.role === 'model' && h.request_id === requestId)) {
                history.push({ role: 'user', text, request_id: requestId }, { role: 'model', text: data.reply, request_id: requestId, ...(data.draft ? { draft: data.draft } : {}) });
                store.save(history);
            }
            if (data.draft) {
                if (!token()) message(log, 'model', 'Vui lòng <a href="/auth/login">đăng nhập</a> để xác nhận đặt lịch.');
                else draftCard(log, data.draft);
            }
            if (panel.hidden) fab.querySelector('span').textContent = 'AI đã trả lời';
            busy = false; controls(false); log.scrollTop = log.scrollHeight;
        }
        async function resume(pending, typing) {
            busy = true; controls(true);
            while (true) {
                try {
                    const data = pending.accepted
                        ? await post(`/api/ai/chat/jobs/${pending.id}`, undefined, true, 'GET')
                        : await post('/api/ai/chat/jobs', { request_id: pending.id, message: pending.text, history: pending.history }, true);
                    pending.accepted = true; savePending(pending);
                    if (data.status === 'SUCCEEDED') {
                        completed(data.result, pending.text, pending.id, typing); savePending(null); return;
                    }
                    if (data.status === 'FAILED') { fail(typing, pending.text, new Error(data.message || 'Trợ lý chưa trả lời được. Vui lòng thử lại.'), pending); return; }
                    typing.innerHTML = `<span class="ai-typing"><i></i><i></i><i></i></span><small class="ai-progress">${data.status === 'PENDING' ? 'Đang chờ trợ lý trả lời…' : 'Trợ lý đang trả lời…'} Bạn có thể chuyển trang, câu trả lời vẫn được giữ.</small>`;
                } catch (error) {
                    if (error.configured === false) { fail(typing, pending.text, error, pending); return; }
                    if (error.status && error.status !== 429 && error.status < 500) { fail(typing, pending.text, error, pending); return; }
                    // Unknown POST outcomes are retried with the SAME id. The server
                    // queues it once; page unload or a lost acknowledgement cannot duplicate work.
                    typing.innerHTML = '<span class="ai-progress">Đang kết nối lại để nhận câu trả lời. Câu hỏi của bạn vẫn được giữ…</span>';
                    await new Promise(resolve => setTimeout(resolve, 10000));
                    continue;
                }
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }

        async function send(text, retryMessage) {
            text = String(text || '').trim();
            if (!text || busy) return;
            busy = true;
            input.value = '';
            if (!retryMessage) message(log, 'user', esc(text));
            const typing = retryMessage || message(log, 'model', '');
            typing.innerHTML = '<span class="ai-typing"><i></i><i></i><i></i></span>';
            controls(true);
            if (status.chat_jobs) {
                const pending = { id: newRequestId(), text, history: history.slice(-10).map(h => ({ role: h.role, text: h.text.slice(0, 1000) })), accepted: false };
                savePending(pending);
                await resume(pending, typing);
                return;
            }
            try {
                const data = await post('/api/ai/chat', { message: text, history: history.slice(-10) });
                completed(data, text, null, typing);
            } catch (error) {
                fail(typing, text, error);
            } finally {
                busy = false;
                controls(false);
                log.scrollTop = log.scrollHeight;
            }
        }
        form.onsubmit = e => { e.preventDefault(); send(input.value); };
        greet();
        const open = readValue('.open') === '1';
        toggle(open, false);
        const pending = status.chat_jobs ? readPending() : null;
        if (pending && !history.some(h => h.role === 'model' && h.request_id === pending.id)) {
            message(log, 'user', esc(pending.text));
            const typing = message(log, 'model', '<span class="ai-progress">Đang lấy tiếp câu trả lời…</span>');
            if (pending.failed) fail(typing, pending.text, new Error(pending.error), pending);
            else void resume(pending, typing);
        } else if (pending) savePending(null);
    }

    document.addEventListener('DOMContentLoaded', async () => {
        try {
            if (window.CustomerAuth?.restoreAccessToken) await window.CustomerAuth.restoreAccessToken();
            const status = await (await fetch('/api/ai/status')).json();
            scopeKey = status.chat_jobs && status.conversation_scope ? KEY + '.' + status.conversation_scope : KEY;
            if (status.configured || status.chat_jobs && readPending()) init(status);
        } catch (e) { /* AI tùy chọn: lỗi thì không hiện widget */ }
    });
})();
