/* All conversion/limits come from server previews. Reservations survive closing. */
(() => {
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const money = value => new Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'}).format(Number(value));
    async function api(url, method='GET', body) {
        const admin = url.startsWith('/api/admin/');
        const headers = admin ? window.getAuthHeaders(true) : {'Content-Type':'application/json'};
        const fetcher = admin ? fetch : window.CustomerAuth.fetch.bind(window.CustomerAuth);
        const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);
        try {
            const response = await fetcher(url, {method, headers, signal:controller.signal, cache:'no-store', ...(body ? {body:JSON.stringify(body)} : {})});
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw Object.assign(new Error(data.msg || data.message || 'Không thể cập nhật điểm'), {status: response.status});
            return data;
        }finally{clearTimeout(timeout);}
    }
    const scopes = {service_invoice:'Hóa đơn dịch vụ', package_purchase:'Mua gói', both:'Cả hai'};
    const pct = value => new Intl.NumberFormat('vi-VN', {maximumFractionDigits:2}).format(Number(value)) + '%';
    function voucherTerms(reward) {
        const minimum = Number(reward.minimum_spend || 0);
        const value = reward.reward_type === 'voucher_percent' ? pct(reward.percentage_value) + (reward.max_discount_amount ? ` (tối đa ${money(reward.max_discount_amount)})` : '') : money(reward.reward_value);
        return `Giảm ${value} · ${minimum ? 'Đơn từ '+money(minimum) : 'Không yêu cầu đơn tối thiểu'} · ${scopes[reward.apply_to || 'both']}`;
    }
    function summary(data) {
        return `<p>Tạm tính: ${money(data.original_total ?? data.tongtien ?? data.amount)}</p>`+
            (Number(data.reward_discount) ? `<p>Voucher: −${money(data.reward_discount)}</p>` : '')+
            (Number(data.loyalty_discount) ? `<p>Đang dùng ${esc(data.points_used)} điểm · Giảm bằng điểm: −${money(data.loyalty_discount)}</p>` : '')+
            `<p><strong>Cần thanh toán: ${money(data.payable_amount ?? data.tongtien ?? data.amount)}</strong></p>`+
            (data.points_earned ? `<p>Điểm tích được: +${esc(data.points_earned)}</p>` : '');
    }
    async function mount(root, base, makh, changed) {
        let host = root.querySelector(':scope > .loyalty-payment');
        if (!host) {
            host = document.createElement('section'); host.className = 'loyalty-payment';
            host.innerHTML = '<p>Đang tải điểm thưởng...</p>'; root.prepend(host);
        }
        const revision=String(Number(root.dataset.loyaltyRevision||0)+1);
        root.dataset.loyaltyRevision=revision;
        const current=()=>host.isConnected&&root.dataset.loyaltyRevision===revision;
        // Customers see only spendable points; staff keep the reserved balance for reconciliation.
        const admin = base.startsWith('/api/admin/');
        try {
            const state = await api(base+'/loyalty');
            if (!current()) return;
            host.innerHTML = `<h4>ĐIỂM THƯỞNG</h4><p>Khả dụng: ${esc(state.wallet.available_points)} điểm${admin ? ` · Đang giữ: ${esc(state.wallet.reserved_points)} điểm` : ''}</p>`+
                summary(state)+
                (state.redeem_enabled && Number(state.max_points_allowed)>0 ? `<label><input type="checkbox" data-enable ${state.points_used ? 'checked' : ''}> Sử dụng điểm</label><div data-point-controls ${state.points_used ? '' : 'hidden'}><label>Số điểm <input data-points type="number" min="1" max="${esc(state.max_points_allowed)}" step="1" value="${esc(state.points_used || '')}"></label><button type="button" class="btn btn-secondary" data-max>Dùng tối đa (${esc(state.max_points_allowed)})</button><button type="button" class="btn btn-secondary" data-preview>Xem quy đổi điểm</button><button type="button" class="btn btn-primary" data-apply>Áp dụng điểm</button></div>` : `<p>${state.redeem_enabled?'Giao dịch chưa đủ điều kiện dùng điểm theo giới hạn hiện tại.':'Quy tắc hiện tại không cho dùng điểm cho thanh toán này.'}</p>`)+
                (state.points_used ? '<button type="button" class="btn btn-secondary" data-remove>Bỏ sử dụng điểm</button>' : '')+
                `<div data-vouchers></div><p data-result role="status" aria-live="polite"></p>`;
            const note = host.querySelector('[data-result]');
            let busy=false,uncertain=false;
            const run = (fn,mutation=false) => async event => {
                if(busy||uncertain||!current())return;
                busy=true;
                const dialog=host.closest('dialog'),scroll=dialog?.scrollTop,focus=document.activeElement;
                const marker=[...event.currentTarget.attributes].find(a=>a.name.startsWith('data-'))?.name;
                const controls=[...new Set([...host.querySelectorAll('button,input'),...(dialog?.querySelectorAll('button:not([data-close]):not(.package-dialog-close)')||[])])].map(el=>[el,el.disabled]);
                const pay=dialog?.querySelector('[data-pay]');if(pay)pay.disabled=true;
                controls.forEach(([el])=>{el.disabled=true;});host.setAttribute('aria-busy','true');note.textContent=mutation?'Đang cập nhật ưu đãi…':'Đang quy đổi điểm…';
                try { await fn(); }
                catch(error) {
                    if(mutation&&(!error.status||error.status>=500||error.status===409)){
                        note.textContent='Đã gửi yêu cầu, đang xác minh kết quả…';
                        try{await changed();}
                        catch(reconcileError){
                            uncertain=true;
                            const recoveryNote=host.querySelector('[data-result]')||host;
                            recoveryNote.textContent='Chưa xác minh được kết quả. Kiểm tra lại trước khi áp dụng tiếp.';
                            const retry=document.createElement('button');retry.type='button';retry.className='btn btn-outline';retry.textContent='Kiểm tra kết quả';
                            retry.onclick=async()=>{retry.disabled=true;try{await changed();}catch(e){retry.disabled=false;recoveryNote.textContent=e.message;recoveryNote.append(retry);}};recoveryNote.append(retry);
                        }
                    }else if(host.isConnected)note.textContent=error.message;
                }
                finally {
                    busy=false;host.removeAttribute('aria-busy');
                    if(!uncertain){controls.forEach(([el,disabled])=>{if(el.isConnected)el.disabled=disabled;});if(pay?.isConnected)pay.disabled=false;}
                    if(dialog?.isConnected&&dialog.open){dialog.scrollTop=scroll;const next=marker?dialog.querySelector(`[${marker}]`):null;(next|| (focus?.isConnected?focus:null) || dialog.querySelector('[data-pay]'))?.focus({preventScroll:true});}
                }
            };
            const points = host.querySelector('[data-points]');
            const pointValue=()=>{
                const value=Number(points.value);
                if(!Number.isSafeInteger(value)||value<1||value>Number(state.max_points_allowed))throw Object.assign(new Error(`Nhập số điểm nguyên từ 1 đến ${state.max_points_allowed}.`),{status:400});
                return value;
            };
            const preview = async () => {
                const requested=pointValue();
                const data = await api(base+'/loyalty/preview', 'POST', {points:requested});
                note.textContent=`Cho phép ${data.points_allowed} điểm · Giảm ${money(data.discount_amount)} · Còn trả ${money(data.payable_amount)}`;
                return data;
            };
            const enable = host.querySelector('[data-enable]');
            if (enable) {
                enable.onchange=()=>{host.querySelector('[data-point-controls]').hidden=!enable.checked;};
                host.querySelector('[data-preview]').onclick=run(preview);
                host.querySelector('[data-max]').onclick=run(async()=>{points.value=state.max_points_allowed;await preview();});
                host.querySelector('[data-apply]').onclick=run(async()=>{
                    await api(base+'/loyalty','POST',{points:pointValue()});await changed();
                },true);
            }
            const remove = host.querySelector('[data-remove]');
            if (remove) remove.onclick=run(async()=>{await api(base+'/loyalty','DELETE');await changed();},true);
            // The server filters by transaction type; the backend still validates every apply.
            const kind = base.includes('/packages/') ? 'package_purchase' : 'service_invoice';
            const endpoint = admin ? `/api/admin/loyalty/customers/${makh}/vouchers?usable_for=${kind}&per_page=100` : `/api/loyalty/my-rewards?status=usable&usable_for=${kind}&per_page=100`;
            const vouchers = (await api(endpoint)).items.filter(v=>v.status==='available' && ['voucher_amount','voucher_percent'].includes(v.reward.reward_type) && [undefined,null,'both',kind].includes(v.reward.apply_to));
            if (!current()) return;
            const section = host.querySelector('[data-vouchers]');
            const total = Number(state.original_total);
            const option = v => {
                const minimum = Number(v.reward.minimum_spend || 0), short = minimum > total;
                return `<label class="loyalty-voucher-option"><input type="radio" name="voucher-${revision}-${esc(base)}" data-voucher value="${v.id}" ${short?'disabled':''}><span><strong>${esc(v.reward.name)}</strong><span>${esc(v.code)}</span><small>${esc(voucherTerms(v.reward))}${short?' · Chưa đạt đơn tối thiểu':''}</small></span></label>`;
            };
            section.innerHTML = state.reward_redemption_id ? `<p data-applied-voucher>Voucher đang áp dụng: ${esc(state.reward_name)} · ${esc(state.reward_code)}</p><button type="button" class="btn btn-secondary" data-remove-voucher>Bỏ voucher</button>` :
                vouchers.length ? `<fieldset class="loyalty-voucher-list"><legend>Ưu đãi của khách</legend>${vouchers.map(option).join('')}</fieldset><button type="button" class="btn btn-secondary" data-apply-voucher>Áp dụng voucher</button>` : '';
            const apply = section.querySelector('[data-apply-voucher]');
            if (apply) apply.onclick=run(async()=>{
                const id = Number(section.querySelector('[data-voucher]:checked')?.value);
                if (!id) { note.textContent='Hãy chọn voucher.'; return; }
                await api(base+'/reward','POST',{redemption_id:id});await changed();
            },true);
            const removeVoucher = section.querySelector('[data-remove-voucher]');
            if (removeVoucher) removeVoucher.onclick=run(async()=>{await api(base+'/reward','DELETE');await changed();},true);
        } catch(error) { if(current()){host.textContent=error.message;const retry=document.createElement('button');retry.type='button';retry.className='btn btn-outline';retry.textContent='Thử lại';retry.onclick=async()=>{retry.disabled=true;try{await changed();}catch(e){retry.disabled=false;}};host.append(retry);}return false; }
    }
    let invoiceOpenRequest=0;
    async function openCustomerInvoice(id) {
        const request=++invoiceOpenRequest;
        const trigger=document.activeElement;
        document.getElementById('customerLoyaltyPayment')?.close();
        document.getElementById('customerLoyaltyPayment')?.remove();
        let invoice=await api(`/api/payment/invoices/${id}`);
        if(request!==invoiceOpenRequest)return;
        if(invoice.trangthai==='Đã thanh toán'){window.loadUserInvoices?.();return;}
        const dialog=document.createElement('dialog');dialog.id='customerLoyaltyPayment';dialog.className='loyalty-dialog';
        let zero=Number(invoice.payable_amount ?? invoice.tongtien)===0;
        dialog.setAttribute('aria-label',`Thanh toán HD${String(id).padStart(6,'0')}`);
        dialog.innerHTML=`<header class="loyalty-payment-header"><h3>Thanh toán HD${String(id).padStart(6,'0')}</h3><button type="button" class="btn btn-outline" data-close>Đóng</button></header><div data-invoice-summary>${summary(invoice)}</div><div data-editor></div><footer class="loyalty-payment-footer"><button type="button" class="btn btn-primary" data-pay>${zero?'Thanh toán bằng điểm':'Tiếp tục thanh toán VietQR'}</button></footer><div data-bank></div><p data-message role="status" aria-live="polite"></p>`;
        document.body.append(dialog);dialog.showModal();let timer;
        dialog.addEventListener('close',()=>{clearTimeout(timer);dialog.remove();if(trigger?.isConnected)trigger.focus();});
        dialog.querySelector('[data-close]').onclick=()=>dialog.close();
        const base=`/api/payment/invoices/${id}`;
        const refresh=async()=>{
            const latest=await api(base);
            if(!dialog.isConnected||!dialog.open)return;
            invoice=latest;zero=Number(invoice.payable_amount??invoice.tongtien)===0;
            if(invoice.trangthai==='Đã thanh toán'){dialog.close();window.loadUserInvoices?.();return;}
            clearTimeout(timer);dialog.querySelector('[data-bank]').replaceChildren();
            dialog.querySelector('[data-invoice-summary]').innerHTML=summary(invoice);
            dialog.querySelector('[data-pay]').textContent=zero?'Thanh toán bằng điểm':'Tiếp tục thanh toán VietQR';
            dialog.querySelector('[data-editor]').hidden=false;dialog.querySelector('[data-message]').textContent='Đã cập nhật ưu đãi. Tiếp tục để lấy mã thanh toán đúng số tiền.';
            if(await mount(dialog.querySelector('[data-editor]'),base,null,refresh)===false)throw Error('Chưa tải được trạng thái ưu đãi.');
            dialog.querySelector('[data-pay]').disabled=false;
        };
        dialog.querySelector('[data-pay]').onclick=async event=>{
            const button=event.currentTarget;button.disabled=true;
            try{
                if(zero){await api(base+'/pay-points','POST',{});dialog.close();window.loadUserInvoices?.();return;}
                const payment=await api(base+'/generate-qr','POST',{});
                if(!dialog.isConnected||!dialog.open)return;
                dialog.querySelector('[data-bank]').innerHTML=`<img src="${esc(payment.qrCodeUrl)}" alt="VietQR" style="max-width:100%"><p>${esc(payment.accountName)} · ${esc(payment.accountNo)} · ${esc(payment.bank)}</p><button type="button" class="btn btn-outline" data-copy="${esc(payment.accountNo)}">Sao chép số tài khoản</button><p>Nội dung: ${esc(payment.description)}</p><button type="button" class="btn btn-outline" data-copy="${esc(payment.description)}">Sao chép nội dung</button><p>Số tiền: ${money(payment.amount)}</p>`;
                dialog.querySelector('[data-message]').textContent='Đang chờ ngân hàng xác nhận thanh toán. Bạn có thể đóng và tiếp tục từ Hóa đơn của tôi.';
                dialog.querySelectorAll('[data-copy]').forEach(copy=>copy.onclick=async()=>{
                    try{await navigator.clipboard.writeText(copy.dataset.copy);dialog.querySelector('[data-message]').textContent='Đã sao chép. Đang chờ xác nhận thanh toán từ ngân hàng.';}
                    catch(_){dialog.querySelector('[data-message]').textContent='Chưa sao chép được. Vui lòng chọn và sao chép thông tin chuyển khoản ở trên.';}
                });
                dialog.querySelector('[data-editor]').hidden=true;
                const deadline=Date.now()+300000;
                const poll=async()=>{
                    if(!dialog.isConnected||!dialog.open)return;
                    try{const latest=await api(base);if(latest.trangthai==='Đã thanh toán'){dialog.close();window.loadUserInvoices?.();window.CustomerLoyalty?.load();return;}}
                    catch(error){dialog.querySelector('[data-message]').textContent=error.message;}
                    if(Date.now()<deadline)timer=setTimeout(poll,3000);
                    else dialog.querySelector('[data-message]').textContent='Chưa nhận xác nhận. Bạn có thể đóng và tiếp tục sau.';
                };
                timer=setTimeout(poll,3000);
            }catch(error){if(dialog.isConnected){dialog.querySelector('[data-message]').textContent=error.message;button.disabled=false;}}
        };
        await mount(dialog.querySelector('[data-editor]'),base,null,refresh);
    }
    window.LoyaltyPayment={api,mount,summary,money,esc,voucherTerms,openCustomerInvoice};
})();
