(() => {
    'use strict';
    document.addEventListener('DOMContentLoaded',async()=>{
        const form=document.getElementById('communicationPreferences');if(!form)return;
        const note=document.getElementById('communicationStatus'),retry=document.getElementById('reloadCommunicationPreferences');
        const fields=['reminders','post_care','review_requests','personalization'],submit=form.querySelector('[type=submit]');
        let version=null;
        function busy(value){form.querySelector('fieldset').disabled=value;submit.disabled=value||version===null;}
        async function api(options){const r=await window.CustomerAuth.fetch('/api/me/communication-preferences',options),d=await r.json();if(!r.ok)throw new Error(d.message||d.msg||'Chưa tải được lựa chọn.');return d;}
        function render(d){version=d.version;fields.forEach(k=>{form.elements[k].checked=d[k]});}
        async function load(){busy(true);retry.hidden=true;note.textContent='Đang tải lựa chọn…';try{render(await api());note.textContent='';}catch(e){note.textContent=e.message;retry.hidden=false;}finally{busy(false);}}
        retry.onclick=load;
        form.onsubmit=async e=>{
            e.preventDefault();if(version===null||submit.disabled)return;
            const data={version};fields.forEach(k=>{data[k]=form.elements[k].checked});busy(true);retry.hidden=true;note.textContent='Đang lưu…';
            try{render(await api({method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}));note.textContent='Đã lưu lựa chọn của bạn.';}catch(error){note.textContent=error.message;retry.hidden=false;}finally{busy(false);}
        };
        if(await window.CustomerAuth.restoreAccessToken())await load();
    });
})();
