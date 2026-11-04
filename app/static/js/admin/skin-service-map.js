/* Gemini drafts stay in this page until an admin explicitly approves them. */
document.addEventListener('DOMContentLoaded', () => {
    if (!isTokenValid() || !hasRole(['admin', 'manager'])) return;
    const api = '/api/admin/skin-service-map';
    const groups = document.getElementById('skin-map-groups');
    const propose = document.getElementById('skin-map-propose');
    const save = document.getElementById('skin-map-save');
    const draft = document.getElementById('skin-map-draft');
    const status = document.getElementById('skin-map-status');
    let state, busy = false;
    const rows = [];
    function say(message, error = false) {
        status.textContent = message || '';
        status.dataset.error = String(error);
    }
    function setBusy(value) {
        busy = value;
        propose.disabled = save.disabled = value || !state || state.schema_ready === false;
        groups.setAttribute('aria-busy', String(value));
        rows.forEach(row => { row.input.disabled = value || state?.schema_ready === false; });
    }
    async function request(method, suffix = '', body) {
        const headers = getAuthHeaders();
        if (!headers) throw new Error('Vui lòng đăng nhập lại.');
        const response = await fetch(api + suffix, {
            method, headers, ...(body === undefined ? {} : {body: JSON.stringify(body)})
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || data.msg || 'Chưa thực hiện được yêu cầu.');
        return data;
    }
    function node(tag, text, className) {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        if (className) element.className = className;
        return element;
    }
    function differences() {
        rows.forEach(row => {
            const approved = (state.map[row.code] || []).includes(row.sid);
            row.diff.textContent = row.input.checked === approved ? '' :
                (row.input.checked ? 'Thêm mới so với map đang dùng' : 'Bị bỏ so với map đang dùng');
        });
    }
    function render(data) {
        state = data;
        rows.length = 0;
        groups.replaceChildren();
        const sources = {database: 'DB (map đã duyệt)', env: '.env (SKIN_SERVICE_MAP)', empty: 'Chưa có map'};
        document.getElementById('skin-map-source').textContent = 'Nguồn đang dùng: ' + sources[data.source];
        const approved = data.approved_at ? new Date(data.approved_at).toLocaleString('vi-VN') : '';
        document.getElementById('skin-map-approved').textContent = approved ?
            `Duyệt lúc ${approved} · Người duyệt: ${data.approved_by_name || 'Không còn thông tin'}` : 'Chưa có lần duyệt trong DB.';
        Object.entries(data.types).forEach(([code, name]) => {
            const block = node('fieldset', undefined, 'skin-map-type');
            block.append(node('legend', name));
            if (!data.services.length) block.append(node('p', 'Chưa có dịch vụ đang hoạt động.'));
            const hiddenCount = (data.map[code] || []).filter(id => !data.services.some(s => s.madv === id)).length;
            if (hiddenCount) block.append(node('p', `${hiddenCount} dịch vụ trong map đã ngừng hoặc không còn tồn tại; sẽ được bỏ khi lưu.`));
            data.services.forEach(service => {
                const label = node('label', undefined, 'skin-map-service');
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.dataset.type = code;
                input.value = service.madv;
                input.checked = (data.map[code] || []).includes(service.madv);
                const copy = node('span');
                const reason = node('small');
                const diff = node('small', '', 'skin-map-diff');
                copy.append(node('span', service.tendv), node('small', service.category_name || 'Chưa có danh mục'), reason, diff);
                label.append(input, copy);
                block.append(label);
                rows.push({code, sid: service.madv, input, reason, diff});
                input.addEventListener('change', () => { draft.hidden = false; differences(); say(''); });
            });
            groups.append(block);
        });
        draft.hidden = true;
    }
    propose.addEventListener('click', async () => {
        if (busy) return;
        setBusy(true);
        say('Đang nhờ Gemini đề xuất…');
        try {
            const data = await request('POST', '/proposal');
            rows.forEach(row => {
                const group = data.assignments.find(g => g.type_code === row.code);
                const item = group?.items.find(i => i.service_id === row.sid);
                row.input.checked = Boolean(item);
                row.reason.textContent = item?.reason || '';
            });
            differences();
            draft.hidden = false;
            say(data.message || 'Đã nhận đề xuất. Hãy xem, chỉnh sửa rồi lưu và duyệt.');
        } catch (error) { say(error.message, true); }
        finally { setBusy(false); }
    });
    save.addEventListener('click', async () => {
        if (busy || !state) return;
        const mapping = Object.fromEntries(Object.keys(state.types).map(t => [t, []]));
        rows.forEach(row => { if (row.input.checked) mapping[row.code].push(row.sid); });
        if (Object.values(mapping).some(ids => ids.length > 10)) {
            say('Mỗi loại mụn chỉ được duyệt tối đa 10 dịch vụ.', true);
            return;
        }
        const counts = Object.entries(mapping).map(([t, ids]) => `${state.types[t]}: ${ids.length} dịch vụ`).join('\n');
        const empty = Object.values(mapping).every(ids => !ids.length);
        if (!window.confirm(`Lưu và duyệt map này?\n${counts}${empty ? '\nMap rỗng: sẽ quay về dùng SKIN_SERVICE_MAP trong .env.' : ''}`)) return;
        setBusy(true);
        say('Đang lưu…');
        try {
            const data = await request('PUT', '', {map: mapping});
            render({...state, ...data});
            say(data.message);
        } catch (error) { say(error.message, true); }
        finally { setBusy(false); }
    });
    setBusy(true);
    request('GET').then(data => { render(data); say(data.schema_ready === false ? 'Cấu hình gợi ý dịch vụ chưa được cập nhật trên hệ thống này. Cần cập nhật dữ liệu trước khi duyệt dịch vụ; cấu hình đang dùng vẫn được giữ nguyên.' : '', data.schema_ready === false); })
        .catch(error => say(error.message, true)).finally(() => setBusy(false));
});
