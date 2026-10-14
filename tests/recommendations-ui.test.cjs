const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/customers/recommendations.js', 'utf8');

function setup({token = 'customer-token', data, ok = true, throws = false, detail = true} = {}) {
    const nodes = new Map(), handlers = {}, calls = [];
    const node = () => ({hidden: true, innerHTML: '', textContent: '', querySelector: select});
    const select = key => { if (!nodes.has(key)) nodes.set(key, node()); return nodes.get(key); };
    const root = node();
    const context = {Date, Intl, Map, Number, JSON, String, document: {
        getElementById: id => id === 'relatedRecommendations' && detail ? root : null,
        addEventListener: (name, callback) => handlers[name] = callback
    }, window: {location: {pathname: detail ? '/services/1' : '/services'}, CustomerAuth: {
        getAccessToken: () => token, restoreAccessToken: async () => token,
        fetch: async (url, options) => { calls.push({url, options}); if (throws) throw Error('offline'); return {ok, json:async()=>data}; }
    }, PackageCare: {packageHtml: (p, badge) => `<article>${badge}${p.magoi}`}}};
    vm.runInNewContext(source, context);
    return {context, root, select, calls, handlers};
}

test('anonymous browsing never posts events', async () => {
    const s = setup({token:null});
    await s.context.window.CustomerRecommendations.track('view_service', {madv:1});
    assert.equal(s.calls.length, 0);
});

test('tracking deduplicates views and retains request on navigation', async () => {
    const s = setup();
    for(let i=0;i<10;i++) await s.context.window.CustomerRecommendations.track('view_service', {madv:1});
    assert.equal(s.calls.length, 1);
    assert.equal(s.calls[0].options.keepalive, true);
    assert.deepEqual(JSON.parse(s.calls[0].options.body), {action:'view_service', madv:1});
});

test('API errors hide recommendations and resolve without breaking page', async () => {
    for(const options of [{ok:false}, {throws:true}]) {
        const s = setup(options); s.root.hidden=false;
        await s.context.window.CustomerRecommendations.refresh();
        assert.equal(s.root.hidden, true);
    }
});

test('detail uses one mixed grid with badges, escapes HTML and excludes current service', async () => {
    const s = setup({data:{success:true, items:[
        {type:'package',magoi:8,reason:'<script>package</script>'},
        {type:'service',madv:1,tendv:'Current service'},
        {type:'service',madv:5,tendv:'<img onerror=alert(1)>',reason:'<script>x</script>',gia:100000}
    ]}});
    await s.context.window.CustomerRecommendations.refresh();
    assert.equal(s.root.hidden, false);
    const html = s.select('[data-related-items]').innerHTML;
    assert.match(html, /&lt;img/);
    assert.ok(!html.includes('<script>') && !html.includes('Current service'));
    assert.match(html, />Dịch vụ</);
    assert.match(html, />Gói</);
    assert.ok(html.indexOf('/packages/8') < html.indexOf('/services/5'));
    assert.equal(s.calls[0].url, '/api/recommendations/related/1');
});

test('catalog never loads a separate recommendation section', async () => {
    const s = setup({detail:false});
    await s.context.window.CustomerRecommendations.refresh();
    assert.equal(s.calls.length, 0);
});

test('empty detail recommendations hide the section', async () => {
    const s = setup({data:{success:true, items:[]}});
    await s.context.window.CustomerRecommendations.refresh();
    assert.equal(s.root.hidden, true);
});
