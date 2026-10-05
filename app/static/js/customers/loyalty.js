/* Customer loyalty: wallet, catalog (Đổi thưởng) and redeemed offers (Ưu đãi của tôi).
   Reserved points are internal to payments and are never shown here. */
(() => {
    const {api,esc,money}=window.LoyaltyPayment;
    const walletLabels={available_points:'Điểm khả dụng',lifetime_earned:'Tổng điểm đã tích',lifetime_redeemed:'Tổng điểm đã dùng'};
    const views=['history','rewards','mine'];
    const groups={usable:'Có thể sử dụng',pickup:'Chờ nhận quà',applied:'Đang áp dụng',done:'Đã sử dụng / Đã nhận',closed:'Hết hạn / Đã hủy',all:'Tất cả'};
    const emptyGroups={usable:'Bạn chưa có voucher nào có thể sử dụng.',pickup:'Không có quà nào đang chờ nhận.',applied:'Không có ưu đãi nào đang áp dụng cho thanh toán.',done:'Chưa có ưu đãi nào đã sử dụng hoặc đã nhận.',closed:'Không có ưu đãi hết hạn hoặc đã hủy.',all:'Bạn chưa đổi ưu đãi nào.'};
    const PENDING='binspa.loyalty.pendingRedeem';
    const date=value=>value?new Date(value).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Không hết hạn';
    const isGift=item=>(item.reward_type||item.reward?.reward_type)==='physical_gift';
    const pct=value=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(Number(value))+'%';
    const isPercent=r=>r.reward_type==='voucher_percent';
    const benefit=r=>isGift(r)?'Quà nhận tại Bin Spa':isPercent(r)?`Giảm ${pct(r.percentage_value)}${r.max_discount_amount?`, tối đa ${money(r.max_discount_amount)}`:''} khi thanh toán`:'Giảm '+money(r.reward_value)+' khi thanh toán';
    // Snapshots redeemed before voucher terms existed have no apply_to/minimum_spend: usable everywhere.
    const scopes={service_invoice:'Hóa đơn dịch vụ',package_purchase:'Mua gói dịch vụ',both:'Dịch vụ và gói'};
    const scopeGuide={service_invoice:'hóa đơn dịch vụ',package_purchase:'mua gói dịch vụ',both:'hóa đơn dịch vụ hoặc mua gói'};
    const minimum=r=>Number(r.minimum_spend||0);
    const validity=r=>r.validity_days?`${r.validity_days} ngày sau khi đổi`:'Không hết hạn';
    const terms=r=>isGift(r)?[['Quyền lợi',esc(benefit(r))]]:[...(isPercent(r)?[['Giảm',pct(r.percentage_value)],['Tối đa',r.max_discount_amount?money(r.max_discount_amount):'Không giới hạn']]:[['Giảm',money(r.reward_value)]]),['Áp dụng',scopes[r.apply_to||'both']],['Đơn tối thiểu',minimum(r)?money(r.minimum_spend):'Không yêu cầu']];
    const newKey=()=>window.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);
    const params=new URLSearchParams(location.search);
    const state={
        view:views.includes(params.get('loyalty_view'))?params.get('loyalty_view'):'history',page:1,version:0,
        balance:null,catalog:new Map(),offers:new Map(),highlight:null,busy:false,toolbar:null,
        filters:{rewards:{search:'',reward_type:'',affordable_only:''},mine:{status:groups[params.get('loyalty_status')]?params.get('loyalty_status'):'usable',reward_type:'',search:''}}
    };
    const el=id=>document.getElementById(id);
    // Hạng xét theo điểm tích từ thanh toán; đổi điểm không làm giảm tiến độ.
    const tierCard=t=>{
        if(!t)return '';
        const next=t.next_tier;
        const pctValue=Math.round(Number(t.progress_percent)||0);
        return `<div class="loyalty-card loyalty-tier-card"><span>Hạng thành viên</span><strong>${esc(t.tier.name)}</strong>`+
            (next?`<div class="loyalty-tier-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pctValue}" aria-label="Tiến độ lên hạng ${esc(next.name)}"><span style="width:${pctValue}%"></span></div>`+
                `<small>Còn ${esc(t.points_to_next)} điểm tích lũy để lên hạng ${esc(next.name)}</small>`
                :'<small>Bạn đang ở hạng cao nhất</small>')+
            `<small class="loyalty-tier-note">${esc(t.qualifying_points)} điểm xét hạng · đổi thưởng không làm giảm hạng</small></div>`;
    };
    const notify=text=>{const m=el('customerLoyaltyMessage');if(m)m.textContent=text;};
    // sessionStorage can be unavailable (private mode); retry protection then lasts for this page only.
    let memoryPending=null;
    const readPending=()=>{try{return JSON.parse(sessionStorage.getItem(PENDING))||memoryPending;}catch{return memoryPending;}};
    const writePending=value=>{memoryPending=value;try{value?sessionStorage.setItem(PENDING,JSON.stringify(value)):sessionStorage.removeItem(PENDING);}catch{}};

    function statusLabel(offer){
        if(offer.status==='available')return isGift(offer)?'Chờ nhận quà':'Có thể sử dụng';
        return {reserved:'Đang áp dụng',used:'Đã sử dụng',fulfilled:'Đã nhận quà',expired:'Đã hết hạn',cancelled:'Đã hủy'}[offer.status]||offer.status;
    }
    const targetRef=o=>o.target_type==='service_invoice'?`hóa đơn HD${String(o.target_id).padStart(6,'0')}`:o.target_type==='package_purchase'?`giao dịch mua gói PG${String(o.target_id).padStart(6,'0')}`:'một giao dịch đang chờ thanh toán';
    function guide(offer){
        switch(offer.status){
        case 'available':return isGift(offer)?'Vui lòng đưa mã này cho nhân viên Bin Spa. Nhân viên sẽ xác nhận khi giao quà.':
            `Khi thanh toán ${scopeGuide[offer.reward.apply_to||'both']}${minimum(offer.reward)?` từ ${money(offer.reward.minimum_spend)}`:''}, chọn voucher này ở mục “Ưu đãi của khách”. Tại quầy, hãy báo nhân viên để được áp dụng.`;
        case 'reserved':return `Đang áp dụng cho ${targetRef(offer)}. Muốn dùng cho giao dịch khác, hãy bỏ voucher ở màn hình thanh toán đó.`;
        case 'used':return 'Voucher đã được dùng lúc '+date(offer.used_at)+'.';
        case 'fulfilled':return 'Bạn đã nhận quà lúc '+date(offer.fulfilled_at)+'.';
        case 'expired':return 'Ưu đãi đã hết hạn và không thể sử dụng hoặc nhận quà.';
        default:return 'Ưu đãi đã bị hủy.';
        }
    }

    function dialog(){
        let d=el('loyaltyRewardDialog');
        if(!d){d=document.createElement('dialog');d.id='loyaltyRewardDialog';d.className='loyalty-dialog loyalty-reward-dialog';d.setAttribute('aria-labelledby','loyaltyDialogTitle');document.body.append(d);}
        return d;
    }
    const facts=rows=>`<dl class="loyalty-facts">${rows.filter(Boolean).map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;

    function openConfirm(reward){
        const d=dialog(),available=state.balance?.available_points??0,pending=readPending();
        // An unresolved request for this reward is retried with its original key so it can never be applied twice.
        const retry=pending?.reward_id===reward.id;
        const key=retry?pending.key:newKey();
        d.innerHTML=`<h3 id="loyaltyDialogTitle">Xác nhận đổi thưởng</h3><span class="loyalty-badge">${isGift(reward)?'Quà tặng':'Voucher'}</span><h4>${esc(reward.name)}</h4>${reward.description?`<p class="loyalty-muted">${esc(reward.description)}</p>`:''}`+
            facts([['Điểm hiện có',`${available} điểm`],['Điểm dùng',`${reward.points_cost} điểm`],!retry&&['Điểm còn lại',`${available-reward.points_cost} điểm`],...terms(reward),['Hạn sử dụng',validity(reward)]])+
            `<p>${isGift(reward)?'Sau khi đổi, mang mã ưu đãi tới Bin Spa để nhận quà.':'Sau khi đổi, chọn voucher ở bước thanh toán hóa đơn hoặc mua gói.'}</p>`+
            (retry?'<p class="loyalty-warn">Yêu cầu đổi trước đó chưa xác nhận được kết quả. Xác nhận lần này chỉ kiểm tra lại, không trừ điểm hai lần.</p>':'')+
            `<p data-dialog-message class="loyalty-error" role="alert"></p><div class="loyalty-actions"><button type="button" class="btn btn-outline" data-cancel>Hủy</button><button type="button" class="btn btn-primary" data-confirm>Xác nhận đổi</button></div>`;
        d.querySelector('[data-cancel]').onclick=()=>d.close();
        d.querySelector('[data-confirm]').onclick=event=>submit(reward,key,event.currentTarget);
        d.showModal();d.querySelector('[data-confirm]').focus();
    }

    async function submit(reward,key,button){
        if(state.busy)return;
        state.busy=true;button.disabled=true;button.textContent='Đang xử lý...';
        const d=dialog(),note=d.querySelector('[data-dialog-message]');note.textContent='';
        writePending({reward_id:reward.id,key,name:reward.name,reward});
        try{
            const {redemption}=await api(`/api/loyalty/rewards/${reward.id}/redeem`,'POST',{idempotency_key:key});
            writePending(null);
            Object.assign(state.filters.mine,{status:isGift(redemption)?'pickup':'usable',reward_type:'',search:''});
            state.highlight=redemption.id;
            // The list behind the dialog switches to the new offer; the reload also refreshes the balance.
            await setView('mine');
            notify(`Đổi “${redemption.reward.name}” thành công. Mã ưu đãi: ${redemption.code}.`);
            if(d.open)showSuccess(redemption);
        }catch(error){
            // No status (network), 5xx or 409: the server may have processed it, so keep the key for a safe retry.
            const unknown=!error.status||error.status>=500||error.status===409;
            const text=unknown?'Chưa xác nhận được kết quả đổi quà. Bấm “Thử lại” để kiểm tra; điểm sẽ không bị trừ hai lần.':error.message;
            if(!unknown)writePending(null);
            if(d.open){note.textContent=text;button.textContent=unknown?'Thử lại':'Xác nhận đổi';button.disabled=!unknown;}
            notify(text);
            if(!unknown)load();
        }finally{state.busy=false;}
    }

    function showSuccess(redemption){
        const d=dialog(),r=redemption.reward;
        d.innerHTML=`<h3 id="loyaltyDialogTitle">Đổi thưởng thành công</h3><div role="status" data-success><span class="loyalty-badge">${isGift(r)?'Quà tặng':'Voucher'}</span>`+
            facts([[isGift(r)?'Quà':'Voucher',esc(r.name)],['Mã ưu đãi',`<code>${esc(redemption.code)}</code>`],['Điểm đã dùng',`${redemption.points_spent} điểm`],
                state.balance&&['Điểm còn lại',`${esc(state.balance.available_points)} điểm`],...terms(r),['Hạn sử dụng',date(redemption.expires_at)]])+
            `<p>${esc(guide(redemption))}</p></div><div class="loyalty-actions"><button type="button" class="btn btn-primary" data-view-offers>Xem ưu đãi của tôi</button></div>`;
        const open=d.querySelector('[data-view-offers]');
        open.onclick=()=>{
            d.close();
            const card=document.querySelector(`[data-offer="${redemption.id}"]`);
            if(card){card.classList.add('is-new');card.scrollIntoView?.({block:'nearest'});card.focus({preventScroll:true});}
        };
        open.focus();
    }

    function openDetail(offer){
        const d=dialog(),r=offer.reward;
        d.innerHTML=`<h3 id="loyaltyDialogTitle">${esc(r.name)}</h3><span class="loyalty-badge">${isGift(offer)?'Quà tặng':'Voucher'}</span> <span class="loyalty-status loyalty-status--${esc(offer.status)}">${esc(statusLabel(offer))}</span>${r.description?`<p class="loyalty-muted">${esc(r.description)}</p>`:''}`+
            facts([...terms(r),['Mã ưu đãi',`<code>${esc(offer.code)}</code>`],['Điểm đã đổi',`${offer.points_spent} điểm`],['Ngày đổi',date(offer.redeemed_at)],['Hạn sử dụng',date(offer.expires_at)],
                offer.used_at&&['Đã sử dụng',date(offer.used_at)],offer.fulfilled_at&&['Đã nhận quà',date(offer.fulfilled_at)],offer.status==='reserved'&&['Đang áp dụng cho',esc(targetRef(offer))]])+
            `<p>${esc(guide(offer))}</p><div class="loyalty-actions">${['available','reserved'].includes(offer.status)?`<button type="button" class="btn btn-outline" data-copy="${esc(offer.code)}">Sao chép mã</button>`:''}<button type="button" class="btn btn-primary" data-close>Đóng</button></div>`;
        d.querySelector('[data-close]').onclick=()=>d.close();
        bindCopy(d);d.showModal();d.querySelector('[data-close]').focus();
    }

    function bindCopy(root){
        root.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{
            const code=b.dataset.copy;
            try{await navigator.clipboard.writeText(code);notify(`Đã sao chép mã ${code}.`);b.textContent='Đã sao chép';}
            catch{notify(`Không thể sao chép tự động. Mã của bạn: ${code}`);}
        });
    }

    function saveUrl(){
        const url=new URL(location.href);
        if(state.view==='history')url.searchParams.delete('loyalty_view');else url.searchParams.set('loyalty_view',state.view);
        if(state.view==='mine')url.searchParams.set('loyalty_status',state.filters.mine.status);else url.searchParams.delete('loyalty_status');
        url.hash='loyalty';
        history.replaceState(history.state,'',url);
    }

    function syncTabs(){
        document.querySelectorAll('[data-loyalty-view]').forEach(b=>{
            const active=b.dataset.loyaltyView===state.view;
            b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;
            b.classList.toggle('btn-primary',active);b.classList.toggle('btn-outline',!active);
        });
    }

    function renderToolbar(content){
        if(state.toolbar===state.view&&content.querySelector('[data-list]'))return;
        state.toolbar=state.view;
        const f=state.filters[state.view];
        const typeSelect=`<label>Loại<select name="reward_type"><option value="">Tất cả</option><option value="voucher" ${f?.reward_type==='voucher'?'selected':''}>Voucher</option><option value="physical_gift" ${f?.reward_type==='physical_gift'?'selected':''}>Quà tặng</option></select></label>`;
        let toolbar='';
        if(state.view==='rewards')toolbar=`<form class="loyalty-toolbar" data-filter role="search"><label>Tìm quà<input type="search" name="search" maxlength="100" value="${esc(f.search)}" placeholder="Tên quà"></label>${typeSelect}<label class="loyalty-check"><input type="checkbox" name="affordable_only" value="1" ${f.affordable_only?'checked':''}> Chỉ quà đủ điểm</label><button class="btn btn-outline">Tìm</button></form>`;
        if(state.view==='mine')toolbar=`<div class="loyalty-chips" role="group" aria-label="Lọc theo trạng thái">${Object.entries(groups).map(([k,v])=>`<button type="button" class="loyalty-chip" data-group="${k}" aria-pressed="${k===f.status}">${v}</button>`).join('')}</div><form class="loyalty-toolbar" data-filter role="search"><label>Tìm ưu đãi<input type="search" name="search" maxlength="100" value="${esc(f.search)}" placeholder="Tên hoặc mã"></label>${typeSelect}<button class="btn btn-outline">Tìm</button></form>`;
        content.innerHTML=`${toolbar}<div data-pending></div><div data-list aria-live="polite"></div><div data-pager></div>`;
        const form=content.querySelector('[data-filter]');
        if(form){
            const apply=()=>{const data=new FormData(form);Object.assign(f,{search:String(data.get('search')||'').trim(),reward_type:data.get('reward_type')||''});if(state.view==='rewards')f.affordable_only=data.get('affordable_only')?'1':'';state.page=1;load();};
            form.onsubmit=event=>{event.preventDefault();apply();};
            form.querySelectorAll('select,input[type=checkbox]').forEach(i=>i.onchange=apply);
        }
        content.querySelectorAll('[data-group]').forEach(b=>b.onclick=()=>{
            f.status=b.dataset.group;state.page=1;
            content.querySelectorAll('[data-group]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
            saveUrl();load();
        });
    }

    function renderPending(content){
        const host=content.querySelector('[data-pending]'),pending=readPending();
        if(!host)return;
        host.innerHTML=state.view==='rewards'&&pending?`<div class="loyalty-notice" role="status"><p>Yêu cầu đổi “${esc(pending.name)}” chưa xác nhận được kết quả.</p><button type="button" class="btn btn-primary" data-pending-retry>Kiểm tra lại</button><button type="button" class="btn btn-outline" data-pending-drop>Bỏ qua</button></div>`:'';
        const retry=host.querySelector('[data-pending-retry]');
        if(retry)retry.onclick=()=>openConfirm(state.catalog.get(pending.reward_id)||pending.reward);
        const drop=host.querySelector('[data-pending-drop]');
        if(drop)drop.onclick=()=>{writePending(null);host.innerHTML='';};
    }

    function rewardCard(r,available=state.balance?.available_points??0){
        const missing=Math.max(0,r.points_cost-available),soldOut=r.stock===0;
        return `<article class="loyalty-card loyalty-reward"><span class="loyalty-badge">${isGift(r)?'Quà tặng':'Voucher'}</span><h3>${esc(r.name)}</h3>${r.description?`<p class="loyalty-muted">${esc(r.description)}</p>`:''}`+
            facts([['Điểm cần đổi',`${r.points_cost} điểm`],...terms(r),['Hạn',validity(r)],['Tình trạng',soldOut?'Hết quà':r.stock==null?'Còn quà':`Còn ${r.stock} quà`]])+
            (missing&&!soldOut?`<p class="loyalty-warn">Cần thêm ${missing} điểm</p>`:'')+
            `<button type="button" class="btn btn-primary" data-redeem="${r.id}" ${missing||soldOut?'disabled':''}>${soldOut?'Hết quà':missing?'Chưa đủ điểm':'Đổi ngay'}</button></article>`;
    }

    function offerCard(o){
        const active=['available','reserved'].includes(o.status);
        const resume=o.status==='reserved'?(o.target_type==='service_invoice'?`<button type="button" class="btn btn-outline" data-resume-invoice="${o.target_id}">Tiếp tục thanh toán</button>`:o.target_type==='package_purchase'?`<a class="btn btn-outline" href="/packages?purchase=${o.target_id}">Tiếp tục thanh toán</a>`:''):'';
        return `<article class="loyalty-card loyalty-offer${o.id===state.highlight?' is-new':''}" data-offer="${o.id}" tabindex="-1"><div class="loyalty-offer-head"><span class="loyalty-badge">${isGift(o)?'Quà tặng':'Voucher'}</span><span class="loyalty-status loyalty-status--${esc(o.status)}">${esc(statusLabel(o))}</span></div>`+
            `<h3>${esc(o.reward.name)}</h3><p class="loyalty-code">Mã ưu đãi: <code>${esc(o.code)}</code>${active?` <button type="button" class="btn btn-outline btn-sm" data-copy="${esc(o.code)}">Sao chép</button>`:''}</p>`+
            facts([...terms(o.reward),['Ngày đổi',date(o.redeemed_at)],['Hạn dùng',date(o.expires_at)],o.used_at&&['Ngày sử dụng',date(o.used_at)],o.fulfilled_at&&['Ngày nhận quà',date(o.fulfilled_at)]])+`<p>${esc(guide(o))}</p><div class="loyalty-actions"><button type="button" class="btn btn-outline" data-detail="${o.id}">Chi tiết</button>${resume}</div></article>`;
    }

    function query(){
        const f=state.filters[state.view]||{},q=new URLSearchParams({page:state.page});
        for(const [k,v] of Object.entries(f))if(v)q.set(k,v);
        return q;
    }

    async function load(){
        const token=++state.version,content=el('customerLoyaltyContent');
        if(!content)return;
        syncTabs();renderToolbar(content);renderPending(content);
        const list=content.querySelector('[data-list]'),pager=content.querySelector('[data-pager]');
        list.setAttribute('aria-busy','true');
        if(!list.children.length)list.innerHTML='<p class="loyalty-state">Đang tải...</p>';
        try{
            const endpoint={history:'/api/loyalty/me/transactions',rewards:'/api/loyalty/rewards',mine:'/api/loyalty/my-rewards'}[state.view];
            const [me,data]=await Promise.all([api('/api/loyalty/me'),api(endpoint+'?'+query())]);
            if(token!==state.version)return;
            state.balance=me.wallet;
            el('loyaltyBalance').innerHTML=tierCard(me.tier)+Object.entries(walletLabels).map(([k,label])=>`<div class="loyalty-card"><span>${label}</span><strong>${esc(state.balance[k])}</strong></div>`).join('');
            const filtered=Object.entries(state.filters[state.view]||{}).some(([k,v])=>k!=='status'&&v);
            if(state.view==='history')list.innerHTML=`<ul class="loyalty-history">${data.items.map(t=>`<li><strong>${t.points_delta>0?'+':''}${t.points_delta} điểm</strong><p>${esc(t.description)}</p><small>${date(t.created_at)}</small></li>`).join('')||'<li>Bạn chưa có lịch sử điểm.</li>'}</ul>`;
            if(state.view==='rewards'){
                state.catalog=new Map(data.items.map(r=>[r.id,r]));
                list.innerHTML=data.items.length?`<div class="loyalty-cards loyalty-grid">${data.items.map(r=>rewardCard(r)).join('')}</div>`:`<p class="loyalty-state">${filtered?'Không có quà phù hợp với bộ lọc.':'Chưa có quà đổi thưởng.'}</p>`;
                list.querySelectorAll('[data-redeem]').forEach(b=>b.onclick=()=>openConfirm(state.catalog.get(Number(b.dataset.redeem))));
            }
            if(state.view==='mine'){
                state.offers=new Map(data.items.map(o=>[o.id,o]));
                const status=state.filters.mine.status;
                list.innerHTML=data.items.length?`<div class="loyalty-cards loyalty-grid">${data.items.map(offerCard).join('')}</div>`:
                    `<div class="loyalty-state"><p>${filtered?'Không tìm thấy ưu đãi phù hợp với bộ lọc.':emptyGroups[status]}</p>${!filtered&&['usable','all'].includes(status)?'<button type="button" class="btn btn-primary" data-goto="rewards">Xem quà đổi thưởng</button>':''}</div>`;
                list.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>openDetail(state.offers.get(Number(b.dataset.detail))));
                list.querySelectorAll('[data-resume-invoice]').forEach(b=>b.onclick=async()=>{try{await window.LoyaltyPayment.openCustomerInvoice(Number(b.dataset.resumeInvoice));}catch(error){notify(error.message);}});
                list.querySelector('[data-goto]')?.addEventListener('click',()=>setView('rewards'));
                bindCopy(list);
                const fresh=state.highlight&&list.querySelector(`[data-offer="${state.highlight}"]`);
                if(fresh){fresh.scrollIntoView?.({block:'nearest'});fresh.focus({preventScroll:true});}
                state.highlight=null;
            }
            pager.innerHTML=data.pages>1?`<nav class="loyalty-actions" aria-label="Phân trang"><button type="button" class="btn btn-outline" data-prev ${state.page<=1?'disabled':''}>Trước</button><span>Trang ${data.page} / ${data.pages} · ${data.total} mục</span><button type="button" class="btn btn-outline" data-next ${state.page>=data.pages?'disabled':''}>Sau</button></nav>`:'';
            pager.querySelector('[data-prev]')?.addEventListener('click',()=>{state.page--;load();});
            pager.querySelector('[data-next]')?.addEventListener('click',()=>{state.page++;load();});
        }catch(error){
            if(token!==state.version)return;
            list.innerHTML=`<div class="loyalty-state loyalty-error" role="alert"><p>${esc(error.message||'Không thể tải dữ liệu điểm thưởng.')}</p><button type="button" class="btn btn-outline" data-reload>Thử lại</button></div>`;
            list.querySelector('[data-reload]').onclick=()=>load();
        }finally{if(token===state.version)list.removeAttribute('aria-busy');}
    }

    function setView(view){
        if(!views.includes(view))return;
        state.view=view;state.page=1;state.toolbar=null;
        saveUrl();return load();
    }

    document.addEventListener('DOMContentLoaded',()=>{
        const tabs=[...document.querySelectorAll('[data-loyalty-view]')];
        tabs.forEach((b,i)=>{
            b.onclick=()=>{notify('');setView(b.dataset.loyaltyView);};
            b.onkeydown=event=>{
                const step={ArrowRight:1,ArrowLeft:-1}[event.key];
                if(!step)return;
                event.preventDefault();const next=tabs[(i+step+tabs.length)%tabs.length];next.focus();next.click();
            };
        });
        syncTabs();
    });
    // Coming back to the tab (e.g. after paying elsewhere) must not show stale balances or statuses.
    document.addEventListener('visibilitychange',()=>{
        if(!document.hidden&&el('loyalty-section')?.classList.contains('active')&&!el('loyaltyRewardDialog')?.open)load();
    });
    window.CustomerLoyalty={load,setView,render:{rewardCard,offerCard,statusLabel}};
})();
