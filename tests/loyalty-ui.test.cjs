const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('receipt shows original, voucher, point discount, payable and earned points for both sources',()=>{
    const context={window:{},document:{}};
    vm.runInNewContext(fs.readFileSync('app/static/js/admin/invoice-receipt.js','utf8'),context);
    for(const type of ['service','package']){
        const html=context.window.BillingReceipt.render({transaction_type:type,original_total:'500000',total_amount:'500000',reward_discount:'50000',reward_code:'BIN-ABC',loyalty_discount:'100000',payable_amount:'350000',points_used:100,points_earned:30,payment_method:'Tiền mặt',items:[]});
        const text=html.replace(/<[^>]+>/g,'').replace(/\s+/g,' ');
        for(const expected of [/Tạm tính: 500\.000\s₫/,/Voucher \(BIN-ABC\): −50\.000\s₫/,/Điểm thưởng \(100 điểm\): −100\.000\s₫/,/Cần thanh toán: 350\.000\s₫/,/Phương thức: Tiền mặt/,/Điểm tích được: \+30 điểm/])assert.match(text,expected);
        const plain=context.window.BillingReceipt.render({transaction_type:type,total_amount:'500000',reward_discount:0,loyalty_discount:0,payable_amount:500000,points_earned:0,items:[]});
        assert.ok(!plain.includes('Voucher')&&!plain.includes('Điểm thưởng')&&!plain.includes('+0 điểm')&&plain.includes('Cần thanh toán'));
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

function mountPayment(base,{vouchers=[],extra={}}={}){
    const calls=[];
    class Element{
        constructor(){this.parts=new Map();this.isConnected=true;this.innerHTML='';}
        querySelector(selector){if(!this.parts.has(selector))this.parts.set(selector,new Element());return this.parts.get(selector);}
        prepend(node){this.child=node;}
    }
    const state={wallet:{available_points:300,reserved_points:100},original_total:'500000',payable_amount:'500000',redeem_enabled:true,max_points_allowed:250,points_used:0,...extra};
    const respond=url=>url.includes('/vouchers')||url.includes('/my-rewards')?{items:vouchers}:state;
    const fetcher=async url=>{calls.push(url);return {ok:true,status:200,json:async()=>respond(url)};};
    const context={window:{getAuthHeaders:()=>({}),CustomerAuth:{fetch:fetcher}},document:{createElement:()=>new Element()},fetch:fetcher,Intl};
    vm.runInNewContext(fs.readFileSync('app/static/js/loyalty-payment.js','utf8'),context);
    const root=new Element();
    return context.window.LoyaltyPayment.mount(root,base,7,async()=>{}).then(()=>({html:root.child.innerHTML,vouchersHtml:root.child.querySelector('[data-vouchers]').innerHTML,calls}));
}

test('customer payment shows only available points; staff still sees reserved balance',async()=>{
    for(const base of ['/api/payment/invoices/31','/api/packages/purchases/5']){
        const {html,calls}=await mountPayment(base);
        assert.match(html,/Khả dụng: 300 điểm/);
        assert.ok(!html.includes('Đang giữ')&&!html.includes('100 điểm'),html);
        const kind=base.includes('/packages/')?'package_purchase':'service_invoice';
        assert.ok(calls.some(u=>u===`/api/loyalty/my-rewards?status=usable&usable_for=${kind}&per_page=100`),calls.join());
    }
    for(const base of ['/api/admin/invoices/31','/api/admin/packages/purchases/5']){
        const {html,calls}=await mountPayment(base);
        assert.match(html,/Khả dụng: 300 điểm · Đang giữ: 100 điểm/);
        const kind=base.includes('/packages/')?'package_purchase':'service_invoice';
        assert.ok(calls.some(u=>u===`/api/admin/loyalty/customers/7/vouchers?usable_for=${kind}&per_page=100`),calls.join());
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

test('voucher picker shows terms, disables vouchers under the minimum and hides other scopes',async()=>{
    const voucher=(id,reward)=>({id,code:'BIN-'+id,status:'available',reward:{reward_type:'voucher_amount',reward_value:'50000.00',...reward}});
    const vouchers=[voucher(1,{name:'V50',minimum_spend:'0.00',apply_to:'both'}),voucher(2,{name:'V-min',minimum_spend:'600000.00',apply_to:'service_invoice'}),
        voucher(3,{name:'V-pkg',minimum_spend:'0.00',apply_to:'package_purchase'}),voucher(4,{name:'V-legacy'}),
        {id:5,code:'BIN-5',status:'available',reward:{reward_type:'physical_gift',name:'Khăn'}}];
    const {vouchersHtml}=await mountPayment('/api/payment/invoices/31',{vouchers});
    assert.match(vouchersHtml,/V50 · BIN-1 · Giảm 50\.000\s₫ · Không yêu cầu đơn tối thiểu · Cả hai/);
    assert.match(vouchersHtml,/<option value="2" disabled>V-min · BIN-2 · Giảm 50\.000\s₫ · Đơn từ 600\.000\s₫ · Hóa đơn dịch vụ \(chưa đạt đơn tối thiểu\)/);
    assert.ok(vouchersHtml.includes('V-legacy')&&!vouchersHtml.includes('V-pkg')&&!vouchersHtml.includes('Khăn'),vouchersHtml);
    const applied=await mountPayment('/api/payment/invoices/31',{vouchers,extra:{reward_redemption_id:1,reward_name:'V50',reward_code:'BIN-1'}});
    assert.match(applied.vouchersHtml,/Voucher đang áp dụng: V50 · BIN-1/);
    assert.ok(applied.vouchersHtml.includes('data-remove-voucher')&&!applied.vouchersHtml.includes('<select'));
});

function customerRender(){
    const context={window:{},document:{addEventListener(){}},location:{search:'',href:'http://x/profile'},URLSearchParams,Intl};
    vm.runInNewContext(fs.readFileSync('app/static/js/loyalty-payment.js','utf8'),context);
    vm.runInNewContext(fs.readFileSync('app/static/js/customers/loyalty.js','utf8'),context);
    return context.window.CustomerLoyalty.render;
}
const plainText=html=>html.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');

test('reward store card shows voucher value, scope, minimum, validity and stock',()=>{
    const {rewardCard}=customerRender();
    const voucher={id:1,name:'VOUCHER 50.000Đ',description:'Giảm trực tiếp',reward_type:'voucher_amount',points_cost:200,reward_value:'50000.00',apply_to:'both',minimum_spend:'200000.00',validity_days:30,stock:5};
    const text=plainText(rewardCard(voucher,500));
    for(const expected of [/VOUCHER 50\.000Đ/,/Giảm trực tiếp/,/Điểm cần đổi 200 điểm/,/Giảm 50\.000\s₫/,/Áp dụng Dịch vụ và gói/,/Đơn tối thiểu 200\.000\s₫/,/Hạn 30 ngày sau khi đổi/,/Còn 5 quà/,/Đổi ngay/])assert.match(text,expected);
    const scoped=plainText(rewardCard({...voucher,apply_to:'service_invoice',minimum_spend:'0.00',validity_days:null,stock:null},500));
    assert.match(scoped,/Áp dụng Hóa đơn dịch vụ.*Đơn tối thiểu Không yêu cầu.*Hạn Không hết hạn.*Còn quà/);
    assert.match(plainText(rewardCard({...voucher,apply_to:'package_purchase'},500)),/Áp dụng Mua gói dịch vụ/);
    const poor=rewardCard(voucher,150);
    assert.match(plainText(poor),/Cần thêm 50 điểm/);
    assert.match(poor,/data-redeem="1" disabled>Chưa đủ điểm</);
    const gift=plainText(rewardCard({id:2,name:'Khăn',description:'',reward_type:'physical_gift',points_cost:100,reward_value:'0.00',apply_to:null,minimum_spend:null,validity_days:null,stock:0},500));
    assert.match(gift,/Quyền lợi Quà nhận tại Bin Spa/);
    assert.ok(!/Áp dụng|Đơn tối thiểu/.test(gift)&&/Hết quà/.test(gift),gift);
});

test('my rewards card shows code, value, scope, minimum, dates and status labels',()=>{
    const {offerCard,statusLabel}=customerRender();
    const offer={id:9,code:'BIN-ABC',status:'available',points_spent:200,redeemed_at:'2026-10-04T03:00:00Z',expires_at:'2026-11-03T03:00:00Z',
        reward:{name:'Voucher 50k',reward_type:'voucher_amount',reward_value:'50000.00',apply_to:'service_invoice',minimum_spend:'300000.00'}};
    const text=plainText(offerCard(offer));
    for(const expected of [/Voucher 50k/,/Có thể sử dụng/,/Mã ưu đãi: BIN-ABC/,/Giảm 50\.000\s₫/,/Áp dụng Hóa đơn dịch vụ/,/Đơn tối thiểu 300\.000\s₫/,/Ngày đổi 10:00:00 4\/10\/2026/,/Hạn dùng 10:00:00 3\/11\/2026/,/thanh toán hóa đơn dịch vụ từ 300\.000\s₫/])assert.match(text,expected);
    assert.ok(!/cần nhập|Mã giảm giá/i.test(text),text);
    // Legacy snapshot without terms is usable everywhere with no minimum.
    assert.match(plainText(offerCard({...offer,reward:{name:'Cũ',reward_type:'voucher_amount',reward_value:'20000.00'}})),/Áp dụng Dịch vụ và gói.*Đơn tối thiểu Không yêu cầu/);
    const gift={...offer,reward:{name:'Khăn',reward_type:'physical_gift'}};
    const labels=[['available',offer,'Có thể sử dụng'],['reserved',offer,'Đang áp dụng'],['used',offer,'Đã sử dụng'],['expired',offer,'Đã hết hạn'],['available',gift,'Chờ nhận quà'],['fulfilled',gift,'Đã nhận quà']];
    for(const [status,base,label] of labels)assert.equal(statusLabel({...base,status}),label);
});

test('physical gift card guides pickup and shows the received date',()=>{
    const {offerCard}=customerRender();
    const gift={id:3,code:'BIN-GIFT',points_spent:100,redeemed_at:'2026-10-04T03:00:00Z',expires_at:null,reward:{name:'Khăn tắm',reward_type:'physical_gift'}};
    const waiting=plainText(offerCard({...gift,status:'available'}));
    assert.match(waiting,/Chờ nhận quà.*Vui lòng đưa mã này cho nhân viên Bin Spa\./);
    assert.ok(!/Giảm|Áp dụng|Đơn tối thiểu|Ngày nhận quà/.test(waiting),waiting);
    const received=plainText(offerCard({...gift,status:'fulfilled',fulfilled_at:'2026-10-05T02:30:00Z'}));
    assert.match(received,/Đã nhận quà.*Ngày nhận quà 09:30:00 5\/10\/2026.*Bạn đã nhận quà lúc 09:30:00 5\/10\/2026/);
    assert.ok(!received.includes('Sao chép'),received);
});

test('percent voucher card, offer and payment picker show percent, cap, scope and minimum',async()=>{
    const {rewardCard,offerCard}=customerRender();
    const reward={id:7,name:'GIẢM 10%',description:'',reward_type:'voucher_percent',points_cost:300,reward_value:'0.00',percentage_value:'10.00',max_discount_amount:'100000.00',apply_to:'both',minimum_spend:'300000.00',validity_days:30,stock:null};
    const card=plainText(rewardCard(reward,500));
    for(const expected of [/GIẢM 10%/,/Điểm cần đổi 300 điểm/,/Giảm 10%/,/Tối đa 100\.000\s₫/,/Áp dụng Dịch vụ và gói/,/Đơn tối thiểu 300\.000\s₫/,/Hạn 30 ngày sau khi đổi/])assert.match(card,expected);
    assert.ok(!/Giảm 0/.test(card),card);
    assert.match(plainText(rewardCard({...reward,percentage_value:'12.50',max_discount_amount:null},500)),/Giảm 12,5%.*Tối đa Không giới hạn/);
    const offer=plainText(offerCard({id:1,code:'BIN-P',status:'available',points_spent:300,redeemed_at:'2026-10-04T03:00:00Z',expires_at:null,reward}));
    assert.match(offer,/Giảm 10%.*Tối đa 100\.000\s₫.*Áp dụng Dịch vụ và gói.*Đơn tối thiểu 300\.000\s₫/);
    const vouchers=[{id:11,code:'BIN-P',status:'available',reward},{id:12,code:'BIN-Q',status:'available',reward:{...reward,name:'Giảm 5%',percentage_value:'5.00',max_discount_amount:null,minimum_spend:'0.00'}}];
    const {vouchersHtml}=await mountPayment('/api/payment/invoices/31',{vouchers});
    assert.match(vouchersHtml,/GIẢM 10% · BIN-P · Giảm 10% \(tối đa 100\.000\s₫\) · Đơn từ 300\.000\s₫ · Cả hai/);
    assert.match(vouchersHtml,/Giảm 5% · BIN-Q · Giảm 5% · Không yêu cầu đơn tối thiểu · Cả hai/);
});
