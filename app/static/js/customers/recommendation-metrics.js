/* Authenticated top-six impressions; no anonymous identifier or fingerprint. */
(() => {
    'use strict';
    const placement = location.pathname === '/' ? 'home' : /^\/services\/\d+/.test(location.pathname) ? 'related' : location.pathname === '/services' ? 'catalog' : location.pathname === '/appointments/create' ? 'booking' : null;
    if (!placement || !window.IntersectionObserver || !window.MutationObserver) return;
    const selector = '[data-service-id], [data-package-id]';
    const observed = new WeakSet(), visible = new WeakSet(), timers = new WeakMap(), inFlight = new Map();
    const target = el => ({type:el.dataset.serviceId?'service':'package',id:Number(el.dataset.serviceId||el.dataset.packageId)});
    function position(el) {
        const unique=[];
        for(const card of document.querySelectorAll(selector)){
            if(!card.getClientRects().length)continue;
            const v=target(card),key=v.type+':'+v.id;
            if(!unique.includes(key))unique.push(key);
        }
        const v=target(el);return unique.indexOf(v.type+':'+v.id)+1;
    }
    async function register(el) {
        if(document.visibilityState!=='visible')return null;
        const value=target(el),index=position(el),key=value.type+':'+value.id;
        if(!value.id||index<1||index>6)return null;
        if(inFlight.has(key))return inFlight.get(key);
        const pending=(async()=>{
            try{
                const auth=window.CustomerAuth;
                if(!auth||!(auth.getAccessToken()||await auth.restoreAccessToken()))return null;
                if(!el.isConnected||!visible.has(el))return null;
                const response=await auth.fetch('/api/recommendations/impressions',{method:'POST',keepalive:true,
                    headers:{'Content-Type':'application/json'},body:JSON.stringify({placement,items:[{...value,position:index}]})});
                if(!response.ok)return null;
                return (await response.json()).items[0]?.id||null;
            }catch(_){return null;}
        })();
        inFlight.set(key,pending);const result=await pending;if(!result)inFlight.delete(key);return result;
    }
    function dwell(el){clearTimeout(timers.get(el));timers.set(el,setTimeout(()=>{if(el.isConnected&&visible.has(el))void register(el)},600));}
    const observer=new IntersectionObserver(entries=>{
        for(const e of entries){
            if(e.isIntersecting&&e.intersectionRatio>=.5){visible.add(e.target);dwell(e.target);}
            else{visible.delete(e.target);clearTimeout(timers.get(e.target));}
        }
    },{threshold:[0,.5]});
    document.addEventListener('visibilitychange',()=>{for(const el of document.querySelectorAll(selector)){clearTimeout(timers.get(el));if(document.visibilityState==='visible'&&visible.has(el))dwell(el);}});
    function scan(){for(const el of document.querySelectorAll(selector)){if(observed.has(el))continue;observed.add(el);observer.observe(el);}}
    document.addEventListener('click',event=>{
        const el=event.target.closest(selector);if(!el)return;
        const v=target(el),key=v.type+':'+v.id;visible.add(el);
        void Promise.resolve(inFlight.get(key)||register(el)).then(id=>id&&window.CustomerAuth.fetch(`/api/recommendations/impressions/${encodeURIComponent(id)}/click`,{
            method:'POST',keepalive:true,headers:{'Content-Type':'application/json'},body:'{}'
        })).catch(()=>{});
    },true);
    document.addEventListener('DOMContentLoaded',()=>{scan();new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});});
})();
