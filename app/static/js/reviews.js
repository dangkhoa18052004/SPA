(() => {
    'use strict';
    const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const stars=n=>'★'.repeat(Number(n))+'☆'.repeat(5-Number(n));
    const date=value=>value?new Date(value.endsWith('Z')?value:value+'Z').toLocaleString('vi-VN'):'';
    let mine=[], adminPage=1, publicPage=1;
    async function api(url,method='GET',body,admin=false){
        const headers=admin?window.getAuthHeaders(Boolean(body)):{'Content-Type':'application/json'};
        const fetcher=!admin&&window.CustomerAuth?CustomerAuth.fetch.bind(CustomerAuth):fetch;
        const response=await fetcher(url,{method,headers,cache:'no-store',...(body?{body:JSON.stringify(body)}:{})});
        const result=await response.json();
        if(!response.ok)throw new Error(result.message||result.msg||'Không thể tải đánh giá.');
        return result;
    }
    const replyHtml=reply=>reply?`<div class="review-reply"><strong>Phản hồi từ Bin Spa</strong><p>${esc(reply.content)}</p><small>${date(reply.updated_at||reply.created_at)}</small></div>`:'';
    const cardHtml=r=>`<div class="review-stars" aria-label="${r.rating} sao">${stars(r.rating)}</div><strong>${esc(r.services||r.service_items?.map(s=>s.tendv).join(', ')||'Dịch vụ Spa')}</strong><p>${esc(r.comment)}</p><small class="review-muted">${date(r.updated_at||r.created_at)}</small>${replyHtml(r.reply)}`;
    function dialog(title,content){
        document.getElementById('spaReviewDialog')?.remove();
        const el=document.createElement('dialog');el.id='spaReviewDialog';el.className='spa-review-dialog';
        el.setAttribute('aria-labelledby','spaReviewTitle');
        el.innerHTML=`<header class="review-dialog-header"><h2 id="spaReviewTitle">${esc(title)}</h2><button type="button" class="review-dialog-close" data-close aria-label="Đóng đánh giá">×</button></header>${content}<div class="review-actions"><button type="button" class="btn btn-secondary review-close-button" data-close>Đóng</button></div>`;
        el.querySelectorAll('[data-close]').forEach(button=>button.onclick=()=>el.close());
        const outside=event=>{
            const rect=el.getBoundingClientRect();
            return event.target===el&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom);
        };
        let backdropPress=false;
        el.addEventListener('pointerdown',event=>{backdropPress=outside(event);});
        el.addEventListener('click',event=>{if(backdropPress&&outside(event))el.close();backdropPress=false;});
        el.addEventListener('close',()=>el.remove());
        document.body.append(el);el.showModal();return el;
    }
    async function loadMy(){
        const list=document.getElementById('myReviews');if(!list)return;
        try{
            mine=(await api('/api/reviews/my')).reviews;
            list.innerHTML=mine.length?mine.map(r=>`<article class="review-card" id="my-review-${r.madg}">${cardHtml(r)}<p class="review-muted">Lịch hẹn #${r.malh}</p><div class="review-actions"><button class="btn btn-outline" data-edit-review="${r.madg}">Sửa đánh giá</button><button class="btn btn-outline" data-delete-review="${r.madg}">Xóa đánh giá</button></div></article>`).join(''):'Bạn chưa có đánh giá nào.';
        }catch(error){list.textContent=error.message;}
    }
    async function changed(){await loadMy();document.dispatchEvent(new CustomEvent('reviews-updated'));}
    function editor(context,existing=null){
        const services=context.services||existing.service_items;
        const el=dialog(existing?'Sửa đánh giá':'Đánh giá dịch vụ',`<form><p>Lịch hẹn #${context.malh||existing?.malh}</p>${!existing&&services.length>1?`<fieldset><legend>Chọn dịch vụ đã sử dụng muốn đánh giá</legend>${services.map(s=>`<label><input type="checkbox" name="service" value="${s.madv}">${esc(s.tendv)}</label>`).join('')}</fieldset>`:`<p>${esc(services.map(s=>s.tendv).join(', '))}</p>`}<div data-rating-picker></div><label>Nhận xét<textarea name="comment" rows="4" maxlength="5000">${esc(existing?.comment||'')}</textarea></label><button class="btn btn-primary" type="submit">${existing?'Lưu thay đổi':'Gửi đánh giá'}</button><p data-error role="alert"></p></form>`);
        const form=el.querySelector('form');
        const initialRating=Number(existing?.rating||5);
        form.querySelector('[data-rating-picker]').outerHTML=`<fieldset class="review-rating"><legend>Mức độ hài lòng</legend><div class="review-rating-options">${[1,2,3,4,5].map(n=>`<label class="review-rating-option"><input type="radio" name="rating" value="${n}" ${initialRating===n?'checked':''} required aria-label="${n} sao"><span aria-hidden="true">★</span></label>`).join('')}</div><output class="review-rating-value" aria-live="polite"></output></fieldset>`;
        const ratingOptions=form.querySelector('.review-rating-options');
        const paintRating=(value,preview=false)=>{
            ratingOptions.querySelectorAll('.review-rating-option').forEach(option=>option.classList.toggle('is-active',Number(option.querySelector('input').value)<=value));
            form.querySelector('.review-rating-value').textContent=`${value}/5${preview?' · Xem trước':''}`;
        };
        ratingOptions.querySelectorAll('.review-rating-option').forEach(option=>option.addEventListener('pointerenter',event=>{
            if(event.pointerType!=='touch')paintRating(Number(option.querySelector('input').value),true);
        }));
        ratingOptions.addEventListener('pointerleave',()=>paintRating(Number(form.elements.rating.value)));
        ratingOptions.addEventListener('change',()=>paintRating(Number(form.elements.rating.value)));
        paintRating(initialRating);
        form.onsubmit=async event=>{
            event.preventDefault();const button=form.querySelector('[type="submit"]');button.disabled=true;
            const payload={rating:Number(form.elements.rating.value),comment:form.elements.comment.value};
            if(!existing){payload.malh=context.malh;payload.service_ids=services.length===1?[services[0].madv]:[...form.querySelectorAll('[name="service"]:checked')].map(i=>Number(i.value));}
            try{await api(existing?`/api/reviews/${existing.madg}`:'/api/reviews',existing?'PUT':'POST',payload);el.close();await changed();}
            catch(error){el.querySelector('[data-error]').textContent=error.message;}finally{button.disabled=false;}
        };
    }
    async function openAppointmentReview(malh){
        try{
            const context=await api(`/api/reviews/appointments/${malh}/context`);
            if(!context.review){editor(context);return;}
            const r=context.review;
            const el=dialog('Đánh giá của bạn',`${cardHtml(r)}<div class="review-actions"><button class="btn btn-primary" data-edit>Sửa đánh giá</button><button class="btn btn-outline" data-delete>Xóa đánh giá</button></div>`);
            el.querySelector('[data-edit]').onclick=()=>{el.close();editor(context,r);};
            el.querySelector('[data-delete]').onclick=async()=>{if(await removeReview(r.madg))el.close();};
        }catch(error){dialog('Đánh giá dịch vụ',`<p role="alert">${esc(error.message)}</p>`);}
    }
    async function removeReview(id){
        if(!confirm('Bạn có chắc muốn xóa đánh giá này?'))return false;
        try{await api(`/api/reviews/${id}`,'DELETE');await changed();return true;}
        catch(error){dialog('Không thể xóa',`<p>${esc(error.message)}</p>`);return false;}
    }
    async function loadPublic(){
        const root=document.querySelector('[data-service-reviews]');if(!root)return;
        const id=location.pathname.split('/').pop();
        try{
            const r=await api(`/api/services/${id}/reviews?page=${publicPage}`);
            root.querySelector('[data-stats]').innerHTML=`<strong>${r.stats.average_rating}/5</strong> · ${r.stats.total_reviews} đánh giá<div class="review-muted">${[5,4,3,2,1].map(n=>`${n}★: ${r.stats.distribution[String(n)]}`).join(' · ')}</div>`;
            root.querySelector('[data-list]').innerHTML=r.reviews.length?r.reviews.map(item=>`<article class="review-card"><strong>${esc(item.customer_name)}</strong><p class="review-muted">✓ Đã sử dụng dịch vụ</p>${cardHtml(item)}</article>`).join(''):'Chưa có đánh giá cho dịch vụ này.';
            pagination(root.querySelector('[data-pages]'),r.page,r.total,r.per_page,page=>{publicPage=page;loadPublic();});
        }catch(error){root.querySelector('[data-list]').textContent=error.message;}
    }
    function pagination(el,page,total,perPage,change){
        const max=Math.max(1,Math.ceil(total/perPage));
        el.innerHTML=`<button class="btn btn-outline" data-prev ${page<=1?'disabled':''}>Trước</button><span>Trang ${page}/${max}</span><button class="btn btn-outline" data-next ${page>=max?'disabled':''}>Sau</button>`;
        el.querySelector('[data-prev]').onclick=()=>change(page-1);el.querySelector('[data-next]').onclick=()=>change(page+1);
    }
    async function loadAdmin(){
        const root=document.getElementById('adminReviews');if(!root)return;
        const form=document.getElementById('reviewFilters');const params=new URLSearchParams(new FormData(form));params.set('page',adminPage);
        try{
            const r=await api('/api/reviews/manage?'+params,'GET',null,true);
            root.innerHTML=r.reviews.length?r.reviews.map(item=>`<article class="review-card"><strong>${esc(item.customer_name)}</strong><p class="review-muted">Lịch #${item.malh} · ${esc(item.staff_name)}</p>${cardHtml(item)}<div class="review-actions"><button class="btn btn-primary" data-reply-review="${item.madg}">${item.reply?'Sửa phản hồi':'Trả lời'}</button>${item.reply?`<button class="btn btn-secondary" data-delete-reply="${item.madg}">Xóa phản hồi</button>`:''}</div></article>`).join(''):'Không tìm thấy đánh giá.';
            if(!form.dataset.loaded){
                form.elements.service.insertAdjacentHTML('beforeend',r.services.map(s=>`<option value="${s.madv}">${esc(s.tendv)}</option>`).join(''));
                form.elements.staff.insertAdjacentHTML('beforeend',r.staff.map(s=>`<option value="${s.manv}">${esc(s.hoten)}</option>`).join(''));
                form.elements.staff.hidden=!r.staff.length;form.dataset.loaded='true';
            }
            root.querySelectorAll('[data-reply-review]').forEach(button=>button.onclick=()=>replyEditor(r.reviews.find(item=>item.madg===Number(button.dataset.replyReview))));
            root.querySelectorAll('[data-delete-reply]').forEach(button=>button.onclick=async()=>{
                if(!confirm('Xóa phản hồi của Spa?'))return;
                try{await api(`/api/reviews/${button.dataset.deleteReply}/reply`,'DELETE',null,true);await loadAdmin();}catch(error){dialog('Lỗi',`<p>${esc(error.message)}</p>`);}
            });
            pagination(document.getElementById('adminReviewPages'),r.page,r.total,r.per_page,page=>{adminPage=page;loadAdmin();});
        }catch(error){root.textContent=error.message;}
    }
    function replyEditor(review){
        const el=dialog('Phản hồi từ Bin Spa',`<form><p>${esc(review.customer_name)} · Lịch #${review.malh}</p><label>Nội dung<textarea name="content" maxlength="5000" required rows="4">${esc(review.reply?.content||'')}</textarea></label><button class="btn btn-primary" type="submit">Lưu phản hồi</button><p data-error role="alert"></p></form>`);
        el.querySelector('form').onsubmit=async event=>{
            event.preventDefault();const button=el.querySelector('[type="submit"]');button.disabled=true;
            try{await api(`/api/reviews/${review.madg}/reply`,review.reply?'PUT':'POST',{content:el.querySelector('textarea').value},true);el.close();await loadAdmin();}
            catch(error){el.querySelector('[data-error]').textContent=error.message;}finally{button.disabled=false;}
        };
    }
    document.addEventListener('click',event=>{
        const edit=event.target.closest('[data-edit-review]'),remove=event.target.closest('[data-delete-review]');
        if(edit){const r=mine.find(item=>item.madg===Number(edit.dataset.editReview));if(r)editor({malh:r.malh},r);}
        if(remove)removeReview(Number(remove.dataset.deleteReview));
    });
    document.addEventListener('DOMContentLoaded',async()=>{
        if(document.getElementById('myReviews')){await loadMy();document.dispatchEvent(new CustomEvent('reviews-updated'));}
        if(document.getElementById('reviewFilters')){const form=document.getElementById('reviewFilters');form.onchange=()=>{adminPage=1;loadAdmin();};form.onsubmit=event=>{event.preventDefault();adminPage=1;loadAdmin();};loadAdmin();}
        loadPublic();
    });
    window.ReviewUI={openAppointmentReview,loadMy,appointmentActions:malh=>`<button class="btn btn-primary" onclick="ReviewUI.openAppointmentReview(${malh})">${mine.some(r=>r.malh===malh)?'Xem đánh giá':'Đánh giá'}</button>`};
})();
