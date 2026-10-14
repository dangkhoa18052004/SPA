const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/customers/services.js', 'utf8');

const services = [
    {madv:3,tendv:'Da mụn',mota:'Chăm sóc da',gia:300000,category_slug:'acne'},
    {madv:2,tendv:'Massage B',mota:'',gia:200000,category_slug:'massage'},
    {madv:1,tendv:'Nail trong tên nhưng thuộc massage',mota:'',gia:100000,category_slug:'massage'},
    {madv:4,tendv:'Da mặt',mota:'',gia:150000,category_slug:'facial'}
];

async function setup() {
    const nodes = {searchInput:{value:''},sortSelect:{value:'default'},servicesGrid:{innerHTML:''}};
    const rendered = [], calls = [];
    const context = {
        console: {log(){},error(){}}, Map, Number, Intl,
        document: {getElementById:id=>nodes[id],addEventListener(){},querySelectorAll:()=>[]},
        window: {CustomerAuth:{fetch:async url=>{calls.push(url);return {ok:true,json:async()=>({success:true,services})};}}}
    };
    vm.runInNewContext(source, context);
    context.displayServices = rows => rendered.push(Array.from(rows, r=>r.madv));
    await context.loadAllServices();
    return {context,nodes,rendered,calls,last:()=>rendered.at(-1)};
}

test('default shows the entire catalog in authenticated backend order', async () => {
    const s = await setup();
    assert.deepEqual(s.last(), [3,2,1,4]);
    assert.deepEqual(s.calls, ['/api/services']);
});

test('category filters use persisted categories and rank only matching candidates', async () => {
    const s = await setup();
    s.context.filterByCategory('massage');
    assert.deepEqual(s.last(), [2,1]);
    s.context.filterByCategory('facial');
    assert.deepEqual(s.last(), [3,4]);
});

test('search and category intersect without admitting unrelated recommendations', async () => {
    const s = await setup();
    s.nodes.searchInput.value='da';
    s.context.filterServices();
    assert.deepEqual(s.last(), [3,4]);
    s.context.filterByCategory('massage');
    assert.deepEqual(s.last(), []);
});

test('price ascending persists across category/search changes and default restores personalization', async () => {
    const s = await setup();
    s.nodes.sortSelect.value='price-asc';
    s.context.sortServices();
    assert.deepEqual(s.last(), [1,4,2,3]);
    s.context.filterByCategory('massage');
    assert.deepEqual(s.last(), [1,2]);
    s.context.filterByCategory('all');
    s.nodes.searchInput.value='da';
    s.context.filterServices();
    assert.deepEqual(s.last(), [4,3]);
    s.nodes.sortSelect.value='default';
    s.context.sortServices();
    assert.deepEqual(s.last(), [3,4]);
    s.nodes.searchInput.value='';
    s.context.filterServices();
    assert.deepEqual(s.last(), [3,2,1,4]);
});

test('name sort remains selected when filters change', async () => {
    const s = await setup();
    s.nodes.sortSelect.value='name-desc';
    s.context.sortServices();
    s.context.filterByCategory('massage');
    assert.deepEqual(s.last(), [1,2]);
    s.nodes.searchInput.value='massage';
    s.context.filterServices();
    assert.deepEqual(s.last(), [1,2]);
});

test('home loader cannot overwrite the catalog with its six-card preview', async () => {
    const main = fs.readFileSync('app/static/js/customers/main.js', 'utf8');
    const start = main.indexOf('async function loadServices() {');
    const end = main.indexOf('\nfunction displayServices', start);
    const calls = [];
    const context = {window:{location:{pathname:'/services'}},fetch:()=>calls.push('fetch')};
    vm.runInNewContext(main.slice(start,end),context);
    await context.loadServices();
    assert.equal(calls.length,0);
});
