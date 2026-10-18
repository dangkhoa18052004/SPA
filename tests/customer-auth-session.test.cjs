const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup(response) {
    const calls = [], values = new Map([['access_token', 'test-token']]);
    const context = {
        window: {fetch: async (path, options) => {
            calls.push({path, options});
            return path === '/api/auth/restore-session'
                ? new Response(JSON.stringify({success:true,access_token:'restored'})) : response.clone();
        }}, Headers, URL, console,
        localStorage: {getItem:k=>values.get(k), setItem:(k,v)=>values.set(k,v), removeItem:k=>values.delete(k)}
    };
    vm.runInNewContext(fs.readFileSync('app/static/js/customers/auth-session.js', 'utf8'), context);
    return {auth:context.window.CustomerAuth,calls,values};
}
test('validation 422 never restores the session or replays a POST', async () => {
    const s = setup(new Response(JSON.stringify({success:false,message:'Invalid data'}), {status:422}));
    const response = await s.auth.fetch('/api/test', {method:'POST'});
    assert.equal(response.status,422);
    assert.equal(s.calls.length,1);
    assert.equal(s.values.get('access_token'),'test-token');
});
test('malformed JWT restores and retries only once, including a failed retry', async () => {
    const s = setup(new Response(JSON.stringify({msg:'Not enough segments'}), {status:422}));
    await s.auth.fetch('/api/test');
    assert.deepEqual(s.calls.map(c=>c.path), ['/api/test','/api/auth/restore-session','/api/test']);
});
test('401 restores at most once; arbitrary msg 422 does not trigger authentication', async () => {
    const s = setup(new Response(JSON.stringify({msg:'Expired'}), {status:401}));
    await s.auth.fetch('/api/test');
    assert.equal(s.calls.length,3);
    assert.equal(await s.auth.isAuthFailure(new Response(JSON.stringify({msg:'Invalid appointment'}), {status:422})),false);
});
test('wrong current password stays a form error and does not replay the mutation', async () => {
    const s = setup(new Response(JSON.stringify({success:false,message:'Wrong current password'}), {status:401}));
    await s.auth.fetch('/api/profile/change-password', {method:'PUT'});
    assert.equal(s.calls.length,1);
    assert.equal(s.values.get('access_token'),'test-token');
});
