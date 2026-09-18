'use strict';
// The projection is the single owner of reference readiness. These contracts pin `ready` to the exact
// referencesReady() formula that app.js gates Generate on, and pin what presentation is allowed to read.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const M = require('../app/static/reference-model.js');

const slotted = (count, extra = {}) => ({id:'r', reference_slots:Array.from({length:count}, (_, i) => ({id:'slot-'+(i+1), role:'Role '+(i+1)})), ...extra});
const attached = (count, extra = []) => Array.from({length:count}, (_, i) => ({file:'f'+i+'.png', role:'Role '+(i+1)})).concat(extra);

// The pre-#610 definition, kept verbatim as the oracle for `ready`.
function legacyReady(recipe, records, pending) {
  if (!recipe?.reference_slots?.length) return true;
  if (pending || records.length !== recipe.reference_slots.length) return false;
  const filled = records.filter(r => r.file && !r.missing).length;
  return recipe.reference_board ? filled >= (recipe.reference_board.min ?? 1) && !records.some(r => r.missing)
    : filled === records.length;
}

test('ready is bit-identical to the referencesReady() formula it replaced', () => {
  const recipes = [null, {id:'r'}, {id:'r', reference:true}, {id:'r', last_reference:true}, slotted(0),
    slotted(1), slotted(3), slotted(3, {reference_board:{}}), slotted(3, {reference_board:{min:2}}),
    slotted(3, {reference_board:{min:2}, last_reference:true})];
  const recordSets = [[], attached(1), attached(2), attached(3), attached(3).map((r, i) => i ? r : {...r, missing:true}),
    [{file:null}, {file:null}, {file:null}], attached(2).concat([{file:null}])];
  for (const recipe of recipes) for (const records of recordSets) for (const pending of [0, 1]) {
    const view = M.project({recipe, records, pending});
    assert.equal(view.ready, legacyReady(recipe, records, pending),
      JSON.stringify({recipe:recipe?.reference_slots?.length ?? null, board:!!recipe?.reference_board, records:records.length, pending}));
    assert.equal(view.blockers.length === 0, view.ready);
  }
});

test('the projection is frozen, pure and never carries a file path or prompt', () => {
  const input = {recipe:slotted(2), records:[{file:'C:/private/source.png', role:'Role 1'}], pending:0, uploaded:'C:/private/keep.png'};
  const before = structuredClone(input);
  const view = M.project(input);
  assert.deepEqual(input, before);
  assert.equal(Object.isFrozen(view), true);
  assert.equal(Object.isFrozen(view.slots[0]), true);
  assert.doesNotMatch(JSON.stringify(view), /private/);
  assert.throws(() => { view.slots.push({}); });
});

test('a board recipe is gated across the board, never slot by slot', () => {
  const view = M.project({recipe:slotted(3, {reference_board:{min:1}}), records:attached(1).concat([{file:null},{file:null}])});
  assert.deepEqual(view.slots.map(s => s.required), [false, false, false]);
  assert.equal(view.mode, 'board');
  assert.deepEqual(view.board, {min:1, filled:1, total:3});
  assert.equal(view.ready, true);
  const strict = M.project({recipe:slotted(2), records:attached(1).concat([{file:null}])});
  assert.deepEqual(strict.slots.map(s => s.required), [true, true]);
  assert.equal(strict.ready, false);
});

test('a slot-less reference is never a readiness prerequisite', () => {
  const view = M.project({recipe:{id:'r', reference:true, reference_label:'Source picture'}});
  assert.deepEqual(view.slots.map(s => [s.id, s.role, s.required]), [['reference', 'Source picture', false]]);
  assert.equal(view.mode, 'inputs');
  assert.equal(view.ready, true);
  assert.deepEqual(view.references, []);
});

// #610 item 1: a board recipe that also keeps image 1 (combine-klein-9b-*, style-pose-*) must be able to say so.
test('last_reference is modelled alongside an authored board and is required where the workbench reports it', () => {
  const recipe = slotted(3, {reference_board:{min:1}, last_reference:true, last_reference_label:'Picture to keep (image 1)'});
  const missing = M.project({recipe, records:attached(1).concat([{file:null},{file:null}])});
  const keep = missing.slots.at(-1);
  assert.equal(keep.id, 'last-reference');
  assert.equal(keep.role, 'Picture to keep (image 1)');
  assert.equal(keep.required, true);
  assert.equal(keep.staged, false);
  assert.equal(missing.references.some(r => r.slotId === 'last-reference'), false);
  const held = M.project({recipe, records:attached(1).concat([{file:null},{file:null}]), lastUploaded:'keep.png'});
  assert.equal(held.slots.at(-1).staged, true);
  assert.deepEqual(held.references.filter(r => r.slotId === 'last-reference'), [{id:'source-last-reference', slotId:'last-reference', role:'Picture to keep (image 1)', stage:'staged'}]);
  // A claimed continuation already carries image 1; it must not be reported as an outstanding prerequisite.
  assert.equal(M.project({recipe, continuation:true}).slots.at(-1).required, false);
  // Neither a board nor a continuation operation: the picture is offered, not demanded.
  assert.equal(M.project({recipe:{id:'r', last_reference:true}}).slots.at(-1).required, false);
  assert.equal(M.project({recipe:{id:'r', last_reference:true, continuation_operation:'combine'}}).slots.at(-1).required, true);
});

