/* Voucher gift history and issuance for the supported legacy customer screen. */
(() => {
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const money = value => Number(value || 0).toLocaleString('vi-VN') + 'đ';
    const date = value => value ? new Date(value).toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'}) : 'Không hết hạn';
    const sources = {welcome:'Quà chào mừng',staff_gift:'Được spa tặng'};
    const statuses = {available:'Chưa sử dụng',reserved:'Đang áp dụng',used:'Đã dùng',expired:'Hết hạn',cancelled:'Đã thu hồi'};
    const scopes = {both:'Dịch vụ và gói',service_invoice:'Hóa đơn dịch vụ',package_purchase:'Mua gói'};
    const benefit = r => r.reward_type === 'voucher_percent' ? `Giảm ${r.percentage_value}%${r.max_discount_amount ? ' · tối đa '+money(r.max_discount_amount) : ''}` : 'Giảm '+money(r.reward_value);
    async function api(path, method='GET', body, key) {
        const response = await fetch(path, {method, headers:{'Content-Type':'application/json',Authorization:'Bearer '+localStorage.getItem('admin_token'),...(key?{'Idempotency-Key':key}:{})}, ...(body?{body:JSON.stringify(body)}:{})});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {const e = new Error(data.message || data.msg || 'Không thực hiện được yêu cầu'); e.status = response.status; throw e;}
        return data;
    }
    function mount(root, customer) {
        const role = localStorage.getItem('admin_role');
        if (!['admin','manager','letan'].includes(role)) return;
        root.classList.add('loyalty-page');
        root.style.gridColumn = '1 / -1';
        root.innerHTML = `<h3>Voucher tặng</h3><button type="button" class="btn btn-primary" data-gift ${customer.trangthai==='active'?'':'disabled'}>Tặng voucher</button><p data-note role="status"></p><form data-filters><label>Nguồn<select name="issuance_source"><option value="">Mọi nguồn tặng</option><option value="welcome">Quà chào mừng</option><option value="staff_gift">Được spa tặng</option></select></label><label>Trạng thái<select name="status"><option value="all">Tất cả</option><option value="usable">Có thể dùng</option><option value="applied">Đang áp dụng</option><option value="done">Đã dùng</option><option value="closed">Hết hạn / Đã thu hồi</option></select></label><label>Mã nhân viên tặng<input name="issued_by_staff" type="number" min="1" step="1"></label><button class="btn btn-secondary">Lọc lịch sử</button></form><div data-history></div><dialog class="loyalty-dialog" aria-label="Tặng voucher" data-dialog></dialog>`;
        const note = text => {root.querySelector('[data-note]').textContent=text;};
        const history = root.querySelector('[data-history]'), dialog = root.querySelector('[data-dialog]');
        let version=0, page=1, busy=false;
        // Store an actor ID, never the token or its encoded claims, in the storage key.
        let actorId=role;
        try {actorId=JSON.parse(atob(localStorage.getItem('admin_token').split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))).sub;} catch { /* Role fallback only affects optional recovery. */ }
        const recoveryKey=`binspa-voucher-gift-legacy:${actorId}:${customer.makh}`;
        let pending=null;
        try {pending=JSON.parse(sessionStorage.getItem(recoveryKey)||'null');if(!pending?.key||!pending?.body?.reward_id)pending=null;} catch { /* Optional recovery. */ }
        const remember=value=>{pending=value;try {if(value)sessionStorage.setItem(recoveryKey,JSON.stringify(value));else sessionStorage.removeItem(recoveryKey);}catch{/* In-memory retry remains. */}};
        dialog.addEventListener('cancel', e=>{if(busy)e.preventDefault();});
        dialog.addEventListener('keydown', e=>{if(e.key==='Escape')e.stopPropagation();});
        async function load() {
            const token=++version;
            history.textContent='Đang tải lịch sử...';
            const params=new URLSearchParams(new FormData(root.querySelector('[data-filters]')));params.set('page',page);
            try {
                const data=await api(`/api/admin/loyalty/customers/${customer.makh}/voucher-gifts?${params}`);
                if(token!==version||!root.isConnected)return;
                history.innerHTML=data.items.map(g=>`<article class="loyalty-card"><h4>${esc(g.reward.name)}</h4><p>${sources[g.issuance_source]} · ${statuses[g.status]||esc(g.status)}</p><p><code>${esc(g.code)}</code> · ${esc(benefit(g.reward))}</p><p>${scopes[g.reward.apply_to||'both']} · Đơn từ ${money(g.reward.minimum_spend)}</p><p>Cấp lúc ${date(g.issued_at)} · Hạn ${date(g.expires_at)}</p>${g.issued_by_name?`<p>Người tặng: ${esc(g.issued_by_name)}</p>`:''}${g.gift_reason?`<p>Lý do nội bộ: ${esc(g.gift_reason)}</p>`:''}${g.customer_message?`<p>Lời nhắn: ${esc(g.customer_message)}</p>`:''}${g.cancelled_at?`<p>Thu hồi lúc ${date(g.cancelled_at)} · ${esc(g.cancelled_by_name)} · ${esc(g.cancel_reason)}</p>`:''}${['admin','manager'].includes(role)&&g.status==='available'?`<button class="btn btn-danger" type="button" data-cancel="${g.id}">Thu hồi voucher</button>`:''}</article>`).join('')||'<p>Khách chưa có voucher được tặng phù hợp.</p>';
                if(data.pages>1)history.insertAdjacentHTML('beforeend',`<button type="button" class="btn btn-secondary" data-prev ${page<=1?'disabled':''}>Trước</button><span> ${page} / ${data.pages} </span><button type="button" class="btn btn-secondary" data-next ${page>=data.pages?'disabled':''}>Sau</button>`);
                history.querySelector('[data-prev]')?.addEventListener('click',()=>{page--;load();});history.querySelector('[data-next]')?.addEventListener('click',()=>{page++;load();});
                history.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>openCancel(data.items.find(g=>g.id===Number(b.dataset.cancel))));
            } catch(e) {if(token===version){history.innerHTML='<p role="alert"></p><button type="button" class="btn btn-secondary">Thử lại</button>';history.querySelector('p').textContent=e.message;history.querySelector('button').onclick=load;}}
        }
        function openCancel(g) {
            dialog.innerHTML=`<h3>Thu hồi voucher</h3><p>${esc(customer.hoten)} · ${esc(g.code)}</p><p>Không hoàn tồn khi thu hồi.</p><form><label>Lý do thu hồi<textarea name="reason" required maxlength="2000"></textarea></label><p data-error role="alert"></p><button class="btn btn-danger" type="submit">Xác nhận thu hồi</button><button class="btn btn-secondary" type="button" data-close>Đóng</button></form>`;
            dialog.querySelector('[data-close]').onclick=()=>{if(!busy)dialog.close();};
            dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);try{await api(`/api/admin/loyalty/voucher-gifts/${g.id}/cancel`,'POST',{reason:e.target.elements.reason.value});dialog.close();note('Đã thu hồi voucher');await load();}catch(error){dialog.querySelector('[data-error]').textContent=error.message;await load();}finally{busy=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}};
            dialog.showModal();dialog.querySelector('textarea').focus();
        }
        async function openGift() {
            let templatePage=1, templates=[], search='', templatesReady=false;
            dialog.innerHTML=`<h3>Tặng voucher</h3><p>${esc(customer.hoten)} · KH #${customer.makh} · ${customer.sdt?'••••'+esc(customer.sdt.slice(-4)):'Chưa có SĐT'}</p><p>Cấp vào Ưu đãi của tôi; điểm của khách không thay đổi.</p><form data-templates><label>Tìm mẫu<input name="search" type="search" maxlength="100"></label><button type="submit" class="btn btn-secondary">Tìm mẫu</button></form><form data-issue><fieldset><label>Mẫu voucher<select name="reward_id" required></select></label><p data-template-status role="status"></p><p data-template-help hidden></p><div data-template-pager></div><div data-terms></div><label>Lý do nội bộ (khách không thấy)<textarea name="reason" required maxlength="2000"></textarea></label><label>Lời nhắn cho khách<textarea name="customer_message" maxlength="1000"></textarea></label></fieldset><p data-error role="alert"></p><p data-pending role="status"></p><button type="submit" class="btn btn-primary" data-submit>Xác nhận tặng 1 voucher</button><button type="button" class="btn btn-secondary" data-close>Đóng</button></form>`;
            const form=dialog.querySelector('[data-issue]');
            const terms=()=>{const r=templates.find(t=>t.id===Number(form.elements.reward_id.value));dialog.querySelector('[data-terms]').textContent=r?`${benefit(r)} · ${scopes[r.apply_to||'both']} · Đơn từ ${money(r.minimum_spend)} · ${r.validity_days?'Hạn '+r.validity_days+' ngày':'Không hết hạn'} · ${r.stock==null?'Tồn không giới hạn':'Còn '+r.stock}`:'';};
            const sync=()=>{form.querySelector('fieldset').disabled=busy||!!pending;dialog.querySelector('[data-templates]').querySelectorAll('input,button').forEach(b=>b.disabled=busy||!!pending);form.querySelector('[data-pending]').textContent=pending?'Đang giữ yêu cầu chưa rõ kết quả. Thử lại sẽ không tặng thêm voucher.':'';form.querySelector('[data-submit]').textContent=pending?'Thử lại cùng yêu cầu':'Xác nhận tặng 1 voucher';form.querySelector('[data-submit]').disabled=busy||(!pending&&(!templatesReady||!templates.length));form.querySelector('[data-close]').disabled=busy;};
            async function loadTemplates(){
                templatesReady=false;sync();dialog.querySelector('[data-template-status]').textContent='Đang tải mẫu...';
                try{const data=await api(`/api/admin/loyalty/gift-templates?${new URLSearchParams({page:templatePage,per_page:10,search})}`);templates=data.items;form.elements.reward_id.innerHTML='<option value="">Chọn mẫu voucher</option>'+templates.map(t=>`<option value="${t.id}">${esc(t.name)} · ${esc(benefit(t))}</option>`).join('');if(pending){if(!templates.some(t=>t.id===pending.body.reward_id))form.elements.reward_id.add(new Option('Mẫu đã chọn #'+pending.body.reward_id,pending.body.reward_id));form.elements.reward_id.value=pending.body.reward_id;form.elements.reason.value=pending.body.reason;form.elements.customer_message.value=pending.body.customer_message;}templatesReady=true;dialog.querySelector('[data-template-status]').textContent=templates.length?'':'Không có mẫu voucher phù hợp để tặng';const help=dialog.querySelector('[data-template-help]');help.hidden=!!templates.length;help.innerHTML='Có thể tặng voucher giảm tiền hoặc phần trăm còn tồn, kể cả mẫu tắt hoạt động. Kiểm tra bộ lọc hoặc bổ sung mẫu/tồn kho. '+(['admin','manager'].includes(role)?'<a href="/admin/loyalty?tab=rewards" target="_blank" rel="noopener noreferrer">Quản lý mẫu voucher</a>':'Nhờ quản lý tạo hoặc bật mẫu voucher tặng.');dialog.querySelector('[data-template-pager]').innerHTML=data.pages>1?`<button type="button" data-prev ${templatePage<=1?'disabled':''}>Trước</button> ${templatePage}/${data.pages} <button type="button" data-next ${templatePage>=data.pages?'disabled':''}>Sau</button>`:'';dialog.querySelector('[data-template-pager] [data-prev]')?.addEventListener('click',()=>{templatePage--;loadTemplates();});dialog.querySelector('[data-template-pager] [data-next]')?.addEventListener('click',()=>{templatePage++;loadTemplates();});terms();}catch(e){dialog.querySelector('[data-template-status]').textContent=e.message;}finally{sync();}}
            form.elements.reward_id.onchange=terms;
            dialog.querySelector('[data-templates]').onsubmit=e=>{e.preventDefault();search=e.target.elements.search.value.trim();templatePage=1;loadTemplates();};
            form.querySelector('[data-close]').onclick=()=>{if(!busy)dialog.close();};
            form.onsubmit=async e=>{e.preventDefault();if(busy)return;const operation=pending||{key:crypto.randomUUID(),body:{reward_id:Number(form.elements.reward_id.value),reason:form.elements.reason.value.trim(),customer_message:form.elements.customer_message.value.trim()}};remember(operation);busy=true;sync();try{const data=await api(`/api/admin/loyalty/customers/${customer.makh}/voucher-gifts`,'POST',operation.body,operation.key);remember(null);dialog.close();note('Đã tặng voucher '+data.redemption.code);await load();}catch(error){form.querySelector('[data-error]').textContent=error.message;if(error.status&&error.status<500)remember(null);}finally{busy=false;sync();}};
            dialog.showModal();await loadTemplates();sync();dialog.querySelector('[data-close]').focus();
        }
        root.querySelector('[data-gift]').onclick=openGift;
        root.querySelector('[data-filters]').onsubmit=e=>{e.preventDefault();page=1;load();};
        load();
        return {openGift};
    }
    window.AdminVoucherGifts={mount};
})();
