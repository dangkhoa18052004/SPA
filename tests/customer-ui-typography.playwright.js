// Run with Playwright CLI from a public page or an authenticated /profile page.
// Reads styles only; never submits a form or creates a booking/payment.
async page => {
  const base = new URL(page.url()).origin;
  const account = new URL(page.url()).pathname === '/profile';
  const local = new URL(base).hostname === '127.0.0.1';
  const out = '.test-tmp/customer-ui-2026-10-19/';
  const errors = [], failed = [], http = [], results = [];
  const safeUrl = url => { const u = new URL(url); return u.origin + u.pathname; };
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => {if(r.failure()?.errorText !== 'net::ERR_ABORTED') failed.push({url:safeUrl(r.url()),error:r.failure()?.errorText});});
  page.on('response', r => {if(r.status() >= 400) http.push({url:safeUrl(r.url()),status:r.status()});});
  const paths = account
    ? ['appointments','invoices','treatments','loyalty','reviews','info','edit','password','communication'].map(tab=>'/profile#'+tab).concat('/appointments/create')
    : ['/', '/services', '/packages', '/auth/login', '/auth/register', '/auth/forgot-password', '/auth/verify-otp', '/auth/reset-password', '/appointments/create'];
  if(!account) {
    for(const endpoint of ['/api/services','/api/packages']) {
      const response = await page.request.get(base+endpoint);
      if(!response.ok()) continue;
      const data=await response.json();
      const items=Array.isArray(data)?data:data.services||data.packages||[];
      const id=endpoint.includes('services')?items[0]?.madv:items[0]?.id||items[0]?.magoi;
      if(id) paths.push(endpoint.replace('/api','')+'/'+id);
    }
  }
  for(const width of [360,390,768,1024,1440]) {
    await page.setViewportSize({width,height:900});
    for(const path of paths) {
      // Additional breakpoints cover the shared shells and representative forms.
      if(![390,1440].includes(width) && !(account
        ? ['/profile#appointments','/profile#edit','/appointments/create'].includes(path)
        : ['/','/services','/auth/login','/appointments/create'].includes(path))) continue;
      await page.goto(base+path,{waitUntil:'domcontentloaded'});
      await page.waitForTimeout(700);
      let loadingTimedOut=false;
      try { await page.locator('[aria-busy=true]').first().waitFor({state:'hidden',timeout:20000}); }
      catch { loadingTimedOut=true; }
      await page.evaluate(()=>Promise.race([document.fonts.ready,new Promise(r=>setTimeout(r,1500))]));
      const report=await page.evaluate(()=>{
        // Tailwind may resolve colors to oklab()/color(srgb), not just rgb().
        const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
        const context=canvas.getContext('2d',{willReadFrequently:true});
        const rgb=s=>{context.clearRect(0,0,1,1);context.fillStyle=s;context.fillRect(0,0,1,1);const d=context.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
        const mix=(a,b)=>{const alpha=a[3]??1;return [0,1,2].map(i=>a[i]*alpha+b[i]*(1-alpha)).concat(1);};
        const lum=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((v,x,i)=>v+x*[.2126,.7152,.0722][i],0);
        const contrast=(fg,bg)=>{const l=[lum(mix(rgb(fg),bg)),lum(bg)].sort((a,b)=>b-a);return +( (l[0]+.05)/(l[1]+.05)).toFixed(2);};
        const visible=e=>{const r=e.getBoundingClientRect();if(!r.width||!r.height)return false;for(let n=e;n;n=n.parentElement){const s=getComputedStyle(n);if(s.visibility!=='visible'||s.display==='none'||s.opacity==='0')return false;}return true;};
        const background=e=>{const chain=[];for(let n=e;n;n=n.parentElement)chain.unshift(n);let bg=[255,255,255,1],complex=false;for(const n of chain){const s=getComputedStyle(n);bg=mix(rgb(s.backgroundColor),bg);if(s.backgroundImage!=='none'||s.opacity!=='1')complex=true;}if(e.closest('.about-content,.hero-content'))complex=true;return {bg,complex};};
        const samples=[],issues=[],seen=new Set();let checked=0,complexCount=0;
        const add=issue=>{const key=JSON.stringify([issue.type,issue.selector,issue.color,issue.bg,issue.size]);if(!seen.has(key)){seen.add(key);issues.push(issue);}};
        for(const e of document.querySelectorAll('body *')) {
          if(!visible(e)||/^(SCRIPT|STYLE|NOSCRIPT|SVG|PATH|IFRAME|OPTION)$/.test(e.tagName))continue;
          const ownText=[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
          const input=e instanceof HTMLInputElement||e instanceof HTMLTextAreaElement;
          if(!ownText&&!input&&!(e instanceof HTMLSelectElement))continue;
          const s=getComputedStyle(e),backgroundInfo=background(e);
          const item={selector:e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+(typeof e.className==='string'?e.className.trim().replaceAll(' ','.'):''),font:s.fontFamily,size:s.fontSize,weight:s.fontWeight,style:s.fontStyle,color:s.color,bg:backgroundInfo.bg.slice(0,3).map(Math.round),lineHeight:s.lineHeight};
          // Do not write customer names, addresses, invoice data, or input values.
          if(samples.length<100)samples.push(item);
          if(/serif/i.test(s.fontFamily)&&!/sans-serif/i.test(s.fontFamily))add({type:'serif-font',...item});
          if(backgroundInfo.complex){complexCount++;continue;}
          const exempt=e.matches(':disabled')||e.closest('[aria-disabled=true],.ant-btn-disabled,.ant-input-disabled');
          if(!exempt&&ownText){checked++;const ratio=contrast(s.color,backgroundInfo.bg),minimum=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700)?3:4.5;if(ratio<minimum)add({type:'contrast',...item,ratio,minimum});}
          if(input&&e.placeholder&&!exempt){const p=getComputedStyle(e,'::placeholder');checked++;const color=mix(rgb(p.color),backgroundInfo.bg);const alpha=Number(p.opacity);const displayed=color.map((x,i)=>i<3?x*alpha+backgroundInfo.bg[i]*(1-alpha):x);const l=[lum(displayed),lum(backgroundInfo.bg)].sort((a,b)=>b-a),ratio=+((l[0]+.05)/(l[1]+.05)).toFixed(2);if(ratio<4.5)add({type:'placeholder-contrast',...item,color:p.color,ratio,minimum:4.5});}
        }
        const b=getComputedStyle(document.body);
        return {url:location.pathname+location.hash,bodyClass:document.body.className,bodyFont:b.fontFamily,bodyColor:b.color,bodyBackground:b.backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth,checked,complexCount,samples,issues};
      });
      const name=(path==='/'?'home':path.slice(1)).replaceAll('/','-').replaceAll('#','-');
      if([390,1440].includes(width))await page.screenshot({path:out+(local?'refactor':'lan')+'-'+name+'-'+width+'.png',fullPage:true});
      results.push({path,width,loadingTimedOut,...report});
    }
  }
  return {base,account,results,errors:[...new Set(errors)],failed,http};
}
