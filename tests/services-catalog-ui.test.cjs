// Catalog now delegates filtering/ranking to the API; test requests and stale-result safety.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/js/customers/services.js','utf8');
function setup(fetcher){
    const nodes={},calls=[],rendered=[];
    for(const id of ['searchInput','sortSelect','min_price','max_price','min_duration','max_duration','servicesGrid','catalogResultCount','catalogActiveFilters','catalogPagination','noResults'])
        nodes[id]={value:id==='sortSelect'?'default':'',innerHTML:'',textContent:'',setAttribute(){},replaceChildren(){},append(){},focus(){},scrollIntoView(){}};
    nodes.sortSelect.options=[{value:'default'},{value:'price-desc'}];
    const location={href:'http://localhost/services',search:''};
    const context={console,Map,Number,Intl,URL,URLSearchParams,AbortController,CSS:{escape:v=>v},location,
        history:{pushState(_a,_b,path){location.href='http://localhost'+path;location.search=new URL(location.href).search;}},
        document:{getElementById:id=>nodes[id],addEventListener(){},querySelectorAll:()=>[],querySelector:()=>null},
        window:{addEventListener(){},CustomerAuth:{fetch:async(url,options)=>{calls.push(url);return fetcher?fetcher(url,options):{ok:true,json:async()=>({success:true,services:[],total:0,total_pages:0})};}}}};
    vm.runInNewContext(source,context);context.displayServices=rows=>rendered.push(rows);
    return {context,nodes,calls,rendered,location};
}
test('catalog explicitly opts into 9-per-page without changing other consumers',async()=>{
    const s=setup();await s.context.loadAllServices();
    const p=new URL(s.calls[0],'http://localhost').searchParams;
    assert.equal(p.get('page'),'1');assert.equal(p.get('per_page'),'9');
});
test('category uses exact persisted slug, with no acne/facial alias',async()=>{
    const s=setup();await s.context.filterByCategory('acne');
    assert.equal(new URL(s.calls.at(-1),'http://localhost').searchParams.get('category'),'acne');
    assert.equal(new URL(s.location.href).searchParams.get('category'),'acne');
});
test('search, ranges and explicit sort are combined by the server before paging',async()=>{
    const s=setup();s.nodes.searchInput.value='Massage %';s.nodes.min_price.value='100000';s.nodes.max_duration.value='60';s.nodes.sortSelect.value='price-desc';
    await s.context.filterServices();const p=new URL(s.calls[0],'http://localhost').searchParams;
    assert.equal(p.get('search'),'Massage %');assert.equal(p.get('min_price'),'100000');assert.equal(p.get('max_duration'),'60');assert.equal(p.get('sort'),'price-desc');
});
test('restored URL keeps its page; a new filter resets to page one',async()=>{
    const s=setup();s.location.search='?page=3&category=acne&search=spa';s.context.restoreCatalogFilters();await s.context.loadAllServices();
    assert.equal(new URL(s.calls[0],'http://localhost').searchParams.get('page'),'3');
    await s.context.filterByCategory('body-care');assert.equal(new URL(s.calls[1],'http://localhost').searchParams.get('page'),'1');
});
test('an older response cannot overwrite the latest request even if abort is ignored',async()=>{
    const pending=[];const s=setup(()=>new Promise(resolve=>pending.push(resolve)));
    const first=s.context.loadAllServices(),second=s.context.filterByCategory('acne');
    pending[1]({ok:true,json:async()=>({success:true,services:[{madv:2}],total:1,total_pages:1})});await second;
    pending[0]({ok:true,json:async()=>({success:true,services:[{madv:1}],total:1,total_pages:1})});await first;
    assert.deepEqual(s.rendered,[[{madv:2}]]);
});
test('server validation/network failures expose a retry without losing the query',async()=>{
    const s=setup(async()=>({ok:false,json:async()=>({message:'<bad range>'})}));s.nodes.searchInput.value='keep';await s.context.filterServices();
    assert.match(s.nodes.servicesGrid.innerHTML,/&lt;bad range&gt;/);assert.match(s.nodes.servicesGrid.innerHTML,/Thử lại/);assert.equal(s.nodes.searchInput.value,'keep');
});
test('clear resets all controls and removes query values',async()=>{
    const s=setup();s.nodes.searchInput.value='spa';s.nodes.min_price.value='100';s.nodes.sortSelect.value='price-desc';await s.context.clearServiceFilters();
    assert.equal(s.location.search,'');assert.equal(s.nodes.min_price.value,'');assert.equal(s.nodes.sortSelect.value,'default');
});
test('home loader cannot overwrite the services catalog',async()=>{
    const main=fs.readFileSync('app/static/js/customers/main.js','utf8');const start=main.indexOf('async function loadServices() {'),end=main.indexOf('\nfunction displayServices',start);const calls=[];
    const context={window:{location:{pathname:'/services'}},fetch:()=>calls.push('fetch')};vm.runInNewContext(main.slice(start,end),context);await context.loadServices();assert.equal(calls.length,0);
});
