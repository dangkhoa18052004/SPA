(() => {
    const {api,esc,money}=window.LoyaltyPayment;
    const labels={available_points:'Điểm khả dụng',reserved_points:'Điểm đang giữ',lifetime_earned:'Tổng điểm đã tích',lifetime_redeemed:'Tổng điểm đã dùng'};
    const statuses={available:'Chưa sử dụng',reserved:'Đang dùng cho thanh toán',used:'Đã sử dụng',fulfilled:'Đã nhận quà',expired:'Hết hạn',cancelled:'Đã hủy'};
    const date=value=>value?new Date(value).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Không hết hạn';
    const keys=new Map();
    let view='history',page=1,version=0;
    async function load(){
        const token=++version;
        const message=document.getElementById('customerLoyaltyMessage');
        try{
            const balance=(await api('/api/loyalty/me')).wallet;
            if(token!==version)return;
            document.getElementById('loyaltyBalance').innerHTML=Object.entries(labels).map(([k,label])=>`<div class="loyalty-card">${label}<strong>${balance[k]}</strong></div>`).join('');
            const endpoint={history:'/api/loyalty/me/transactions',rewards:'/api/loyalty/rewards',mine:'/api/loyalty/my-rewards'}[view];
            const data=await api(endpoint+'?page='+page);if(token!==version)return;
            const content=document.getElementById('customerLoyaltyContent');
            if(view==='history')content.innerHTML=`<ul class="loyalty-history">${data.items.map(t=>`<li><strong>${t.points_delta>0?'+':''}${t.points_delta} điểm</strong><p>${esc(t.description)}</p><small>${date(t.created_at)}</small></li>`).join('')||'<li>Bạn chưa có lịch sử điểm.</li>'}</ul>`;
            if(view==='rewards'){
                content.innerHTML=`<div class="loyalty-cards">${data.items.map(r=>{const missing=Math.max(0,r.points_cost-balance.available_points);return `<article class="loyalty-card"><h3>${esc(r.name)}</h3><p>${esc(r.description)}</p><strong>${r.points_cost} điểm</strong><p>${r.reward_type==='voucher_amount'?money(r.reward_value):'Nhận quà tại Bin Spa'}</p><p>${r.validity_days?`Hiệu lực ${r.validity_days} ngày từ lúc đổi`:'Không hết hạn'}</p>${missing?`<p>Cần thêm ${missing} điểm</p>`:''}<button class="btn btn-primary" data-redeem="${r.id}" ${missing||r.stock===0?'disabled':''}>${r.stock===0?'Hết quà':'Đổi ngay'}</button></article>`;}).join('')||'<p>Chưa có quà đổi thưởng.</p>'}</div>`;
                content.querySelectorAll('[data-redeem]').forEach(b=>b.onclick=async()=>{b.disabled=true;const id=b.dataset.redeem;if(!keys.has(id))keys.set(id,crypto.randomUUID());try{await api(`/api/loyalty/rewards/${id}/redeem`,'POST',{idempotency_key:keys.get(id)});keys.delete(id);view='mine';page=1;await load();message.textContent='Đổi quà thành công.';}catch(error){message.textContent=error.message;b.disabled=false;}});
            }
            if(view==='mine')content.innerHTML=`<ul class="loyalty-history">${data.items.map(r=>`<li><strong>${esc(r.reward.name)}</strong><p>Mã: ${esc(r.code)}</p><p>${esc(statuses[r.status]||r.status)} · Hạn: ${date(r.expires_at)}</p>${r.reward.reward_type==='physical_gift'?'<p>Đến Bin Spa để nhận quà.</p>':'<p>Chọn voucher này khi thanh toán hóa đơn hoặc mua gói.</p>'}</li>`).join('')||'<li>Bạn chưa đổi ưu đãi nào.</li>'}</ul>`;
            if(data.pages>1){const controls=document.createElement('div');controls.className='loyalty-actions';controls.innerHTML=`<button class="btn btn-outline" data-prev ${page===1?'disabled':''}>Trước</button><span>${page} / ${data.pages}</span><button class="btn btn-outline" data-next ${page===data.pages?'disabled':''}>Sau</button>`;controls.querySelector('[data-prev]').onclick=()=>{page--;load();};controls.querySelector('[data-next]').onclick=()=>{page++;load();};content.append(controls);}
        }catch(error){if(token===version)message.textContent=error.message;}
    }
    document.addEventListener('DOMContentLoaded',()=>{
        document.querySelectorAll('[data-loyalty-view]').forEach(b=>b.onclick=()=>{view=b.dataset.loyaltyView;page=1;load();});
        if(location.hash==='#loyalty')load();
    });
    window.CustomerLoyalty={load};
})();
