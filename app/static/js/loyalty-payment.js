/* All conversion/limits come from server previews. Reservations survive closing. */
(() => {
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const money = value => new Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'}).format(Number(value));
    async function api(url, method='GET', body) {
        const admin = url.startsWith('/api/admin/');
        const headers = admin ? window.getAuthHeaders(true) : {'Content-Type':'application/json'};
        const fetcher = admin ? fetch : window.CustomerAuth.fetch.bind(window.CustomerAuth);
        const response = await fetcher(url, {method, headers, cache:'no-store', ...(body ? {body:JSON.stringify(body)} : {})});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw Object.assign(new Error(data.msg || data.message || 'Không thể cập nhật điểm'), {status: response.status});
        return data;
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
        const host = document.createElement('section');
        host.className = 'loyalty-payment';
        host.innerHTML = '<p>Đang tải điểm thưởng...</p>';
        root.prepend(host);
        // Customers see only spendable points; staff keep the reserved balance for reconciliation.
        const admin = base.startsWith('/api/admin/');
        try {
            const state = await api(base+'/loyalty');
            if (!host.isConnected) return;
            host.innerHTML = `<h4>ĐIỂM THƯỞNG</h4><p>Khả dụng: ${esc(state.wallet.available_points)} điểm${admin ? ` · Đang giữ: ${esc(state.wallet.reserved_points)} điểm` : ''}</p>`+
                summary(state)+
                (state.redeem_enabled ? `<label><input type="checkbox" data-enable ${state.points_used ? 'checked' : ''}> Sử dụng điểm</label><div data-point-controls ${state.points_used ? '' : 'hidden'}><label>Số điểm <input data-points type="number" min="1" step="1" value="${esc(state.points_used || '')}"></label><button type="button" class="btn btn-secondary" data-max>Dùng tối đa (${esc(state.max_points_allowed)})</button><button type="button" class="btn btn-secondary" data-preview>Xem quy đổi</button><button type="button" class="btn btn-primary" data-apply>Áp dụng điểm</button></div>` : '<p>Quy tắc hiện tại không cho dùng điểm cho thanh toán này.</p>')+
                (state.points_used ? '<button type="button" class="btn btn-secondary" data-remove>Bỏ sử dụng điểm</button>' : '')+
                `<div data-vouchers></div><p data-result role="status" aria-live="polite"></p>`;
            const note = host.querySelector('[data-result]');
            const run = fn => async event => {
                const button = event.currentTarget;
                button.disabled = true;
                try { await fn(); } catch(error) { note.textContent=error.message; }
                finally { button.disabled=false; }
            };
            const points = host.querySelector('[data-points]');
            const preview = async () => {
                const data = await api(base+'/loyalty/preview', 'POST', {points:Number(points.value)});
                note.textContent=`Cho phép ${data.points_allowed} điểm · Giảm ${money(data.discount_amount)} · Còn trả ${money(data.payable_amount)}`;
                return data;
            };
            const enable = host.querySelector('[data-enable]');
            if (enable) {
                enable.onchange=()=>{host.querySelector('[data-point-controls]').hidden=!enable.checked;};
                host.querySelector('[data-preview]').onclick=run(preview);
                host.querySelector('[data-max]').onclick=run(async()=>{points.value=state.max_points_allowed;await preview();});
                host.querySelector('[data-apply]').onclick=run(async()=>{
                    await api(base+'/loyalty','POST',{points:Number(points.value)});await changed();
                });
            }
            const remove = host.querySelector('[data-remove]');
            if (remove) remove.onclick=run(async()=>{await api(base+'/loyalty','DELETE');await changed();});
            // The server filters by transaction type; the backend still validates every apply.
            const kind = base.includes('/packages/') ? 'package_purchase' : 'service_invoice';
            const endpoint = admin ? `/api/admin/loyalty/customers/${makh}/vouchers?usable_for=${kind}&per_page=100` : `/api/loyalty/my-rewards?status=usable&usable_for=${kind}&per_page=100`;
            const vouchers = (await api(endpoint)).items.filter(v=>v.status==='available' && ['voucher_amount','voucher_percent'].includes(v.reward.reward_type) && [undefined,null,'both',kind].includes(v.reward.apply_to));
            if (!host.isConnected) return;
            const section = host.querySelector('[data-vouchers]');
            const total = Number(state.original_total);
            const option = v => {
                const minimum = Number(v.reward.minimum_spend || 0), short = minimum > total;
                return `<option value="${v.id}" ${short ? 'disabled' : ''}>${esc(v.reward.name)} · ${esc(v.code)} · ${esc(voucherTerms(v.reward))}${short ? ' (chưa đạt đơn tối thiểu)' : ''}</option>`;
            };
            section.innerHTML = state.reward_redemption_id ? `<p data-applied-voucher>Voucher đang áp dụng: ${esc(state.reward_name)} · ${esc(state.reward_code)}</p><button type="button" class="btn btn-secondary" data-remove-voucher>Bỏ voucher</button>` :
                vouchers.length ? `<label>Ưu đãi của khách<select data-voucher><option value="">Chọn voucher</option>${vouchers.map(option).join('')}</select></label><button type="button" class="btn btn-secondary" data-apply-voucher>Áp dụng voucher</button>` : '';
            const apply = section.querySelector('[data-apply-voucher]');
            if (apply) apply.onclick=run(async()=>{
                const id = Number(section.querySelector('select').value);
                if (!id) { note.textContent='Hãy chọn voucher.'; return; }
                await api(base+'/reward','POST',{redemption_id:id});await changed();
            });
            const removeVoucher = section.querySelector('[data-remove-voucher]');
            if (removeVoucher) removeVoucher.onclick=run(async()=>{await api(base+'/reward','DELETE');await changed();});
        } catch(error) { if(host.isConnected) host.textContent=error.message; }
    }
    async function openCustomerInvoice(id) {
        document.getElementById('customerLoyaltyPayment')?.close();
        document.getElementById('customerLoyaltyPayment')?.remove();
        const invoice=await api(`/api/payment/invoices/${id}`);
        if(invoice.trangthai==='Đã thanh toán'){window.loadUserInvoices?.();return;}
        const dialog=document.createElement('dialog');dialog.id='customerLoyaltyPayment';dialog.className='loyalty-dialog';
        const zero=Number(invoice.payable_amount ?? invoice.tongtien)===0;
        dialog.innerHTML=`<h3>Thanh toán HD${String(id).padStart(6,'0')}</h3>${summary(invoice)}<div data-editor></div><button class="btn btn-primary" data-pay>${zero?'Thanh toán bằng điểm':'Tiếp tục thanh toán VietQR'}</button><button class="btn btn-outline" data-close>Đóng</button><div data-bank></div><p data-message role="status"></p>`;
        document.body.append(dialog);dialog.showModal();let timer;
        dialog.addEventListener('close',()=>{clearTimeout(timer);dialog.remove();});
        dialog.querySelector('[data-close]').onclick=()=>dialog.close();
        const base=`/api/payment/invoices/${id}`;
        dialog.querySelector('[data-pay]').onclick=async event=>{
            const button=event.currentTarget;button.disabled=true;
            try{
                if(zero){await api(base+'/pay-points','POST',{});dialog.close();window.loadUserInvoices?.();return;}
                const payment=await api(base+'/generate-qr','POST',{});
                if(!dialog.isConnected||!dialog.open)return;
                dialog.querySelector('[data-bank]').innerHTML=`<img src="${esc(payment.qrCodeUrl)}" alt="VietQR" style="max-width:100%"><p>${esc(payment.accountName)} · ${esc(payment.accountNo)} · ${esc(payment.bank)}</p><p>Nội dung: ${esc(payment.description)}</p><p>Số tiền: ${money(payment.amount)}</p>`;
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
        await mount(dialog.querySelector('[data-editor]'),base,null,()=>openCustomerInvoice(id));
    }
    window.LoyaltyPayment={api,mount,summary,money,esc,voucherTerms,openCustomerInvoice};
})();
