(() => {
    const {api,esc,money}=window.LoyaltyPayment;
    const el=id=>document.getElementById(id);
    const labels={wallets:'Ví khách hàng',available_points:'Điểm khả dụng',reserved_points:'Điểm đang giữ',lifetime_earned:'Tổng đã tích',lifetime_redeemed:'Tổng đã dùng'};
    const statuses={available:'Chưa sử dụng',reserved:'Đang áp dụng',used:'Đã sử dụng',fulfilled:'Đã giao quà',expired:'Hết hạn',cancelled:'Đã hủy'};
    const pct=value=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(Number(value))+'%';
    const benefitText=r=>r.reward_type==='physical_gift'?'Quà tại cửa hàng':r.reward_type==='voucher_percent'?`Voucher giảm ${pct(r.percentage_value)}${r.max_discount_amount?` · tối đa ${money(r.max_discount_amount)}`:''}`:'Voucher '+money(r.reward_value);
    const statusText=r=>r.status==='available'&&r.reward.reward_type==='physical_gift'?'Chờ nhận quà':statuses[r.status]||r.status;
    const deskGroups={all:'Tất cả',pickup:'Chờ nhận quà',usable:'Voucher có thể dùng',applied:'Đang áp dụng',done:'Đã dùng / Đã giao',closed:'Hết hạn / Đã hủy'};
    const desk={search:'',status:'all',reward_type:''};
    // Front desk only hands over gifts; the server enforces the same split for every API.
    const role=(()=>{try{return localStorage.getItem('admin_role');}catch{return null;}})();
    const deskOnly=role==='letan';
    const applyLabels={service_invoice:'Hóa đơn dịch vụ',package_purchase:'Mua gói',both:'Cả hai'};
    let tab=deskOnly||new URLSearchParams(location.search).get('tab')==='redemptions'?'redemptions':'overview',page=1,search='',version=0,rewards=[],editReward=null,adjustId=null,adjustKey=null;
    const note=text=>el('loyaltyMessage').textContent=text;
    const date=value=>value?new Date(value).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Không hết hạn';
    const history=rows=>`<ul class="loyalty-history">${rows.map(r=>`<li><strong>${r.points_delta>0?'+':''}${r.points_delta} điểm</strong> · KH #${r.makh}<p>${esc(r.description)}</p><small>${date(r.created_at)}</small></li>`).join('')||'<li>Chưa có lịch sử.</li>'}</ul>`;
    function pager(data,callback){
        if(data.pages<2)return;
        const area=document.createElement('div');area.className='loyalty-actions';
        area.innerHTML=`<button class="btn btn-secondary" data-prev ${data.page===1?'disabled':''}>Trước</button><span>${data.page} / ${data.pages}</span><button class="btn btn-secondary" data-next ${data.page>=data.pages?'disabled':''}>Sau</button>`;
        area.querySelector('[data-prev]').onclick=()=>callback(data.page-1);area.querySelector('[data-next]').onclick=()=>callback(data.page+1);el('loyaltyContent').append(area);
    }
    async function detail(id,p=1){
        const data=await api(`/api/admin/loyalty/customers/${id}?page=${p}`);
        el('loyaltyContent').innerHTML=`<h3>${esc(data.customer.hoten)} · ${esc(data.customer.sdt)}</h3><div class="loyalty-cards">${Object.entries(data.wallet).map(([k,v])=>`<div class="loyalty-card">${labels[k]}<strong>${v}</strong></div>`).join('')}</div>${history(data.items)}<button class="btn btn-secondary" data-back>Danh sách khách hàng</button>`;
        el('loyaltyContent').querySelector('[data-back]').onclick=()=>load();pager(data,p=>detail(id,p).catch(e=>note(e.message)));
    }
    const rules={earn_amount_unit:'Số tiền cho mỗi lần tích điểm (VNĐ)',earn_points:'Điểm tích mỗi lần',point_value:'Giá trị một điểm (VNĐ)',minimum_redeem_points:'Số điểm dùng tối thiểu',maximum_redeem_percent:'Giảm bằng điểm tối đa (%)',earn_on_service_invoice:'Tích điểm khi trả tiền dịch vụ',earn_on_package_purchase:'Tích điểm khi mua gói',redeem_on_service_invoice:'Cho dùng điểm trả tiền dịch vụ',redeem_on_package_purchase:'Cho dùng điểm mua gói'};
    // A failed tab must never leave the previous tab's content on screen.
    function showLoadError(error){
        const label=el('adminLoyalty').querySelector(`[data-tab="${tab}"]`)?.textContent.trim()||'mục này';
        const detail=!error.status?'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.':
            error.status===401?'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.':
            error.status===403?'Tài khoản của bạn không có quyền xem mục này.':
            error.status>=500?`Máy chủ gặp lỗi (mã ${error.status}). Vui lòng thử lại; nếu vẫn lỗi, báo bộ phận kỹ thuật.`:error.message;
        const content=el('loyaltyContent');
        content.innerHTML=`<div class="loyalty-state loyalty-error" role="alert"><p><strong>Không tải được “${esc(label)}”.</strong> ${esc(detail)}</p><button type="button" class="btn btn-secondary" data-reload>Thử lại</button></div>`;
        content.querySelector('[data-reload]').onclick=()=>load();
    }
    async function load(){
        const token=++version;note('');
        el('adminLoyalty').querySelectorAll('[data-tab]').forEach(b=>{const on=b.dataset.tab===tab;b.classList.toggle('btn-primary',on);b.classList.toggle('btn-secondary',!on);b.setAttribute('aria-pressed',String(on));});
        try{
            const suffix=tab==='customers'?`?page=${page}&search=${encodeURIComponent(search)}`:tab==='redemptions'?'?'+new URLSearchParams({page,...desk}):`?page=${page}`;
            const data=await api('/api/admin/loyalty/'+tab+suffix);if(token!==version)return;
            const content=el('loyaltyContent');
            if(tab==='overview')content.innerHTML=`<div class="loyalty-cards">${Object.entries(data.overview).map(([k,v])=>`<div class="loyalty-card">${labels[k]}<strong>${v}</strong></div>`).join('')}</div><p>Điểm chỉ tích sau thanh toán được xác nhận. Điểm đang giữ sẽ dùng cho phiếu đang chờ thanh toán.</p>`;
            if(tab==='config'){
                content.innerHTML=`<form id="loyaltyRules">${Object.entries(rules).map(([k,label])=>typeof data.config[k]==='boolean'?`<label><input name="${k}" type="checkbox" ${data.config[k]?'checked':''}> ${label}</label>`:`<label>${label}<input name="${k}" type="number" min="${k==='maximum_redeem_percent'||k==='earn_points'?0:1}" ${k==='maximum_redeem_percent'?'max="100" step="0.01"':'step="1"'} value="${esc(data.config[k])}" required></label>`).join('')}<p>Điểm không hết hạn.</p><button class="btn btn-primary" type="submit">Lưu quy tắc</button></form>`;
                el('loyaltyRules').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('button');b.disabled=true;try{const body={};for(const k of Object.keys(rules))body[k]=typeof data.config[k]==='boolean'?f.elements[k].checked:Number(f.elements[k].value);await api('/api/admin/loyalty/config','PUT',body);note('Đã lưu quy tắc.');}catch(error){note(error.message);}finally{b.disabled=false;}};
            }
            if(tab==='customers'){
                content.innerHTML=`<form data-search><label>Tìm tên, SĐT, email<input name="search" value="${esc(search)}"></label><button class="btn btn-secondary">Tìm khách hàng</button></form><div class="loyalty-table"><table><thead><tr><th>Khách hàng</th><th>Khả dụng</th><th>Đang giữ</th><th>Đã tích</th><th>Đã dùng</th><th>Thao tác</th></tr></thead><tbody>${data.items.map(c=>`<tr><td>${esc(c.hoten)}<br>${esc(c.sdt)}<br>${esc(c.email)}</td><td>${c.available_points}</td><td>${c.reserved_points}</td><td>${c.lifetime_earned}</td><td>${c.lifetime_redeemed}</td><td><button class="btn btn-secondary" data-detail="${c.makh}">Chi tiết</button><button class="btn btn-primary" data-adjust="${c.makh}">Điều chỉnh điểm</button></td></tr>`).join('')||'<tr><td colspan="6">Không tìm thấy khách hàng.</td></tr>'}</tbody></table></div>`;
                content.querySelector('[data-search]').onsubmit=e=>{e.preventDefault();search=e.target.elements.search.value;page=1;load();};
                content.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>detail(b.dataset.detail).catch(e=>note(e.message)));
                content.querySelectorAll('[data-adjust]').forEach(b=>b.onclick=()=>{adjustId=Number(b.dataset.adjust);adjustKey=crypto.randomUUID();el('adjustForm').reset();el('adjustCustomer').textContent=data.items.find(c=>c.makh===adjustId).hoten;el('loyaltyAdjust').showModal();});
            }
            if(tab==='transactions')content.innerHTML=history(data.items);
            if(tab==='rewards'){
                rewards=data.items;content.innerHTML='<button class="btn btn-primary" data-new>Tạo quà đổi thưởng</button><div class="loyalty-cards">'+rewards.map(r=>`<article class="loyalty-card"><h3>${esc(r.name)}</h3><p>${esc(r.description)}</p><strong>${r.points_cost} điểm</strong><p>${r.reward_type==='physical_gift'?'Quà tại cửa hàng':`${esc(benefitText(r))} · ${applyLabels[r.apply_to]||applyLabels.both}${Number(r.minimum_spend)?` · Đơn từ ${money(r.minimum_spend)}`:''}`}</p><p>Còn: ${r.stock??'Không giới hạn'} · ${r.active?'Đang cho đổi':'Ngừng đổi'}</p><button class="btn btn-secondary" data-edit="${r.id}">Sửa</button><button class="btn btn-secondary" data-stop="${r.id}">Ngừng đổi</button></article>`).join('')+'</div>';
                content.querySelector('[data-new]').onclick=()=>edit(null);content.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>edit(rewards.find(r=>r.id===Number(b.dataset.edit))));
                content.querySelectorAll('[data-stop]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api(`/api/admin/loyalty/rewards/${b.dataset.stop}`,'DELETE');await load();}catch(e){note(e.message);b.disabled=false;}});
            }
            if(tab==='redemptions')renderDesk(data);
            if(data.items)pager(data,p=>{page=p;load();});
        }catch(error){if(token===version)showLoadError(error);}
    }
    // Voucher-only fields are disabled (not just hidden) for gifts so the browser skips their validation.
    function syncRewardType(){
        const form=el('rewardForm'),kind=form.elements.reward_type.value,voucher=kind!=='physical_gift';
        // Hidden groups are also disabled so the browser skips their required/min validation.
        for(const [selector,on] of [['[data-amount-fields]',kind==='voucher_amount'],['[data-percent-fields]',kind==='voucher_percent'],['[data-voucher-fields]',voucher]]){
            const fields=form.querySelector(selector);fields.hidden=!on;fields.disabled=!on;
        }
        form.querySelector('[data-name-label]').textContent=voucher?'Tên voucher':'Tên quà';
    }
    function renderDesk(data){
        const content=el('loyaltyContent');
        const option=(value,label,current)=>`<option value="${value}" ${value===current?'selected':''}>${label}</option>`;
        const cell=(label,html)=>`<td data-label="${label}"><div>${html}</div></td>`;
        const row=r=>{
            const handover=r.reward.reward_type==='physical_gift'&&r.status==='available';
            // The handover action sits next to the status so it is never scrolled out of view.
            return `<tr data-redemption="${r.id}">`+cell('Khách',`${esc(r.customer.hoten)}<br><small>${esc(r.customer.sdt||'')}${r.customer.email?' · '+esc(r.customer.email):''}</small>`)+
                cell('Phần thưởng',`${esc(r.reward.name)}<br><small>${esc(benefitText(r.reward))}</small>`)+
                cell('Mã',`<code>${esc(r.code)}</code>`)+cell('Trạng thái',`<span class="loyalty-status loyalty-status--${esc(r.status)}">${esc(statusText(r))}</span>${handover?`<button class="btn btn-primary" data-fulfill="${r.id}">Xác nhận đã giao</button>`:''}`)+
                cell('Điểm đã dùng',r.points_spent)+cell('Ngày đổi',date(r.redeemed_at))+cell('Hạn',date(r.expires_at))+
                cell('Ngày dùng / nhận',r.fulfilled_at?date(r.fulfilled_at):r.used_at?date(r.used_at):'—')+cell('Người giao',esc(r.fulfilled_by_name||'—'))+'</tr>';
        };
        content.innerHTML=`<form data-desk class="loyalty-toolbar" role="search"><label>Tìm khách hoặc mã quà<input name="search" type="search" maxlength="100" value="${esc(desk.search)}" placeholder="Tên, SĐT, email hoặc BIN-..."></label>`+
            `<label>Trạng thái<select name="status">${Object.entries(deskGroups).map(([k,v])=>option(k,v,desk.status)).join('')}</select></label>`+
            `<label>Loại<select name="reward_type">${option('','Tất cả',desk.reward_type)}${option('physical_gift','Quà tại cửa hàng',desk.reward_type)}${option('voucher','Voucher',desk.reward_type)}</select></label><button class="btn btn-secondary">Tìm</button></form>`+
            `<p class="loyalty-muted">${data.total} lượt đổi</p><div class="loyalty-table loyalty-desk"><table><thead><tr><th>Khách</th><th>Phần thưởng</th><th>Mã</th><th>Trạng thái</th><th>Điểm đã dùng</th><th>Ngày đổi</th><th>Hạn</th><th>Ngày dùng / nhận</th><th>Người giao</th></tr></thead>`+
            `<tbody>${data.items.map(row).join('')||'<tr><td colspan="9">Không tìm thấy lượt đổi quà phù hợp.</td></tr>'}</tbody></table></div>`;
        const form=content.querySelector('[data-desk]');
        form.onsubmit=e=>{e.preventDefault();Object.assign(desk,{search:form.elements.search.value.trim(),status:form.elements.status.value,reward_type:form.elements.reward_type.value});page=1;load();};
        form.querySelectorAll('select').forEach(s=>s.onchange=()=>form.requestSubmit());
        content.querySelectorAll('[data-fulfill]').forEach(b=>b.onclick=()=>confirmHandover(data.items.find(r=>r.id===Number(b.dataset.fulfill))));
    }
    function confirmHandover(r){
        const dialog=el('giftHandover');
        el('giftHandoverDetail').innerHTML=`<dl class="loyalty-facts"><dt>Khách</dt><dd>${esc(r.customer.hoten)} · ${esc(r.customer.sdt||'')}</dd><dt>Quà</dt><dd>${esc(r.reward.name)}</dd><dt>Mã</dt><dd><code>${esc(r.code)}</code></dd><dt>Hạn</dt><dd>${date(r.expires_at)}</dd></dl>`;
        const button=el('giftHandoverConfirm');button.disabled=false;
        button.onclick=async()=>{
            button.disabled=true;
            try{
                const result=await api(`/api/admin/loyalty/redemptions/${r.id}/fulfill`,'POST',{});
                const done=result.redemption;dialog.close();await load();
                note(result.already_fulfilled?`Quà ${done.code} đã được giao trước đó lúc ${date(done.fulfilled_at)} bởi ${done.fulfilled_by_name||'nhân viên khác'}.`:`Đã xác nhận giao “${done.reward.name}” (${done.code}) cho ${done.customer.hoten}.`);
            }catch(error){dialog.close();await load();note(error.message);}
        };
        dialog.showModal();button.focus();
    }
    function edit(reward){
        editReward=reward?.id||null;const form=el('rewardForm');form.reset();
        if(reward){
            for(const k of ['name','description','reward_type','points_cost','stock','validity_days'])form.elements[k].value=reward[k]??'';
            if(reward.reward_type==='voucher_amount')form.elements.reward_value.value=Number(reward.reward_value);
            if(reward.reward_type==='voucher_percent'){form.elements.percentage_value.value=Number(reward.percentage_value);form.elements.max_discount_amount.value=reward.max_discount_amount?Number(reward.max_discount_amount):'';}
            if(reward.reward_type!=='physical_gift'){form.elements.minimum_spend.value=Number(reward.minimum_spend||0);form.elements.apply_to.value=reward.apply_to||'both';}
        }
        form.elements.active.checked=reward?.active??true;syncRewardType();el('loyaltyRewardEditor').showModal();
    }
    document.addEventListener('DOMContentLoaded',()=>{
        el('adminLoyalty').querySelectorAll('[data-tab]').forEach(b=>{
            if(deskOnly&&b.dataset.tab!=='redemptions'){b.remove();return;}
            b.onclick=()=>{tab=b.dataset.tab;page=1;el('loyaltyContent').innerHTML='<p class="loyalty-state">Đang tải...</p>';load();};
        });
        el('rewardForm').elements.reward_type.onchange=syncRewardType;
        el('adminLoyalty').querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
        el('adjustForm').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('[type=submit]');b.disabled=true;try{await api(`/api/admin/loyalty/customers/${adjustId}/adjust`,'POST',{points_delta:Number(f.elements.points.value)*Number(f.elements.direction.value),reason:f.elements.reason.value,idempotency_key:adjustKey});el('loyaltyAdjust').close();await load();note('Đã lưu điều chỉnh và lịch sử điểm.');}catch(error){note(error.message);}finally{b.disabled=false;}};
        el('rewardForm').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('[type=submit]');b.disabled=true;try{const body={};for(const k of ['name','description','reward_type'])body[k]=f.elements[k].value;body.points_cost=Number(f.elements.points_cost.value);body.reward_value=body.reward_type==='voucher_amount'?Number(f.elements.reward_value.value):0;if(body.reward_type==='voucher_percent'){body.percentage_value=Number(f.elements.percentage_value.value);body.max_discount_amount=f.elements.max_discount_amount.value===''?null:Number(f.elements.max_discount_amount.value);}if(body.reward_type!=='physical_gift'){body.minimum_spend=Number(f.elements.minimum_spend.value||0);body.apply_to=f.elements.apply_to.value;}for(const k of ['stock','validity_days'])body[k]=f.elements[k].value===''?null:Number(f.elements[k].value);body.active=f.elements.active.checked;await api('/api/admin/loyalty/rewards'+(editReward?'/'+editReward:''),editReward?'PUT':'POST',body);el('loyaltyRewardEditor').close();await load();}catch(error){note(error.message);}finally{b.disabled=false;}};
        load();
    });
})();
