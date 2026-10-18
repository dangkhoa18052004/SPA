const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('app/static/js/ai_chat.js', 'utf8').replace("document.addEventListener('DOMContentLoaded'", "window.testPost=post;document.addEventListener('DOMContentLoaded'");
function setup(fetch) {
    const state = {calls: [], cleared: 0};
    const context = {window: {}, sessionStorage: {getItem: () => '[]'}, localStorage: {getItem: () => null},
        document: {addEventListener: () => {}}, Intl, AbortController,
        setTimeout: () => 1, clearTimeout: () => state.cleared++,
        fetch: async (...args) => { state.calls.push(args); return fetch(...args); }};
    vm.runInNewContext(code, context);
    return {...state, state, post: context.window.testPost};
}
test('network failure is explained in Vietnamese and confirmation is never automatically resent', async () => {
    const s = setup(() => { throw new TypeError('Failed to fetch'); });
    await assert.rejects(s.post('/api/ai/booking/confirm', {draft_id:'same-draft'}, true), e => e.status === 0 && e.message.includes('Mất kết nối') && !e.message.includes('Failed to fetch'));
    assert.equal(s.state.calls.length, 1);
    assert.equal(s.state.cleared, 1);
});
test('timeout releases the request and offers the ordinary booking page', async () => {
    const s = setup(() => { const e = new Error(); e.name='AbortError'; throw e; });
    await assert.rejects(s.post('/api/ai/chat', {}), /phản hồi quá lâu/);
    assert.equal(s.state.cleared, 1);
});
test('server errors preserve their message and HTTP status', async () => {
    const s = setup(() => ({ok:false,status:504,json:async()=>({success:false,msg:'Trợ lý đang phản hồi chậm'})}));
    await assert.rejects(s.post('/api/ai/chat', {}), e => e.status===504 && e.message==='Trợ lý đang phản hồi chậm');
});
test('HTML or malformed JSON does not become an empty successful reply', async () => {
    const s = setup(() => ({ok:true,status:200,json:async()=>{throw new SyntaxError('Unexpected token <')}}));
    await assert.rejects(s.post('/api/ai/chat', {}), /phản hồi chưa hợp lệ/);
    assert.equal(s.state.cleared, 1);
});
test('enqueue survives navigation with keepalive and polling uses a read-only GET', async () => {
    const s = setup(() => ({ok:true,status:202,json:async()=>({status:'PENDING'})}));
    await s.post('/api/ai/chat/jobs', {request_id:'stable-id',message:'test'});
    assert.equal(s.state.calls[0][1].keepalive, true);
    await s.post('/api/ai/chat/jobs/stable-id', undefined, true, 'GET');
    assert.equal(s.state.calls[1][1].method, 'GET');
    assert.equal(s.state.calls[1][1].body, undefined);
});
