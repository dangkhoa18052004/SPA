const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

const context = {};
vm.runInNewContext(fs.readFileSync('app/static/js/customers/skin-analysis-view.js', 'utf8'), context);
const View = context.SkinAnalysisView;
const ids = (list) => list.map((l) => l.id);
const box = [1, 1, 5, 5];
const lesion = (id, type, probability, extra = {}) =>
    ({id, type, probability, reliable: type != null && probability != null, bbox: box, ...extra});

test('detail sort: valid confidence high to low, missing/invalid last, ties keep original id order', () => {
    const lesions = [lesion(1, null, null), lesion(2, 'papule', 0.6), lesion(3, 'pustule', 0.9),
        lesion(4, 'papule', NaN), lesion(5, 'papule', 0.9), lesion(6, 'papule', 1.4), lesion(7, 'papule', -0.2)];
    assert.deepEqual(ids(View.sortDetail(lesions)), [3, 5, 2, 1, 4, 6, 7]);
    assert.deepEqual(ids(lesions), [1, 2, 3, 4, 5, 6, 7], 'input is not mutated');
});

test('overview ranks up to 8 real points even without reliable highlights, ids and scores unchanged', () => {
    const lesions = [];
    for (let i = 1; i <= 8; i++) lesions.push(lesion(i, i % 2 ? 'papule' : 'pustule', i / 10));
    lesions.push(lesion(9, 'nodule', 0.99));                                  // not highlighted
    lesions.push(lesion(10, 'papule', 0.95, {reliable: false, low_confidence: true}));
    lesions.push(lesion(11, 'papule', 0.97, {bbox: null}));                  // cannot be drawn
    const data = {lesions, highlights: [{type: 'papule'}, {type: 'pustule'}]};
    const view = {showAll: false, selectedId: null};
    assert.deepEqual(ids(View.topPoints(lesions)), [9, 11, 10, 8, 7, 6, 5, 4]);
    assert.deepEqual(ids(View.visiblePoints(data, view)), [9, 10, 8, 7, 6, 5, 4]);
    assert.deepEqual(ids(View.topPoints(lesions)), ids(View.topPoints({...data, highlights: []}.lesions)));
    assert.equal(lesions[9].probability, 0.95);
    assert.equal(lesions[9].reliable, false, 'ranking must not promote a point to reliable');
    assert.equal(View.visiblePoints(data, {...view, showAll: true}).length, 10);
    assert.deepEqual(ids(View.visiblePoints(data, {...view, selectedId: 1})), [9, 10, 8, 7, 6, 5, 4, 1], 'selected point is added');
    assert.deepEqual(ids(View.visiblePoints(data, {...view, selectedId: 11})), [9, 10, 8, 7, 6, 5, 4], 'no box, nothing drawn');
});

test('fewer points than the limit and no highlights', () => {
    const one = {lesions: [lesion(1, 'papule', 0.9)], highlights: [{type: 'papule'}]};
    assert.deepEqual(ids(View.visiblePoints(one, {})), [1]);
    const locationOnly = {lesions: [lesion(1, null, null), lesion(2, null, null)], highlights: []};
    assert.deepEqual(ids(View.visiblePoints(locationOnly, {})), [1, 2], 'positions stay visible');
    assert.equal(View.topPoints(Array.from({length: 10}, (_, i) => lesion(i + 1, null, null))).length, 8);
    assert.deepEqual(View.visiblePoints({lesions: [], highlights: []}, {}).length, 0);
});

test('large result: every point stays reachable through pages', () => {
    const lesions = Array.from({length: 137}, (_, i) => lesion(i + 1, i % 3 ? 'papule' : null, i % 3 ? (i % 50) / 50 : null));
    const sorted = View.sortDetail(lesions);
    const seen = new Set();
    for (let shown = View.PAGE_SIZE; ; shown += View.PAGE_SIZE) {
        sorted.slice(0, shown).forEach((l) => seen.add(l.id));
        if (shown >= sorted.length) break;
    }
    assert.equal(seen.size, 137);
    assert.ok(sorted.slice(-46).every((l) => l.probability === null), 'unknown points are last');
});

test('escapeHtml neutralises markup', () => {
    assert.equal(View.escapeHtml('<img src=x onerror="a">&\''), '&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;');
    assert.equal(View.escapeHtml(null), '');
});