test('a chosen but unstaged file is pending, not staged, and counts once in pendingFiles', () => {
  const view = M.project({recipe:{id:'r', reference:true}, picked:{reference:true}});
  assert.deepEqual(view.references, [{id:'source-reference', slotId:'reference', role:'Reference', stage:'selected'}]);
  assert.equal(view.pendingFiles, 1);
  const board = M.project({recipe:slotted(3, {reference_board:{min:1}}), records:[{file:null},{file:null},{file:null}], picked:{slots:[true, false, false]}});
  assert.deepEqual(board.references.map(r => r.stage), ['selected']);
  assert.equal(board.pendingFiles, 1);
  // An upload in flight is pending even before any input reports a file.
  assert.equal(M.project({recipe:slotted(1), records:attached(1), pending:2}).pendingFiles, 2);
});

test('a saved reference that went missing reads as pending, never as staged', () => {
  const view = M.project({recipe:slotted(2), records:[{file:'a.png', missing:true}, {file:'b.png'}]});
  assert.deepEqual(view.slots.map(s => [s.staged, s.pending, s.missing]), [[false, true, true], [true, false, false]]);
  assert.equal(view.ready, false);
  assert.equal(view.hasSources, true);
});

// #610 item 3: the recipe picker's replacement confirm depends on this being the full disjunction again.
test('hasSources still sees a carried source, a claimed asset and a missing record', () => {
  assert.equal(M.project({recipe:slotted(1), records:[{file:null}]}).hasSources, false);
  assert.equal(M.project({recipe:slotted(1, {last_reference:true}), records:[{file:null}], lastUploaded:'keep.png'}).hasSources, true);
  assert.equal(M.project({recipe:slotted(1), records:[{file:'a.png', missing:true}]}).hasSources, true);
  assert.equal(M.project({recipe:slotted(1), records:[{file:null}], claimedAssets:2}).hasSources, true);
  assert.equal(M.project({recipe:{id:'r', reference:true}, uploaded:'a.png'}).hasSources, true);
});

test('malformed and hostile recipe shapes degrade to an empty, ready projection', () => {
  for (const recipe of [null, undefined, 7, 'refine', [], {id:'r', reference_slots:'three'}]) {
    const view = M.project({recipe});
    assert.equal(view.ready, true);
    assert.deepEqual(view.slots, []);
    assert.equal(view.mode, 'none');
  }
  const hostile = M.project({recipe:{id:'r', reference_slots:[{id:'../../etc', role:'  '}, {key:'url(https://evil.test)'}]}});
  assert.deepEqual(hostile.slots.map(s => s.id), ['reference-1', 'reference-2']);
  assert.deepEqual(hostile.slots.map(s => s.role), ['Reference 1', 'Reference 2']);
  assert.equal(M.project('nonsense').ready, true);
  assert.equal(M.project().ready, true);
});

test('live() reads Studio state without a DOM and never mutates one', () => {
  let writes = 0;
  const scope = {document:{querySelector:() => { writes++; return null; }}};
  const view = M.live(scope);
  assert.equal(view.ready, true);
  assert.equal(view.mode, 'none');
  assert.equal(Object.isFrozen(view), true);
  assert.equal(M.live().ready, true);
  assert.ok(writes >= 0);
  const source = require('node:fs').readFileSync(require('node:path').join(__dirname, '../app/static/reference-model.js'), 'utf8');
  for (const forbidden of ['innerHTML', 'textContent =', '.append(', 'fetch(', 'addEventListener'])
    assert.ok(!source.includes(forbidden), forbidden + ' must not appear in a pure projection');
});

// Found by draft PR #627: a duplicate slot id makes presentation-context.js reject the whole capability.
test('an authored slot that already owns the last-reference id is not duplicated', () => {
  const recipe = {id:'r', last_reference:true, last_reference_label:'Picture to keep', reference_board:{min:1},
    reference_slots:[{id:'last-reference', role:'Authored'}, {id:'board-2', role:'Board 2'}]};
  const view = M.project({recipe, records:[{file:'a.png'}, {file:null}]});
  const ids = view.slots.map(slot => slot.id);
  assert.deepEqual(ids, ['last-reference', 'board-2']);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(view.references.filter(r => r.slotId === 'last-reference').length, 1);
});
