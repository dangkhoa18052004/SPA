// Legacy shell and inbox share a list-only poll. No message GETs for badges.
(() => {
    let timer,request,version=0,ticking=false,paused=false;
    const publish=data=>{
        const rows=(data.conversations||[]).sort((a,b)=>(Date.parse(b.last_message_time)||0)-(Date.parse(a.last_message_time)||0)||b.maht-a.maht);
        const count=rows.reduce((n,c)=>n+Math.max(0,Number(c.unread_count)||0),0);
        for(const link of document.querySelectorAll('a[href="/admin/chat"]')){
            let badge=link.querySelector('[data-chat-unread]');
            if(!badge){badge=document.createElement('span');badge.dataset.chatUnread='';badge.className='legacy-chat-unread';link.append(badge);}
            badge.hidden=!count;badge.textContent=count>99?'99+':String(count);badge.setAttribute('aria-label',`${count} tin chưa đọc`);
        }
        const result={...data,conversations:rows};document.dispatchEvent(new CustomEvent('binspa:inbox',{detail:result}));return result;
    };
    async function refresh(force=false){
        if(document.hidden||!localStorage.getItem('admin_token'))return;
        if(request&&!force)return request;
        const id=++version;
        request=(async()=>{const r=await fetch('/api/chat/conversations',{headers:getAuthHeaders(false)});if(!r.ok)throw Error('Không tải được hộp thư');const d=await r.json();return id===version?publish(d):d;})();
        try{return await request;}finally{if(id===version)request=null;}
    }
    const tick=()=>{clearTimeout(timer);if(paused||document.hidden||ticking)return;ticking=true;refresh().catch(()=>{}).finally(()=>{ticking=false;if(!paused&&!document.hidden)timer=setTimeout(tick,15000);});};
    window.AdminChatInbox={refresh};
    document.addEventListener('visibilitychange',tick);
    document.addEventListener('binspa:sidebar-ready',tick);
    window.addEventListener('pagehide',()=>{paused=true;++version;clearTimeout(timer);request=null;});
    window.addEventListener('pageshow',()=>{paused=false;tick();});
    document.addEventListener('DOMContentLoaded',tick);
})();
