(() => {
    const {api,esc,money}=window.LoyaltyPayment;
    const el=id=>document.getElementById(id);
    const labels={wallets:'Ví khách hàng',available_points:'Điểm khả dụng',reserved_points:'Điểm đang giữ',lifetime_earned:'Tổng đã tích',lifetime_redeemed:'Tổng đã dùng'};
    const statuses={available:'Chưa sử dụng',reserved:'Đang giữ',used:'Đã sử dụng',fulfilled:'Đã giao quà',expired:'Hết hạn',cancelled:'Đã hủy'};
    let tab='overview',page=1,search='',version=0,rewards=[],editReward=null,adjustId=null,adjustKey=null;
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
    async function load(){
        const token=++version;note('');
        try{
            const suffix=tab==='customers'?`?page=${page}&search=${encodeURIComponent(search)}`:`?page=${page}`;
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
                rewards=data.items;content.innerHTML='<button class="btn btn-primary" data-new>Tạo quà đổi thưởng</button><div class="loyalty-cards">'+rewards.map(r=>`<article class="loyalty-card"><h3>${esc(r.name)}</h3><p>${esc(r.description)}</p><strong>${r.points_cost} điểm</strong><p>${r.reward_type==='voucher_amount'?money(r.reward_value):'Quà tại cửa hàng'}</p><p>Còn: ${r.stock??'Không giới hạn'} · ${r.active?'Đang cho đổi':'Ngừng đổi'}</p><button class="btn btn-secondary" data-edit="${r.id}">Sửa</button><button class="btn btn-secondary" data-stop="${r.id}">Ngừng đổi</button></article>`).join('')+'</div>';
                content.querySelector('[data-new]').onclick=()=>edit(null);content.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>edit(rewards.find(r=>r.id===Number(b.dataset.edit))));
                content.querySelectorAll('[data-stop]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api(`/api/admin/loyalty/rewards/${b.dataset.stop}`,'DELETE');await load();}catch(e){note(e.message);b.disabled=false;}});
            }
            if(tab==='redemptions'){
                content.innerHTML=`<ul class="loyalty-history">${data.items.map(r=>`<li><strong>${esc(r.reward.name)}</strong> · KH #${r.makh} · ${r.points_spent} điểm<p>${esc(r.code)} · ${esc(statuses[r.status]||r.status)} · ${date(r.redeemed_at)}</p>${r.reward.reward_type==='physical_gift'&&r.status==='available'?`<button class="btn btn-primary" data-fulfill="${r.id}">Xác nhận đã giao quà</button>`:''}</li>`).join('')||'<li>Chưa có lượt đổi quà.</li>'}</ul>`;
                content.querySelectorAll('[data-fulfill]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api(`/api/admin/loyalty/redemptions/${b.dataset.fulfill}/fulfill`,'POST',{});await load();}catch(e){note(e.message);b.disabled=false;}});
            }
            if(data.items)pager(data,p=>{page=p;load();});
        }catch(error){if(token===version)note(error.message);}
    }
    function edit(reward){editReward=reward?.id||null;const form=el('rewardForm');form.reset();if(reward)for(const k of ['name','description','reward_type','points_cost','reward_value','stock','validity_days'])form.elements[k].value=reward[k]??'';form.elements.active.checked=reward?.active??true;el('loyaltyRewardEditor').showModal();}
    document.addEventListener('DOMContentLoaded',()=>{
        el('adminLoyalty').querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;page=1;load();});
        el('adminLoyalty').querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
        el('adjustForm').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('[type=submit]');b.disabled=true;try{await api(`/api/admin/loyalty/customers/${adjustId}/adjust`,'POST',{points_delta:Number(f.elements.points.value)*Number(f.elements.direction.value),reason:f.elements.reason.value,idempotency_key:adjustKey});el('loyaltyAdjust').close();await load();note('Đã lưu điều chỉnh và lịch sử điểm.');}catch(error){note(error.message);}finally{b.disabled=false;}};
        el('rewardForm').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('[type=submit]');b.disabled=true;try{const body={};for(const k of ['name','description','reward_type'])body[k]=f.elements[k].value;for(const k of ['points_cost','reward_value'])body[k]=Number(f.elements[k].value);for(const k of ['stock','validity_days'])body[k]=f.elements[k].value===''?null:Number(f.elements[k].value);body.active=f.elements.active.checked;await api('/api/admin/loyalty/rewards'+(editReward?'/'+editReward:''),editReward?'PUT':'POST',body);el('loyaltyRewardEditor').close();await load();}catch(error){note(error.message);}finally{b.disabled=false;}};
        load();
    });
})();
