(() => {
    'use strict';
    const {api,esc,price,status,validity,packageHtml,showPayment}=window.PackageCare;
    const el=id=>document.getElementById(id);
    const note=text=>el('packageMessage').textContent=text;
    const date=value=>value?new Date(value).toLocaleString('vi-VN'):'';
    const method=value=>({cash:'Tiền mặt',vietqr:'VietQR',points:'Điểm thưởng'}[value]||value);
    let packages=[],currentCash=null,searchVersion=0;
    async function customers(){
        const version=++searchVersion;
        try{const r=await api('/api/admin/package-sales/customers?search='+encodeURIComponent(el('saleCustomerSearch').value));if(version!==searchVersion)return;el('saleCustomer').innerHTML='<option value="">Chọn khách hàng</option>'+r.customers.map(c=>`<option value="${c.makh}">${esc(c.hoten)} · ${esc(c.sdt)}</option>`).join('');}catch(e){note(e.message);}
    }
    function preview(){const p=packages.find(p=>p.magoi===Number(el('salePackage').value));el('salePackagePreview').innerHTML=p?packageHtml(p)+'</article>':'';}
    async function cash(p){
        if(Number(p.payable_amount ?? p.amount)===0){await showPayment(p);return;}
        currentCash=p;el('cashSalePanel').classList.remove('package-hidden');
        el('cashSaleSummary').textContent=`${p.receipt_code} · ${p.customer_name} · ${p.tengoi} · Cần thu ${price(p.payable_amount ?? p.amount)}`;
        el('cashReceived').value='';change();el('cashSalePanel').scrollIntoView({behavior:'smooth',block:'center'});
        el('cashSalePanel').querySelector('.loyalty-payment')?.remove();
        if(window.LoyaltyPayment)await LoyaltyPayment.mount(el('cashSalePanel'),`/api/admin/packages/purchases/${p.id}`,p.makh,async()=>cash((await api(`/api/admin/package-sales/${p.id}`)).purchase));
    }
    function change(){if(!currentCash)return;const received=Number(el('cashReceived').value),expected=Number(currentCash.payable_amount ?? currentCash.amount);el('cashChange').textContent=received>=expected?'Tiền thối: '+price(received-expected):'Chưa đủ: '+price(expected-received);el('confirmPackageCash').disabled=received<expected;}
    async function receipt(id){
        try { const r=await api(`/api/admin/billing/transactions/package/${id}`); el('saleReceipt').innerHTML=BillingReceipt.render(r.transaction);el('saleReceiptDialog').showModal();el('printSaleReceipt').onclick=()=>{el('saleReceiptDialog').close();BillingReceipt.print(r.transaction);el('saleReceiptDialog').showModal();}; }
        catch(e){note(e.message);}
    }
    async function history(){
        try{const r=await api('/api/admin/package-sales?search='+encodeURIComponent(el('saleHistorySearch').value)+'&status='+el('saleHistoryStatus').value);el('saleHistory').innerHTML=r.purchases.map(p=>`<tr><td>${esc(p.receipt_code)}</td><td>${esc(p.customer_name)}<br>${esc(p.phone)}</td><td>${esc(p.tengoi)}</td><td>${price(p.payable_amount ?? p.amount)}</td><td>${esc(method(p.payment_method))}</td><td>${esc(status(p.status))}</td><td>${date(p.created_at)}<br>${date(p.paid_at)}</td><td>${esc(p.staff_name||'Online')}</td><td><button type="button" class="btn btn-secondary" data-receipt="${p.id}">Xem phiếu</button>${p.status==='pending'?`<button type="button" class="btn btn-primary" data-collect="${p.id}">Thanh toán</button>`:''}</td></tr>`).join('')||'<tr><td colspan="9">Chưa có phiếu bán gói.</td></tr>';el('saleHistory').querySelectorAll('[data-receipt]').forEach(b=>b.onclick=()=>receipt(b.dataset.receipt));el('saleHistory').querySelectorAll('[data-collect]').forEach(b=>b.onclick=async()=>{try{const p=(await api(`/api/admin/package-sales/${b.dataset.collect}`)).purchase;p.payment_method==='cash'?cash(p):await showPayment(p);}catch(e){note(e.message);}});}catch(e){note(e.message);}
    }
    document.addEventListener('DOMContentLoaded',async()=>{
        el('createPackageSale').disabled=true;
        el('salePackage').onchange=preview;el('cashReceived').oninput=change;
        let timer;el('saleCustomerSearch').oninput=()=>{clearTimeout(timer);timer=setTimeout(customers,250);};
        let historyTimer;el('saleHistorySearch').oninput=()=>{clearTimeout(historyTimer);historyTimer=setTimeout(history,250);};el('saleHistoryStatus').onchange=history;
        el('saleForm').onsubmit=async e=>{e.preventDefault();const button=el('createPackageSale');button.disabled=true;try{const p=(await api('/api/admin/package-sales','POST',{makh:Number(el('saleCustomer').value),magoi:Number(el('salePackage').value),payment_method:el('saleMethod').value})).purchase;p.payment_method==='cash'?cash(p):await showPayment(p);await history();note('Đã tạo phiếu. Liệu trình chỉ kích hoạt sau thanh toán.');}catch(e){note(e.message);}finally{button.disabled=false;}};
        el('confirmPackageCash').onclick=async()=>{if(!currentCash)return;const button=el('confirmPackageCash');button.disabled=true;try{const r=await api(`/api/admin/packages/purchases/${currentCash.id}/confirm-payment`,'POST',{cash_received:el('cashReceived').value});el('cashSalePanel').classList.add('package-hidden');currentCash=null;note('Thanh toán thành công. Liệu trình đã được kích hoạt.');await history();await receipt(r.purchase.id);}catch(e){note(e.message);change();}};
        el('closeSaleReceipt').onclick=()=>el('saleReceiptDialog').close();el('printSaleReceipt').onclick=()=>window.print();
        document.addEventListener('package:paid',()=>{note('Thanh toán thành công. Liệu trình đã được kích hoạt.');history();});
        try{const [r,options]=await Promise.all([api('/api/packages'),api('/api/packages/payment-options')]);packages=r.packages;el('salePackage').innerHTML='<option value="">Chọn gói dịch vụ</option>'+packages.map(p=>`<option value="${p.magoi}">${esc(p.tengoi)} · ${price(p.giagoi)}</option>`).join('');if(!options.vietqr_available){const option=el('saleMethod').querySelector('[value=vietqr]');option.disabled=true;option.textContent='VietQR tạm thời chưa khả dụng';}await customers();await history();el('createPackageSale').disabled=packages.length===0;}catch(e){note(e.message);}
    });
})();
