const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('receipt shows original, voucher, point discount, payable and earned points for both sources',()=>{
    const context={window:{},document:{}};
    vm.runInNewContext(fs.readFileSync('app/static/js/admin/invoice-receipt.js','utf8'),context);
    for(const type of ['service','package']){
        const html=context.window.BillingReceipt.render({transaction_type:type,original_total:'500000',total_amount:'500000',reward_discount:'50000',loyalty_discount:'100000',payable_amount:'350000',points_used:100,points_earned:30,items:[]});
        for(const expected of ['Tạm tính','Voucher','Giảm bằng điểm','100 điểm','350.000','+30 điểm'])assert.ok(html.includes(expected),expected);
        const plain=context.window.BillingReceipt.render({transaction_type:type,total_amount:'500000',reward_discount:0,loyalty_discount:0,payable_amount:500000,points_earned:0,items:[]});
        assert.ok(!plain.includes('Voucher:')&&!plain.includes('Giảm bằng điểm:')&&!plain.includes('+0 điểm'));
    }
});

function setup(payable){
    const nodes=new Map(),calls=[];
    class Element{
        constructor(){this.style={};this.parts=new Map();this.isConnected=false;}
        querySelector(selector){if(!this.parts.has(selector))this.parts.set(selector,new Element());return this.parts.get(selector);}
        querySelectorAll(selector){return [this.querySelector(selector)];}
        appendChild(node){node.isConnected=true;nodes.set(node.id,node);}
        remove(){this.isConnected=false;nodes.delete(this.id);}
    }
    const document={body:new Element(),getElementById:id=>nodes.get(id),createElement:()=>new Element(),addEventListener(){},dispatchEvent(){}};
    const context={window:{},document,CustomEvent:class{},getAuthHeaders:()=>({}),showSuccess(){},showError:m=>{throw new Error(m);},clearTimeout(){},setTimeout(){},fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({mahd:31,tongtien:500000,payable_amount:payable,loyalty_discount:500000-payable,points_used:(500000-payable)/1000,trangthai:'Chưa thanh toán'})};}};
    vm.runInNewContext(fs.readFileSync('app/static/js/admin/invoice-payment.js','utf8'),context);
    return {context,nodes,calls};
}

test('cash input uses server payable; closing keeps reservation without a DELETE',async()=>{
    const s=setup(400000);await s.context.window.openInvoicePayment(31);
    s.nodes.get('sharedInvoicePayment').querySelector('[data-cash]').onclick();
    assert.match(s.nodes.get('sharedInvoicePayment').innerHTML,/min="400000"/);
    s.nodes.get('sharedInvoicePayment').querySelector('[data-close]').onclick();
    assert.ok(s.calls.every(c=>c.options.method==='GET'));
});

test('zero payable offers point settlement and never asks for a QR',async()=>{
    const s=setup(0);await s.context.window.openInvoicePayment(31);
    const modal=s.nodes.get('sharedInvoicePayment');assert.match(modal.innerHTML,/Thanh toán bằng điểm/);
    await modal.querySelector('[data-points-pay]').onclick({currentTarget:{disabled:false}});
    assert.ok(s.calls.some(c=>c.url.endsWith('/pay-points')));
    assert.ok(s.calls.every(c=>!c.url.endsWith('/generate-qr')));
});

function mountPayment(base){
    const calls=[];
    class Element{
        constructor(){this.parts=new Map();this.isConnected=true;this.innerHTML='';}
        querySelector(selector){if(!this.parts.has(selector))this.parts.set(selector,new Element());return this.parts.get(selector);}
        prepend(node){this.child=node;}
    }
    const state={wallet:{available_points:300,reserved_points:100},original_total:'500000',payable_amount:'500000',redeem_enabled:true,max_points_allowed:250,points_used:0};
    const respond=url=>url.includes('/vouchers')||url.includes('/my-rewards')?{items:[]}:state;
    const fetcher=async url=>{calls.push(url);return {ok:true,status:200,json:async()=>respond(url)};};
    const context={window:{getAuthHeaders:()=>({}),CustomerAuth:{fetch:fetcher}},document:{createElement:()=>new Element()},fetch:fetcher,Intl};
    vm.runInNewContext(fs.readFileSync('app/static/js/loyalty-payment.js','utf8'),context);
    const root=new Element();
    return context.window.LoyaltyPayment.mount(root,base,7,async()=>{}).then(()=>({html:root.child.innerHTML,calls}));
}

test('customer payment shows only available points; staff still sees reserved balance',async()=>{
    for(const base of ['/api/payment/invoices/31','/api/packages/purchases/5']){
        const {html,calls}=await mountPayment(base);
        assert.match(html,/Khả dụng: 300 điểm/);
        assert.ok(!html.includes('Đang giữ')&&!html.includes('100 điểm'),html);
        assert.ok(calls.some(u=>u==='/api/loyalty/my-rewards?status=usable&per_page=100'),calls.join());
    }
    for(const base of ['/api/admin/invoices/31','/api/admin/packages/purchases/5']){
        const {html,calls}=await mountPayment(base);
        assert.match(html,/Khả dụng: 300 điểm · Đang giữ: 100 điểm/);
        assert.ok(calls.some(u=>u.startsWith('/api/admin/loyalty/customers/7/vouchers')));
    }
});

test('api errors carry the HTTP status and tolerate non-JSON bodies',async()=>{
    const context={window:{CustomerAuth:{fetch:async()=>({ok:false,status:502,json:async()=>{throw new SyntaxError('html');}})}},document:{},Intl};
    vm.runInNewContext(fs.readFileSync('app/static/js/loyalty-payment.js','utf8'),context);
    await assert.rejects(context.window.LoyaltyPayment.api('/api/loyalty/me'),e=>e.status===502&&e.message==='Không thể cập nhật điểm');
});

test('customer loyalty page never renders the reserved-points label',()=>{
    const source=fs.readFileSync('app/static/js/customers/loyalty.js','utf8');
    assert.ok(!/Điểm đang giữ|reserved_points/.test(source));
    assert.ok(!/Đang giữ|reserved_points/.test(fs.readFileSync('app/templates/customer/profile.html','utf8').match(/id="loyalty-section"[\s\S]*?id="reviews-section"/)[0]));
});
