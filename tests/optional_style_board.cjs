'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../app/static/continuation-core.js');
const R = require('../app/static/reference-model.js');
const catalog = require('../presets/catalog.json');
const p = structuredClone(catalog.presets.find(p => p.id === 'restyle-wai'));
p.reference_board.min = 0;
p.continuation_capability = {version:1, consumes_source:true, operation:'restyle',
  source_input:'last_reference', reference_count:4, board_min:0, prompt_role:'description',
  keeps_picture:true, template_sha256:'b'.repeat(64)};
const source = {version:1, asset_id:'source-asset', sha256:'a'.repeat(64),
  positive:'An adult traveller.', prompt_origin:'submitted-output', prompt_role:'description'};
const file = 'a'.repeat(32) + '_source.png';
const claim = C.initial(source, p, 'restyle', file).claim;
const controls = {positive:'An adult traveller holding a lantern.', last_reference:file};
const records = p.reference_slots.map(() => ({role:'style', file:null}));
const items = (preset=p, refs=records, parents=['source-asset'], inputs=controls) =>
  C.blockerItems(claim, preset, inputs, parents, refs);

test('empty optional board agrees with the shared readiness owner', () => {
  assert.deepEqual(items(), []);
  const state = R.project({recipe:p, records, lastUploaded:{file}, continuation:true});
  assert.equal(state.ready, true);
  assert.equal(state.board.min, 0);
  assert.equal(state.board.filled, 0);
  assert.equal(state.slots.find(s => s.id === 'last-reference').staged, true);
});
test('required board remains blocked by both consumers', () => {
  const required = {...p, reference_board:{...p.reference_board, min:1},
    continuation_capability:{...p.continuation_capability, board_min:1}};
  assert.ok(items(required).some(b => b.code === 'board'));
  assert.equal(R.project({recipe:required, records}).ready, false);
});
test('optional does not ignore an occupied missing board picture or a pending upload', () => {
  const missing = [{file:'missing.png', missing:true}, ...records.slice(1)];
  assert.ok(items(p, missing).some(b => b.code === 'inputs'));
  assert.equal(R.project({recipe:p, records:missing}).ready, false);
  assert.equal(R.project({recipe:p, records, pending:1}).ready, false);
});
test('optional board still needs the independent source file and lineage parent', () => {
  assert.ok(items(p, records, []).some(b => b.code === 'source'));
  assert.ok(items(p, records, ['source-asset'], {...controls, last_reference:null})
    .some(b => b.code === 'source'));
});
test('guidance calls the board optional, not absent or mandatory', () => {
  const text = C.guidance(p, source).join(' ');
  assert.match(text, /style board is optional/i);
  assert.doesNotMatch(text, /there is no style board|add one to three pictures/i);
});
