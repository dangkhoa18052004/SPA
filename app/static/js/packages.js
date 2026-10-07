(() => {
    'use strict';
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const price = value => new Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'}).format(Number(value));
    const date = value => value ? new Date(value).toLocaleDateString('vi-VN') : '';
    const status = value => ({active:'Đang hoạt động', used_up:'Đã dùng hết', expired:'Hết hạn',cancelled:'Đã hủy',pending:'Chờ thanh toán',paid:'Đã thanh toán',failed:'Thất bại',reserved:'Đang giữ',consumed:'Đã sử dụng',released:'Đã trả lại'}[value] || value);
    const isAdmin = () => document.querySelector('[data-package-page="admin"], [data-package-page="sales"]');
    async function api(url, method='GET', data) {
        const form = typeof FormData !== 'undefined' && data instanceof FormData;
        const headers = isAdmin() ? window.getAuthHeaders(!form) : (form ? {} : {'Content-Type':'application/json'});
        const fetcher = !isAdmin() && window.CustomerAuth ? window.CustomerAuth.fetch.bind(window.CustomerAuth) : fetch;
        const response = await fetcher(url,{method,headers, ...(data ? {body:form ? data : JSON.stringify(data)} : {})});
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.toLowerCase().includes('application/json')) {
            console.error('Package API expected JSON:', url, response.status, contentType);
            throw new Error('Không thể tải dữ liệu. Vui lòng thử lại.');
        }
        let result;
        try {
            result = await response.json();
        } catch (error) {
            console.error('Package API returned invalid JSON:', url, response.status);
            throw new Error('Không thể tải dữ liệu. Vui lòng thử lại.');
        }
        if (!response.ok) throw new Error(result.message || result.msg || 'Không thể tải dữ liệu');
        return result;
    }
    function message(text) { const el=document.getElementById('packageMessage'); if(el) el.textContent=text; }
    const validity = months => months == null ? 'Vô thời hạn' : `${months} tháng từ khi kích hoạt`;
    const cover = p => `<img class="package-cover" src="${esc(p.image_url || '/static/images/default-package.svg')}" alt="${esc(p.tengoi)}" loading="lazy" onerror="this.onerror=null;this.src='/static/images/default-package.svg'">`;
    const packageHtml = (p, saleBadge = '') => `<article class="package-panel package-card">${cover(p)}<div class="package-card-body">${saleBadge}<span class="package-badge">${Number(p.savings)>0?'Tiết kiệm '+price(p.savings):validity(p.validity_months)}</span><h3>${esc(p.tengoi)}</h3><p class="package-description">${esc(p.mota)}</p><ul class="package-service-list">${p.items.map(i=>`<li><span>${esc(i.tendv)}</span><strong>${i.total_sessions} buổi</strong><small>${price(i.regular_unit_price_snapshot)}/buổi</small></li>`).join('')}</ul><p class="package-retail">Giá lẻ tổng: ${price(p.regular_total)}</p><p class="package-price">${price(p.giagoi)}</p>${Number(p.savings)>0?`<p class="package-saving">Tiết kiệm: ${price(p.savings)}</p>`:''}<p class="package-validity">${validity(p.validity_months)}</p></div>`;
    let pollTimer, pollCount=0;
    async function showPayment(purchase) {
        const panel=document.getElementById('packagePayment');
        if (!panel) return;
        panel.classList.remove('package-hidden');
        const dialog=document.getElementById('packagePaymentDialog');
        if(dialog && !dialog.open) dialog.showModal();
        if (purchase.status==='paid') {
            panel.innerHTML='<h2>Thanh toán thành công</h2><p>Liệu trình của bạn đã được kích hoạt.</p>'+(window.LoyaltyPayment?LoyaltyPayment.summary(purchase):'')+(!isAdmin()?'<a class="btn btn-primary" href="/profile#treatments">Liệu trình của tôi</a>':'');
            clearInterval(pollTimer); document.dispatchEvent(new CustomEvent('package:paid',{detail:purchase})); return;
        }
        const payment=purchase.payment;
        const payable=purchase.payable_amount ?? purchase.amount;
        const zero=Number(payable)===0;
        panel.innerHTML=`<h2>${esc(purchase.tengoi)} · PKG${purchase.id}</h2><p>${esc(status(purchase.status))}</p>`+
            (window.LoyaltyPayment?'<div data-package-loyalty></div>':`<p>${price(payable)}</p>`)+
            (zero ? '<button type="button" class="btn btn-primary" data-pay-points>Thanh toán bằng điểm</button>' :
            payment ? `<button type="button" class="btn btn-primary" data-reveal-qr>Tiếp tục thanh toán VietQR</button><div data-package-qr hidden><img src="${esc(payment.qrCodeUrl)}" alt="Mã VietQR thanh toán gói"><p>${esc(payment.account_name)} · ${esc(payment.account_no)} · ${esc(payment.bank_id)}</p><p>Nội dung chuyển khoản: <strong>${esc(payment.description)}</strong></p><p>Chuyển đúng ${price(payment.amount)}. Liệu trình chỉ kích hoạt khi ngân hàng xác nhận.</p></div>` :
            purchase.payment_method==='vietqr'?'<p>VietQR tạm thời chưa khả dụng. Vui lòng liên hệ cửa hàng.</p>':
            isAdmin()?`<form data-package-cash><label>Số tiền khách đưa<input type="number" min="${esc(payable)}" step="1" value="${esc(payable)}" required></label><p data-cash-change></p><button type="submit" class="btn btn-primary">Xác nhận đã nhận tiền</button></form>`:'<p>Vui lòng đến quầy thanh toán. Nhân viên xác nhận đã nhận tiền để kích hoạt liệu trình.</p>')+
            '<button type="button" class="btn btn-secondary" id="checkPackagePayment">Kiểm tra thanh toán</button>';
        const endpoint=isAdmin()?`/api/admin/package-sales/${purchase.id}/status`:`/api/packages/purchases/${purchase.id}/status`;
        const base=isAdmin()?`/api/admin/packages/purchases/${purchase.id}`:`/api/packages/purchases/${purchase.id}`;
        const reload=async()=>showPayment((await api(endpoint)).purchase);
        const reveal=panel.querySelector('[data-reveal-qr]');
        if(reveal) reveal.onclick=()=>{panel.querySelector('[data-package-qr]').hidden=false;reveal.hidden=true;};
        const pointButton=panel.querySelector('[data-pay-points]');
        if(pointButton) pointButton.onclick=async()=>{pointButton.disabled=true;try{await api(base+'/pay-points','POST',{});await reload();}catch(e){message(e.message);pointButton.disabled=false;}};
        const cashForm=panel.querySelector('[data-package-cash]');
        if(cashForm){
            const input=cashForm.querySelector('input');
            input.oninput=()=>cashForm.querySelector('[data-cash-change]').textContent='Tiền thối: '+price(Math.max(0,Number(input.value)-Number(payable)));
            cashForm.onsubmit=async e=>{e.preventDefault();const b=cashForm.querySelector('button');b.disabled=true;try{await api(base+'/confirm-payment','POST',{cash_received:input.value});await reload();}catch(error){message(error.message);b.disabled=false;}};
        }
        document.getElementById('checkPackagePayment').onclick=()=>api(endpoint).then(r=>{
            if (!dialog || dialog.open) return showPayment(r.purchase);
        }).catch(e=>message(e.message));
        clearInterval(pollTimer);pollCount=0;
        pollTimer=setInterval(async()=>{
            if(++pollCount>60){clearInterval(pollTimer);panel.insertAdjacentHTML('beforeend','<p>Đã dừng chờ tự động. Bạn có thể kiểm tra lại thanh toán.</p>');return;}
            try{const r=await api(endpoint);if(dialog && !dialog.open)return;if(r.purchase.status==='paid')await showPayment(r.purchase);else if(r.purchase.status!=='pending'){clearInterval(pollTimer);message(status(r.purchase.status));}}
            catch(e){clearInterval(pollTimer);message(e.message);}
        },5000);
        if(window.LoyaltyPayment) await LoyaltyPayment.mount(panel.querySelector('[data-package-loyalty]'),base,purchase.makh,reload);
    }
    // Đăng nhập = có access token. Phiên server còn nhưng mất token (hết hạn, xóa storage) → khôi phục từ phiên,
    // tránh vòng lặp: hiện hộp đăng nhập → /auth/login thấy phiên hợp lệ → trả về trang gói mà không mua được.
    async function customerLoggedIn() {
        const auth=window.CustomerAuth;
        let token=auth?auth.getAccessToken():localStorage.getItem('access_token');
        if(!token && auth) token=await auth.restoreAccessToken();
        return !!token;
    }
    // Giống trang đặt lịch: yêu cầu đăng nhập, sau đó quay lại trang gói và tiếp tục mua đúng gói đã chọn.
    function requireLogin(id) {
        const page=document.querySelector('[data-package-page="customer"]');
        const modal=document.getElementById('packageLoginModal');
        if(!modal){location.href='/auth/login';return;}
        const back=new URL(location.href);back.searchParams.set('buy',id);
        modal.querySelector('[data-login-link]').href=`${page.dataset.loginUrl||'/auth/login'}?redirect=${encodeURIComponent(back.pathname+back.search)}`;
        modal.hidden=false;
        modal.querySelector('[data-login-link]').focus();
        const close=()=>{modal.hidden=true;document.removeEventListener('keydown',onKey);};
        const onKey=e=>{if(e.key==='Escape')close();};
        document.addEventListener('keydown',onKey);
        modal.querySelector('[data-login-close]').onclick=close;
        modal.onclick=e=>{if(e.target===modal)close();};
    }
    async function buy(id) {
        if(!(await customerLoggedIn())) return requireLogin(id);
        try {
            // Khách mua online chỉ thanh toán VietQR (bán tiền mặt do nhân viên tạo tại quầy).
            const result=await api(`/api/packages/${id}/purchase`,'POST',{payment_method:'vietqr'});
            await showPayment(result.purchase);
        } catch(e){
            if(/đăng nhập|token|401/i.test(e.message)) return requireLogin(id);
            message(e.message);
        }
    }
    async function loadCustomerPackages() {
        const page=document.querySelector('[data-package-page="customer"]');
        const id=page.dataset.packageId;
        try {
            const options=await api('/api/packages/payment-options');
            const result=await api(id?`/api/packages/${id}`:'/api/packages');
            const packages=(result.packages || [result.package]).filter(p=>p.active && p.customer_sale_enabled);
            document.getElementById('packageList').innerHTML=packages.length?packages.map(p=>packageHtml(p)+
                `<div class="package-card-actions">${!id?`<a class="btn btn-secondary" href="/packages/${p.magoi}">Xem chi tiết</a>`:''}<p class="package-pay-method"><i class="fas fa-qrcode" aria-hidden="true"></i> Thanh toán chuyển khoản VietQR</p>${options.vietqr_available?`<button type="button" class="btn btn-primary" data-buy="${p.magoi}">Mua gói</button>`:'<button type="button" class="btn btn-primary" disabled title="VietQR đang tạm ngưng">Tạm ngưng bán online</button>'}</div></article>`).join(''):'Chưa có gói dịch vụ đang bán.';
            document.querySelectorAll('[data-buy]').forEach(b=>b.onclick=()=>{b.disabled=true;buy(Number(b.dataset.buy)).finally(()=>b.disabled=false);});
            // Vừa đăng nhập xong từ hộp "Vui lòng đăng nhập": tiếp tục mua gói đã chọn.
            const resume=Number(new URLSearchParams(location.search).get('buy'));
            if(resume>0 && packages.some(p=>p.magoi===resume) && await customerLoggedIn()){
                history.replaceState(null,'',location.pathname);
                await buy(resume);
            }
            const pending=new URLSearchParams(location.search).get('purchase');
            if(pending) await showPayment((await api(`/api/packages/purchases/${Number(pending)}`)).purchase);
        } catch(e){message(e.message);}
    }
    function treatmentHtml(t, admin=false) {
        const sections = ['package', 'gift'].map(source => {
            const items=t.items.filter(i=>(i.source_type||'package')===source);
            return items.length?`<h4>${source==='gift'?'🎁 Dịch vụ tặng':'Dịch vụ trong gói'}</h4><ul class="treatment-services">${items.map(i=>`<li><strong>${esc(i.tendv)}</strong><p>${source==='gift'?'Miễn phí · ':''}Đã dùng: ${i.consumed}/${i.total_sessions} · Đang giữ: ${i.reserved} · Còn: ${i.available_sessions}</p><p>Hạn: ${i.effective_expires_at?date(i.effective_expires_at):'Vô thời hạn'}${i.usable===false?' · Không còn khả dụng':''}</p><progress value="${i.consumed}" max="${i.total_sessions}" aria-label="Số buổi đã sử dụng"></progress>${!admin&&i.usable!==false&&i.available_sessions>0?`<a class="btn btn-primary" href="/appointments/create?treatment=${t.mathe}&service=${i.madv}&item=${i.id}">Đặt lịch</a>`:''}</li>`).join('')}</ul>`:'';
        }).join('');
        return `<article class="package-panel treatment-card">${cover(t)}<div class="package-card-body"><span class="package-badge">${esc(status(t.status))}</span><h3>${esc(t.tengoi)}</h3><p>Mã liệu trình #${t.mathe}</p>${admin?`<p>${esc(t.customer_name)} · ${esc(t.phone)}</p>`:''}<div class="treatment-dates"><p>Ngày mua: ${date(t.purchased_at)}</p><p>Kích hoạt: ${date(t.activated_at)}</p><p>Hạn gói gốc: ${t.expires_at?date(t.expires_at):'Vô thời hạn'}</p></div>${sections}</div>`+
            (admin ? `<details><summary>Lịch sử sử dụng</summary>${historyHtml(t.history || [])}</details>`:
            `<button type="button" class="btn btn-secondary" data-history="${t.mathe}">Xem lịch sử</button><div id="history-${t.mathe}" class="package-history"></div>`)+`</article>`;
    }
    const historyHtml = rows => rows.length?`<ul>${rows.map(u=>`<li>Lịch hẹn #${u.malh} · ${esc(u.tendv||'Dịch vụ #'+u.madv)} · ${u.source_type==='gift'?'🎁 Lượt tặng':'Trong gói'} #${u.the_item_id} · ${esc(status(u.state))} · ${date(u.consumed_at || u.released_at || u.reserved_at)}</li>`).join('')}</ul>`:'Chưa có lịch sử sử dụng.';
    async function loadTreatments() {
        const list=document.getElementById('myTreatments'); if(!list)return;
        try {
            const r=await api('/api/packages/my-treatments');
            list.innerHTML=r.treatments.length?r.treatments.map(t=>treatmentHtml(t)).join(''):'<div class="package-empty"><h3>Bạn chưa có liệu trình nào.</h3><a class="btn btn-primary" href="/packages">Mua gói dịch vụ</a></div>';
            list.querySelectorAll('[data-history]').forEach(b=>b.onclick=async()=>{
                try {const t=(await api(`/api/packages/my-treatments/${b.dataset.history}`)).treatment;document.getElementById(`history-${b.dataset.history}`).innerHTML=historyHtml(t.history);}catch(e){b.textContent=e.message;}
            });
            const purchases=await api('/api/packages/my-purchases');
            document.getElementById('myPackagePurchases').innerHTML=purchases.purchases.filter(p=>p.status==='pending').map(p=>`<p>${esc(p.tengoi)} · ${price(p.payable_amount ?? p.amount)} · Chờ thanh toán <a href="/packages?purchase=${p.id}">Tiếp tục thanh toán</a></p>`).join('');
        } catch(e){list.textContent=e.message;}
    }
    let treatmentSelections=new Map(), renderVersion=0, lastBookingKey='', bookingRequest;
    function chooseBookingItem(treatment, item) {
        treatmentSelections.set(Number(item.madv), {mathe:Number(treatment.mathe), the_item_id:Number(item.id), madv:Number(item.madv), quantity:1});
        lastBookingKey='';
    }
    async function renderBooking(serviceIds, selectedDate) {
        const el=document.getElementById('bookingTreatments');if(!el)return;
        const key=JSON.stringify([serviceIds,selectedDate]);
        if(key===lastBookingKey)return bookingRequest?.catch(()=>undefined);
        lastBookingKey=key;
        treatmentSelections=new Map([...treatmentSelections].filter(([id])=>serviceIds.includes(id)));
        const version=++renderVersion;
        try {
            bookingRequest=api('/api/packages/my-treatments');
            const r=await bookingRequest; if(version!==renderVersion)return;
            const choices=serviceIds.map(id=>({id,items:r.treatments.flatMap(t=>t.status==='cancelled'?[]:t.items.filter(i=>i.madv===id&&i.usable!==false&&i.available_sessions>0&&(!selectedDate||(!i.effective_expires_at||i.effective_expires_at.slice(0,10)>=selectedDate)&&(!i.valid_from||i.valid_from.slice(0,10)<=selectedDate))).map(item=>({treatment:t,item})))}));
            const previous=JSON.stringify([...treatmentSelections]);
            treatmentSelections=new Map([...treatmentSelections].filter(([id,usage])=>choices.some(c=>c.id===id&&c.items.some(({item})=>item.id===usage.the_item_id))));
            el.innerHTML=choices.filter(c=>c.items.length).map(c=>`<label>${esc(c.items[0].item.tendv)}<select data-treatment-service="${c.id}"><option value="">Thanh toán bình thường</option>${c.items.map(({treatment:t,item:i})=>`<option value="${i.id}" ${treatmentSelections.get(c.id)?.the_item_id===i.id?'selected':''}>${i.source_type==='gift'?'🎁 Dịch vụ tặng':'Sử dụng liệu trình'}: ${esc(t.tengoi)} — Còn ${i.available_sessions} buổi</option>`).join('')}</select></label>`).join('');
            el.classList.toggle('package-hidden',!el.innerHTML);
            el.querySelectorAll('select').forEach(select=>select.onchange=()=>{const id=Number(select.dataset.treatmentService);const choice=choices.find(c=>c.id===id)?.items.find(c=>c.item.id===Number(select.value));choice?treatmentSelections.set(id,{mathe:choice.treatment.mathe,the_item_id:choice.item.id,madv:id,quantity:1}):treatmentSelections.delete(id);window.refreshBookingSummary?.();});
            if(previous!==JSON.stringify([...treatmentSelections])) window.refreshBookingSummary?.();
        } catch(e){
            if(version!==renderVersion)return;
            // Preserve an explicit entitlement choice; the backend validates it again.
            // A transient list failure must never silently turn a free booking into retail billing.
            el.classList.remove('package-hidden');
            el.textContent='Không thể tải liệu trình. Vui lòng thử lại trước khi sử dụng lượt gói.';
            const retry=document.createElement('button');retry.type='button';retry.className='btn btn-secondary';retry.textContent='Thử lại';
            retry.onclick=()=>{lastBookingKey='';renderBooking(serviceIds,selectedDate);};el.append(retry);
        }
    }
    let adminPackages=[], services=[], editId=null;
    function addItem(item={}) {
        const row=document.createElement('div');row.className='package-item-row';
        row.innerHTML=`<label>Dịch vụ<select class="package-service">${services.map(s=>`<option value="${s.madv}" ${s.madv===item.madv?'selected':''}>${esc(s.tendv)}</option>`).join('')}</select></label><label>Số buổi<input class="package-sessions" type="number" min="1" step="1" value="${item.total_sessions || 1}" required></label><button type="button" class="btn btn-secondary">Bỏ</button>`;
        row.querySelector('button').onclick=()=>{row.remove();priceWarning();};document.getElementById('packageItems').append(row);priceWarning();
    }
    function editPackage(p) {
        editId=p.magoi;const form=document.getElementById('packageForm');
        for(const name of ['tengoi','mota','giagoi','validity_months'])form.elements[name].value=p[name]||'';
        form.elements.active.checked=p.active;document.getElementById('packageItems').innerHTML='';p.items.forEach(addItem);
        form.elements.unlimited.checked=p.validity_months==null;toggleValidity();
        document.getElementById('packageImage').value='';document.getElementById('packageImagePreview').src=p.image_url;
        document.getElementById('packageFormTitle').textContent=`Sửa gói #${p.magoi}`;form.scrollIntoView({behavior:'smooth'});
    }
    async function loadAdminTreatments() {
        const r=await api('/api/admin/packages/treatments?search='+encodeURIComponent(document.getElementById('treatmentSearch').value));
        document.getElementById('adminTreatments').innerHTML=r.treatments.map(t=>treatmentHtml(t,true)).join('')||'Không tìm thấy liệu trình.';
    }
    async function loadAdmin() {
        try {
            const r=await api('/api/admin/packages');adminPackages=r.packages;services=r.services;
            document.getElementById('packageRevenue').textContent='Doanh thu gói đã thanh toán: '+price(r.package_revenue);
            document.getElementById('packageList').innerHTML=adminPackages.map(p=>packageHtml(p)+`<p>${p.active?'Đang bán':'Ngừng bán'} · Đã bán: ${p.sold_count} · Liệu trình hoạt động: ${p.active_treatments}</p><button class="btn btn-secondary" data-edit="${p.magoi}">Sửa / Ngừng bán</button></article>`).join('');
            document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editPackage(adminPackages.find(p=>p.magoi===Number(b.dataset.edit))));
            if(!document.querySelector('.package-item-row'))addItem();
            const selector=document.getElementById('postCareService');selector.innerHTML=services.map(s=>`<option value="${s.madv}">${esc(s.tendv)}</option>`).join('');
            selector.onchange=()=>document.getElementById('postCareText').value=services.find(s=>s.madv===Number(selector.value))?.post_care_instructions||'';selector.onchange();
            const purchases=(await api('/api/admin/packages/purchases')).purchases;
            document.getElementById('packagePurchases').innerHTML=purchases.map(p=>`<article class="package-panel"><h3>PKG${p.id} · ${esc(p.tengoi)}</h3><p>${esc(p.customer_name)} · ${price(p.payable_amount ?? p.amount)} · ${esc(status(p.status))}</p>${p.status==='pending'&&p.payment_method==='cash'?`<button type="button" class="btn btn-primary" data-cash="${p.id}" data-amount="${esc(p.payable_amount ?? p.amount)}">Xác nhận đã nhận ${price(p.payable_amount ?? p.amount)}</button>`:''}</article>`).join('');
            document.querySelectorAll('[data-cash]').forEach(b=>b.onclick=async()=>{if(!confirm('Xác nhận cửa hàng đã nhận đủ tiền mua gói?'))return;b.disabled=true;try{await api(`/api/admin/packages/purchases/${b.dataset.cash}/confirm-payment`,'POST',{amount:b.dataset.amount});await loadAdmin();}catch(e){message(e.message);b.disabled=false;}});
            await loadAdminTreatments();
        } catch(e){message(e.message);}
    }
    document.addEventListener('DOMContentLoaded',()=>{
        if(document.querySelector('[data-package-page="customer"]'))loadCustomerPackages();
        const close=document.getElementById('closePackagePayment');if(close){
            const dialog=document.getElementById('packagePaymentDialog');
            close.onclick=()=>dialog.close();
            dialog.addEventListener('close',()=>{if(!dialog.open)clearInterval(pollTimer);});
        }
        if(document.querySelector('[data-package-page="admin"]')) {
            loadAdmin();
            document.getElementById('addPackageItem').onclick=()=>addItem();
            document.getElementById('newPackage').onclick=()=>{editId=null;document.getElementById('packageForm').reset();toggleValidity();document.getElementById('packageImagePreview').src='/static/images/default-package.svg';document.getElementById('packageFormTitle').textContent='Tạo gói dịch vụ';document.getElementById('packageItems').innerHTML='';addItem();};
            document.getElementById('packageForm').elements.unlimited.onchange=toggleValidity;
            document.getElementById('packageForm').addEventListener('input',priceWarning);
            document.getElementById('packageImage').onchange=e=>{const file=e.target.files[0];if(file){const reader=new FileReader();reader.onload=()=>document.getElementById('packageImagePreview').src=reader.result;reader.readAsDataURL(file);}};
            document.getElementById('packageForm').onsubmit=async e=>{
                e.preventDefault();const f=e.target;
                const body={tengoi:f.elements.tengoi.value,mota:f.elements.mota.value,giagoi:f.elements.giagoi.value,validity_months:f.elements.unlimited.checked?null:Number(f.elements.validity_months.value),active:f.elements.active.checked,items:[...f.querySelectorAll('.package-item-row')].map(row=>({madv:Number(row.querySelector('select').value),total_sessions:Number(row.querySelector('input').value)}))};
                const file=document.getElementById('packageImage').files[0];let payload=body;if(file){payload=new FormData();payload.append('data',JSON.stringify(body));payload.append('anhgoi',file);}
                try{const saved=await api(editId?`/api/admin/packages/${editId}`:'/api/admin/packages',editId?'PUT':'POST',payload);editId=saved.package.magoi;document.getElementById('packageImage').value='';message('Đã lưu gói dịch vụ.');await loadAdmin();}catch(error){message(error.message);}
            };
            let timer;document.getElementById('treatmentSearch').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>loadAdminTreatments().catch(e=>message(e.message)),250);};
            document.getElementById('postCareForm').onsubmit=async e=>{e.preventDefault();try{await api(`/api/admin/packages/services/${document.getElementById('postCareService').value}/post-care`,'PUT',{instructions:document.getElementById('postCareText').value});message('Đã lưu dặn dò.');await loadAdmin();}catch(error){message(error.message);}};
        }
    });
    function toggleValidity(){const f=document.getElementById('packageForm');f.elements.validity_months.disabled=f.elements.unlimited.checked;f.elements.validity_months.required=!f.elements.unlimited.checked;}
    function priceWarning(){const f=document.getElementById('packageForm');const retail=[...f.querySelectorAll('.package-item-row')].reduce((sum,row)=>sum+Number(services.find(s=>s.madv===Number(row.querySelector('select').value))?.gia||0)*Number(row.querySelector('input').value),0);document.getElementById('packagePriceWarning').textContent=Number(f.elements.giagoi.value)>retail?'Giá gói đang cao hơn tổng giá lẻ.':'';}
    window.PackageCare={api,showPayment,packageHtml,esc,price,status,validity,loadTreatments,renderBooking,chooseBookingItem,getUsages:()=>[...treatmentSelections.values()]};
})();
