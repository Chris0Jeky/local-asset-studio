import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {slots, routes, assets} from './fixtures.mjs';
import {freshDraft, readDraft, assign, candidates, prepare, returnResult, requestFor, summary, routeState} from './model.mjs';
let checks = 0;
function test(name, run) { run(); checks++; console.log(`PASS ${name}`); }
test('six slots cover every requested media kind', () => {
  assert.equal(slots.length, 6); assert.deepEqual(new Set(slots.map(s => s.kind)), new Set(['image','video','audio','3d']));
  assert.equal(summary(freshDraft()).missing.length, 4);
});
test('replacement preserves the previous record and never changes review', () => {
  const draft = freshDraft(); assign(draft, 'background', 'marsh-moon');
  assert.equal(draft.slots.background.previousAssetId, 'marsh-dusk');
  assign(draft, 'background', draft.slots.background.previousAssetId);
  assert.equal(draft.slots.background.assetId, 'marsh-dusk');
  assert.ok(assets.every(a => a.review === 'unreviewed'));
});
test('wrong-kind and unknown selections are refused without losing current choice', () => {
  const draft = freshDraft();
  for (const id of ['marsh-bed','missing']) assert.throws(() => assign(draft,'background',id));
  assert.equal(draft.slots.background.assetId, 'marsh-dusk');
});
test('edits and assignments round-trip through serialized storage', () => {
  const draft = freshDraft(); draft.title = 'Changed scene'; draft.slots.icon.intent = 'A silver key'; assign(draft,'model','lantern-mesh');
  assert.deepEqual(readDraft(JSON.stringify(draft)), draft);
});
test('malformed and incompatible drafts refuse instead of reinterpreting IDs', () => {
  for (const raw of ['{','null','{}',JSON.stringify({...freshDraft(),version:2})]) assert.throws(() => readDraft(raw));
  const draft = freshDraft(); draft.slots.background.assetId = 'marsh-bed'; assert.throws(() => readDraft(JSON.stringify(draft)));
});
test('unsupported and blocked routes cannot prepare or fabricate a return', () => {
  const draft = freshDraft();
  for (const [slot,id] of [['sprite','sprite'],['sound','voice'],['model','trellis'],['model','hunyuan'],['loop','h3'],['background','scene']]) {
    assert.notEqual(routeState(draft,slot,id).state,'preview');
    assert.throws(() => prepare(draft,slot,id)); assert.throws(() => returnResult(draft,slot,id));
  }
});
test('the look handoff uses the existing id, scene and revision fields', () => {
  const draft = freshDraft(), request = requestFor(draft,'background','image');
  assert.deepEqual(Object.keys(request).sort(), ['expected_revision','id','scene']);
  assert.equal(request.id, routes.image.lookId); assert.ok(request.scene.includes(draft.slots.background.intent));
});
test('return requires deliberate preparation and retains review gaps', () => {
  const draft = freshDraft(); assert.throws(() => returnResult(draft,'icon','icon'));
  prepare(draft,'icon','icon'); returnResult(draft,'icon','icon');
  assert.equal(draft.slots.icon.assetId,'synthetic-icon'); assert.equal(summary(draft).missing.length,3);
  assert.throws(() => returnResult(draft,'icon','icon'));
});
test('changed wording, requirements or selected sources invalidate prepared returns', () => {
  for (const change of [d => { d.brief += '!'; }, d => { d.slots.icon.intent += '!'; }, d => { d.slots.icon.criteria += '!'; }]) {
    const draft = freshDraft(); prepare(draft,'icon','icon'); change(draft); assert.throws(() => returnResult(draft,'icon','icon'));
  }
  const draft = freshDraft(); prepare(draft,'loop','scene'); assign(draft,'background','marsh-moon'); assert.throws(() => returnResult(draft,'loop','scene'));
});
test('scene handoff reuses chosen sources and does not claim animation', () => {
  const draft = freshDraft(), request = requestFor(draft,'loop','scene');
  assert.deepEqual(request.asset_ids,['marsh-dusk','marsh-bed']); assert.equal(request.frames_per_shot,96);
  draft.slots.background.assetId = null; assert.equal(routeState(draft,'loop','scene').state,'blocked');
});
test('blank brief blocks preparation; Library remains usable', () => {
  const draft = freshDraft(); draft.brief = ''; assert.throws(() => prepare(draft,'icon','icon'));
  assign(draft,'icon','brass-key'); assert.equal(draft.slots.icon.assetId,'brass-key');
});
test('reload retains the returned asset but drops transient preparation authority', () => {
  const draft = freshDraft(); prepare(draft,'background','image');
  assert.equal(readDraft(JSON.stringify(draft)).slots.background.prepared,null);
  returnResult(draft,'background','image'); assert.equal(readDraft(JSON.stringify(draft)).slots.background.assetId,'synthetic-background');
});
test('empty searches never broaden media scope', () => {
  assert.equal(candidates('sound','no such asset').length,0); assert.equal(candidates('sound').length,2);
  assert.ok(candidates('model').every(a => a.media_type === '3d'));
});
test('preview has no transport or runtime execution code; CSP denies connections', () => {
  for (const path of ['app.mjs','model.mjs','fixtures.mjs']) assert.doesNotMatch(readFileSync(new URL(path, import.meta.url),'utf8'), /\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource/);
  assert.match(readFileSync(new URL('index.html',import.meta.url),'utf8'), /connect-src 'none'/);
});
console.log(`${checks} focused checks passed; no network or generation.`);
