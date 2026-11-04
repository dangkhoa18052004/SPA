// Server owns persisted categories, filtering, ranking and opt-in pagination.
let currentCategory='all',catalogPage=1,catalogRequest=0,catalogController,catalogTimer;
const catalogRanges=['min_price','max_price','min_duration','max_duration'];
const catalogEsc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const catalogFetch=(url,options)=>window.CustomerAuth?window.CustomerAuth.fetch(url,options):fetch(url,options);
document.addEventListener('DOMContentLoaded',()=>{
    setupCatalogFilterDrawer();
    restoreCatalogFilters();loadCategories();loadAllServices();
    document.getElementById('searchInput').addEventListener('input',()=>{
        clearTimeout(catalogTimer);catalogController?.abort();++catalogRequest;
        catalogTimer=setTimeout(()=>filterServices(),300);
    });
    document.querySelectorAll('[data-catalog-range]').forEach(i=>i.addEventListener('change',()=>filterServices()));
});
function setupCatalogFilterDrawer(){
    const group=document.querySelector('.catalog-range-grid'),desktop=document.querySelector('.catalog-advanced'),mobile=document.getElementById('catalogMobileRanges'),dialog=document.getElementById('catalogFilterDialog');
    const media=window.matchMedia('(max-width: 639px)');
    const sync=()=>{if(dialog.open)dialog.close();(media.matches?mobile:desktop).append(group);};
    sync();media.addEventListener('change',sync);
}
window.addEventListener('popstate',()=>{clearTimeout(catalogTimer);restoreCatalogFilters();loadAllServices();});
function restoreCatalogFilters(){
    const p=new URLSearchParams(location.search);currentCategory=p.get('category')||'all';catalogPage=Math.max(1,Number(p.get('page'))||1);
    document.getElementById('searchInput').value=p.get('search')||'';
    const sort=document.getElementById('sortSelect');sort.value=[...sort.options].some(o=>o.value===p.get('sort'))?p.get('sort'):'default';
    catalogRanges.forEach(k=>{document.getElementById(k).value=p.get(k)||'';});markCatalogCategory();
}
async function loadCategories(){
    const root=document.getElementById('catalogCategories');
    try{
        const r=await catalogFetch('/api/services/categories');if(!r.ok)throw Error();const d=await r.json();root.replaceChildren();
        for(const c of [{slug:'all',name:'Tất cả'},...d.categories]){
            const b=document.createElement('button');b.type='button';b.className='filter-btn';b.dataset.category=c.slug;
            b.textContent=c.name+(c.service_count==null?'':` (${c.service_count})`);b.onclick=()=>filterByCategory(c.slug);root.append(b);
        }markCatalogCategory();
    }catch(e){root.innerHTML='<span role="alert">Chưa tải được danh mục.</span><button type="button" class="filter-btn" onclick="loadCategories()">Thử lại</button>';}
}
function markCatalogCategory(){document.querySelectorAll('[data-category]').forEach(b=>{const active=b.dataset.category===currentCategory;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});}
function catalogParams(){
    const p=new URLSearchParams({page:String(catalogPage),per_page:'9'});
    if(currentCategory!=='all')p.set('category',currentCategory);
    const s=document.getElementById('searchInput').value.trim();if(s)p.set('search',s);
    const sort=document.getElementById('sortSelect').value;if(sort!=='default')p.set('sort',sort);
    catalogRanges.forEach(k=>{const v=document.getElementById(k).value;if(v!=='')p.set(k,v);});return p;
}
function syncCatalogUrl(){
    const p=catalogParams(),url=new URL(location.href);
    for(const k of ['page','per_page','category','search','sort',...catalogRanges])url.searchParams.delete(k);
    p.delete('per_page');if(catalogPage===1)p.delete('page');p.forEach((v,k)=>url.searchParams.set(k,v));
    if(url.href!==location.href)history.pushState(null,'',url.pathname+url.search+url.hash);
}
function filterServices(){catalogPage=1;syncCatalogUrl();return loadAllServices();}
function filterByCategory(c){currentCategory=c;markCatalogCategory();return filterServices();}
function sortServices(){return filterServices();}
function clearServiceFilters(){currentCategory='all';document.getElementById('searchInput').value='';document.getElementById('sortSelect').value='default';catalogRanges.forEach(k=>{document.getElementById(k).value='';});markCatalogCategory();return filterServices();}
async function loadAllServices(){
    const request=++catalogRequest;catalogController?.abort();catalogController=new AbortController();
    const root=document.getElementById('servicesGrid'),count=document.getElementById('catalogResultCount');
    root.setAttribute('aria-busy','true');root.innerHTML=Array.from({length:9},()=>'<div class="service-skeleton" aria-hidden="true"><div class="skeleton-image"></div><div class="skeleton-content">Đang tải…</div></div>').join('');
    document.getElementById('noResults').hidden=true;document.getElementById('catalogPagination').replaceChildren();count.textContent='Đang tải dịch vụ…';
    try{
        const r=await catalogFetch('/api/services?'+catalogParams(),{signal:catalogController.signal}),d=await r.json();if(request!==catalogRequest)return;
        if(!r.ok||!d.success)throw Error(d.message||d.msg||'Không thể tải dịch vụ.');
        if(d.total_pages&&catalogPage>d.total_pages){catalogPage=d.total_pages;syncCatalogUrl();return loadAllServices();}
        displayServices(d.services);document.getElementById('noResults').hidden=d.total!==0;
        const first=d.total?(catalogPage-1)*9+1:0;count.textContent=`Hiển thị ${first}–${first?first+d.services.length-1:0} / ${d.total} dịch vụ`;renderCatalogPagination(d.total_pages);
        document.getElementById('catalogActiveFilters').textContent=[currentCategory!=='all'?`Danh mục: ${document.querySelector('[data-category="'+CSS.escape(currentCategory)+'"]')?.textContent||currentCategory}`:'',...catalogRanges.filter(k=>document.getElementById(k).value).map(k=>`${document.querySelector('label[for="'+k+'"]').textContent}: ${document.getElementById(k).value}`)].filter(Boolean).join(' · ');
    }catch(e){if(request!==catalogRequest||e.name==='AbortError')return;root.innerHTML=`<div class="catalog-state" role="alert"><p>${catalogEsc(e.message)}</p><button type="button" class="btn btn-outline" onclick="loadAllServices()">Thử lại</button></div>`;count.textContent='Chưa tải được kết quả.';
    }finally{if(request===catalogRequest)root.setAttribute('aria-busy','false');}
}
function displayServices(services){
    document.getElementById('servicesGrid').innerHTML=services.map(s=>{
        if(window.CustomerCatalog)return window.CustomerCatalog.serviceCard(s,s.category_name||'Chưa phân loại');
        const id=Number(s.madv),name=catalogEsc(s.tendv);
        return `<article class="service-card" data-service-id="${id}"><a class="service-image-container" href="/services/${id}" tabindex="-1" aria-hidden="true"><img class="service-image" src="${s.anhdichvu?'data:image/jpeg;base64,'+catalogEsc(s.anhdichvu):'/static/images/default-service.jpg'}" alt="" width="640" height="480" loading="lazy" onerror="this.onerror=null;this.src='/static/images/default-service.jpg'"></a><div class="service-content"><span class="service-category">${catalogEsc(s.category_name||'Chưa phân loại')}</span><h3 class="service-name"><a href="/services/${id}">${name}</a></h3><p class="service-description">${catalogEsc(s.mota)}</p><div class="service-meta"><span class="service-price">${formatPrice(s.gia)}</span><span>${Number(s.thoiluong)||0} phút</span></div><div class="service-actions"><a class="btn btn-primary" href="/appointments/create?service=${id}">Đặt lịch</a><a class="btn btn-outline" href="/services/${id}">Chi tiết</a></div></div></article>`;
    }).join('');
}
function renderCatalogPagination(total){
    const root=document.getElementById('catalogPagination');root.replaceChildren();if(total<=1)return;
    const pages=[1,...Array.from({length:5},(_,i)=>catalogPage+i-2).filter(p=>p>1&&p<total),total];
    const add=(text,p,disabled,current=false)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.disabled=disabled;b.className='btn btn-outline';if(current)b.setAttribute('aria-current','page');b.onclick=()=>{catalogPage=p;syncCatalogUrl();loadAllServices().then(()=>{const el=document.getElementById('catalogResultCount');el.focus({preventScroll:true});el.scrollIntoView({block:'start',behavior:'instant'});});};root.append(b);};
    add('Trước',catalogPage-1,catalogPage===1);let last=0;
    for(const p of pages){if(p===last)continue;if(last&&p>last+1)root.append(document.createTextNode('…'));add(String(p),p,false,p===catalogPage);last=p;}
    add('Sau',catalogPage+1,catalogPage===total);
}
function viewServiceDetail(id){location.href=`/services/${Number(id)}`;}
function formatPrice(v){return v==null?'Liên hệ':new Intl.NumberFormat('vi-VN',{style:'currency',currency:'VND'}).format(Number(v));}
