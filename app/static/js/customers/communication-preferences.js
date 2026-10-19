(() => {
    'use strict';
    document.addEventListener('DOMContentLoaded',async()=>{
        const form=document.getElementById('communicationPreferences');if(!form)return;
        const note=document.getElementById('communicationStatus'),retry=document.getElementById('reloadCommunicationPreferences');
        const fields=['reminders','post_care','review_requests','personalization'],submit=form.querySelector('[type=submit]');
        let version=null,loading=false,saving=false;
        function sync(){
            const blocked=loading||saving||version===null;
            form.querySelectorAll('fieldset').forEach(fieldset=>fieldset.disabled=blocked);submit.disabled=blocked;retry.disabled=loading||saving;
            if(loading||saving)form.setAttribute('aria-busy','true');else form.removeAttribute('aria-busy');
        }
        function announce(message,state=''){
            note.textContent=message;note.className=state;note.setAttribute('role',state==='is-error'?'alert':'status');
        }
        async function api(options={}){
            const controller=new AbortController(),timeout=window.setTimeout(()=>controller.abort(),20000);
            try{
                let r;
                try{r=await window.CustomerAuth.fetch('/api/me/communication-preferences',{...options,signal:controller.signal});}
                catch{throw new Error('Không thể kết nối máy chủ. Vui lòng tải lại lựa chọn để kiểm tra trước khi lưu lại.');}
                const d=await r.json().catch(()=>null);
                if(!r.ok)throw Object.assign(new Error(d?.message||d?.msg||'Chưa tải được lựa chọn.'),{status:r.status});
                if(!d||!Number.isInteger(d.version)||d.version<0||fields.some(k=>typeof d[k]!=='boolean'))throw new Error('Chưa nhận được lựa chọn hợp lệ. Vui lòng tải lại.');
                return d;
            }finally{window.clearTimeout(timeout);}
        }
        function render(d){version=d.version;fields.forEach(k=>{form.elements[k].checked=d[k]});}
        async function load(){
            if(loading||saving)return;
            loading=true;version=null;sync();retry.hidden=true;announce('Đang tải lựa chọn…');
            try{render(await api());announce('');}
            catch(e){announce(e.message,'is-error');retry.hidden=false;}
            finally{loading=false;sync();}
        }
        retry.onclick=load;
        form.onsubmit=async e=>{
            e.preventDefault();if(version===null||loading||saving||submit.disabled)return;
            const data={version};fields.forEach(k=>{data[k]=form.elements[k].checked});saving=true;sync();retry.hidden=true;announce('Đang lưu…');
            try{render(await api({method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}));announce('Đã lưu lựa chọn của bạn.','is-success');}
            catch(error){
                // After a conflict or uncertain result, reload the authoritative version before another write.
                if(error.status!==400&&error.status!==422)version=null;
                announce(error.message,'is-error');retry.hidden=false;
            }finally{saving=false;sync();}
        };
        document.addEventListener('customer:section',event=>{if(event.detail==='communication')load();});
    });
})();
