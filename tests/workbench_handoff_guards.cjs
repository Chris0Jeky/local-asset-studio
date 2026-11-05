const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');
const references = fs.readFileSync(path.join(__dirname, '../app/static/references.js'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const workshop = fs.readFileSync(path.join(__dirname, '../app/static/workshop.js'), 'utf8');
const privacyOptionsSource = app.match(/^function privacyOptions\([^\n]+/m)?.[0];
assert.ok(privacyOptionsSource, 'attachment handlers use the actual app privacy helper');
const attachmentSource = references.slice(references.indexOf('const referenceAttachments='), references.indexOf('// The readiness model itself lives'));

function between(start, end) {
  const first = source.indexOf(start);
  assert.notEqual(first, -1, `missing source marker: ${start}`);
  const last = source.indexOf(end, first);
  assert.notEqual(last, -1, `missing source marker: ${end}`);
  return source.slice(first, last);
}

const openHandoffSource = between('  function openHandoff(', "\n  q('#uxDestination').onchange=destinationDetails;");
const useSecondPictureSource = between('  const useSecondPicture=', "\n  q('#uxSecondRestyle').onclick=");
const pullIntoSlotSource = between('  async function pullIntoSlot(', "\n  q('#uxSourceAssets').onclick=");

function secondPictureHarness(sourceExists, localFile = false) {
  const context = {};
  const asset = sourceExists
    ? "[{id:'source',title:'Source',review:'unreviewed',sha256:'a'.repeat(64),media_type:'image',trashed_at:null}]"
    : '[]';
  vm.runInNewContext([
    "const file={name:'look.png',size:20,lastModified:1};let pickerBusy=false;let secondPicture=" + (localFile ? "{file}" : "{asset:{id:'style',title:'Style'}}") + ",pendingStyle=null;",
    "const continuationState={source_asset_id:'source'};",
    "const boardDestination=()=>({id:'restyle-recipe'});",
    "const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',innerHTML:'',textContent:''});return nodes.get(selector);};",
    "const dismissSecondPicture=()=>{secondPicture=null};const syncReady=()=>{};",
    "let handoffEpoch=0,sourceContext=null,handoffBaseline=null,handoffIntent='edit',handoffId=null;",
    "let dirty=false;const assetDetailsDirty=()=>dirty;const warnUnsavedAsset=()=>{};",
    "let catalog={presets:[]};const notices=[];const announce=(message,error=false)=>notices.push({message,error});",
    `const assetState={assets:${asset}};`,
    "const workbenchStamp=()=> 'stamp';const assetPreview=()=>'<img>';const escape=value=>String(value);",
    "const handoffRecipes=()=>{};const destinationDetails=()=>{};",
    "const handoff={open:false,modal:false,showModal(){if(this.open&&!this.modal)throw Error('Modeless dialog conflict');this.open=this.modal=true;}};",
    "const readSource=()=>new Promise(()=>{});",
    openHandoffSource,
    useSecondPictureSource,
    "this.run=useSecondPicture('restyle');this.pending=()=>pendingStyle;this.dialog=handoff;this.notices=notices;",
    "this.openDirect=(epoch)=>openHandoff('source','restyle-recipe',epoch,'restyle');",
    "this.makeDirty=()=>{dirty=true};this.clearCatalog=()=>{catalog=null};",
    "this.trashSource=()=>{assetState.assets[0].trashed_at=123};",
    "this.choice=()=>secondPicture;this.reference=q('#reference');this.reference.value='selected-look.png';",
  ].join('\n'), context);
  return context;
}

test('a rejected second-picture handoff clears the pending style', () => {
  const harness = secondPictureHarness(false);
  harness.run();
  assert.equal(harness.pending(), null);
  assert.equal(harness.dialog.open, false);
  assert.match(harness.notices.at(-1).message, /available image/);
});

test('a rejected local-file handoff retains the actual choice and input', () => {
  const harness = secondPictureHarness(false, true);
  const choice = harness.choice();
  harness.run();
  assert.equal(harness.choice(), choice);
  assert.equal(harness.reference.value, 'selected-look.png');
  assert.equal(harness.pending(), null);
  assert.equal(harness.openDirect(), false);
});

test('an opened handoff retains the local file until preparation commits', () => {
  const harness = secondPictureHarness(true, true);
  const choice = harness.choice();
  harness.run();
  assert.equal(harness.choice(), choice);
  assert.equal(harness.reference.value, 'selected-look.png');
  assert.equal(harness.pending(), choice);
});

test('a valid handoff reports that it opened and retains the reviewed style', () => {
  const harness = secondPictureHarness(true);
  harness.run();
  assert.equal(harness.dialog.open, true);
  assert.equal(harness.pending().asset.id, 'style');
  assert.equal(harness.openDirect(), true);
});

function pullHarness() {
  const context = {};
  vm.runInNewContext([
    "const notices=[];let stamp='before',finish,fail,uploaded='old-upload',draftDirty=false;",
    "const referenceRecords=[{parent_asset:'old-parent',file:'old.png',missing:false}];",
    "const selected={reference_slots:[{}],continuation_capability:{}};const StudioContinuation={sourceInput:()=> 'last_reference'};",
    "let referenceEpoch=0,referencePending=0,selectionEpoch=0;const updateReady=()=>{};const $=()=>({textContent:''});",
    "const post=()=>new Promise((resolve,reject)=>{finish=resolve;fail=reject;});",
    "const workbenchStamp=()=>stamp;let renderCount=0,replaceCount=0,saveCount=0,syncCount=0;",
    "const renderReferenceSlots=()=>{renderCount++};const replaceParentAsset=()=>{replaceCount++};",
    "const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});",
    attachmentSource,
    pullIntoSlotSource,
    "this.start=(index=0)=>pullIntoSlot(index,'style-asset');this.setStamp=value=>{stamp=value;referenceEpoch++;referencePending=0;};",
    "this.editWording=()=>{stamp='typed wording'};",
    "this.finish=value=>finish(value);this.fail=error=>fail(error);",
    "this.snapshot=()=>JSON.stringify(referenceRecords[0]);",
    "this.counts=()=>[renderCount,replaceCount,saveCount,syncCount];this.notices=notices;",
  ].join('\n'), context);
  return context;
}

test('a delayed copy cannot overwrite a newer reference epoch', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.setStamp('after');
  harness.finish({parent_asset:'style-asset',file:'style.png'});
  assert.equal(await pending, false);
  assert.deepEqual(JSON.parse(harness.snapshot()), {parent_asset:'old-parent',file:'old.png',missing:false});
  assert.deepEqual(Array.from(harness.counts()), [0,0,0,0]);
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /slot changed/);
});

test('a failed copy is reported without an unhandled rejection', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.fail(new Error('offline'));
  assert.equal(await pending, false);
  assert.deepEqual(Array.from(harness.counts()), [1,0,0,0]);
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /offline/);
});

test('a current copy commits once', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.finish({parent_asset:'style-asset',file:'style.png'});
  assert.equal(await pending, true);
  assert.deepEqual(JSON.parse(harness.snapshot()), {parent_asset:'style-asset',file:'style.png',missing:false});
  assert.deepEqual(Array.from(harness.counts()), [1,1,1,1]);
  assert.equal(harness.notices.length, 0);
});

const replaceSecondPictureSource = between("  q('#uxSecondReplace').onclick=async()=>{", '\n  // A modal handoff carries IDs');

function replaceHarness() {
  const context = {StudioContinuation:require('../app/static/continuation-core.js')};
  vm.runInNewContext([
    privacyOptionsSource,
    "let pickerBusy=false,pickerBusyOwner=null,handoffBusy=false,submitting=false,restoring=false,referencePending=0;let secondPicture={asset:{id:'replacement',sha256:'b'.repeat(64),title:'Replacement'}},continuationState={version:1,intent:'edit',preset_id:'recipe',reference_file:'a'.repeat(32)+'_old.png',source_asset_id:'source',source_sha256:'a'.repeat(64),template_sha256:'c'.repeat(64)};",
    "const selected={id:'recipe'};let selectionEpoch=0,referenceEpoch=0,stamp='before',finish,fail,uploaded='old-upload',draftDirty=false;",
    "const notices=[];const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',files:[]});return nodes.get(selector);};",
    "const window={confirm:()=>true};const dismissSecondPicture=()=>{secondPicture=null};",
    "const selectPreset=()=>{stamp='reset';selectionEpoch++;continuationState=null};const workbenchStamp=()=>stamp;",
    "const post=()=>new Promise((resolve,reject)=>{finish=resolve;fail=reject});",
    "let replaceCount=0,saveCount=0,syncCount=0;const attachContinuationSource=result=>{uploaded=result.file;replaceCount++};",
    "const replaceParentAsset=()=>{replaceCount++};const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});const secondName=item=>item.asset.title;const syncReady=()=>{};",
    "const legacyReferenceChange=null;const DataTransfer=function(){};const Event=function(){};",
    replaceSecondPictureSource,
    "this.start=()=>q('#uxSecondReplace').onclick();this.setStamp=value=>{stamp=value};this.editWording=()=>{stamp='typed wording'};this.finish=value=>finish(value);this.fail=error=>fail(error);this.draft=()=>JSON.stringify({stamp,continuationState,secondPicture});",
    "this.setPending=value=>{referencePending=value};this.pendingCount=()=>referencePending;",
    "this.state=()=>JSON.stringify({uploaded,draftDirty,replaceCount,saveCount,syncCount});this.notices=notices;",
  ].join('\n'), context);
  return context;
}

const pickerAttachSource = between("  q('#uxSourceAssets').onclick=async e=>{", "\n  picker.addEventListener('cancel'");
const attachStampSource = between('  function attachStamp(){', '\n  function syncContinuation(){');

const replacement=()=>({file:'b'.repeat(32)+'_replacement.png',sha256:'b'.repeat(64),parent_asset:'replacement',context:{asset_id:'replacement',sha256:'b'.repeat(64)}});

test('replacement staging and failures retain the original draft and decision',async()=>{
  const h=replaceHarness(),before=h.draft(),pending=h.start();
  assert.equal(h.draft(),before,'do not reset the live draft before a copy is ready');
  h.fail(Error('copy failed'));await pending;
  assert.equal(h.draft(),before);
  assert.match(h.notices.at(-1).message,/copy failed/);
});
for(const [name,change] of [
  ['file path',r=>r.file='../outside.png'],
  ['parent identity',r=>r.parent_asset='other'],
  ['file digest',r=>r.sha256='d'.repeat(64)],
  ['context identity',r=>r.context.asset_id='other'],
  ['context digest',r=>r.context.sha256='d'.repeat(64)],
  ['missing context',r=>delete r.context],
])test(`invalid replacement ${name} preserves the live draft`,async()=>{
  const h=replaceHarness(),before=h.draft(),pending=h.start(),result=replacement();change(result);h.finish(result);await pending;
  assert.equal(h.draft(),before);assert.match(h.notices.at(-1).message,/could not be verified/);
});

test('a delayed replacement copy cannot overwrite a newer workbench state', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.setStamp('changed');
  harness.finish(replacement());
  await pending;
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'old-upload',draftDirty:false,replaceCount:0,saveCount:0,syncCount:0,
  });
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /workbench changed/);
});

test('wording typed during replacement cancels the stale confirmation', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.editWording();
  const before = harness.draft();
  harness.finish(replacement());
  await pending;
  assert.equal(harness.draft(), before, 'a stale confirmation must not wipe wording typed while its copy runs');
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'old-upload',draftDirty:false,replaceCount:0,saveCount:0,syncCount:0,
  });
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /workbench changed/);
});

test('a newer pending role upload prevents source replacement without losing its owner', async () => {
  const harness=replaceHarness(),before=harness.draft(),pending=harness.start();
  harness.setPending(1);
  harness.finish(replacement());
  await pending;
  assert.equal(harness.draft(),before,'a newly pending attachment is newer work even before its record changes');
  assert.equal(harness.pendingCount(),1,'refusing replacement must not cancel the new attachment');
  assert.deepEqual(JSON.parse(harness.state()),{
    uploaded:'old-upload',draftDirty:false,replaceCount:0,saveCount:0,syncCount:0,
  });
  assert.match(harness.notices.at(-1).message,/workbench changed/);
});

test('a current replacement copy commits once', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.finish(replacement());
  await pending;
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'b'.repeat(32)+'_replacement.png',draftDirty:true,replaceCount:1,saveCount:1,syncCount:1,
  });
  assert.equal(harness.notices.length, 1);
  assert.equal(harness.notices[0].error, false);
  assert.match(harness.notices[0].message, /now the reference/);
});


test('unrelated wording does not cancel a deferred board copy', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.editWording();
  harness.finish({parent_asset:'style-asset',file:'style.png'});
  assert.equal(await pending, true);
  assert.deepEqual(Array.from(harness.counts()), [1,1,1,1]);
});

test('a missing slot is refused before the helper stages an asset', async () => {
  const harness = pullHarness();
  assert.equal(await harness.start(9), false);
  assert.deepEqual(Array.from(harness.counts()), [0,0,0,0]);
  assert.match(harness.notices.at(-1).message, /destination slot/);
});


for (const [name, setup, epoch] of [
  ['stale request epoch', () => {}, -1],
  ['unsaved asset details', h => h.makeDirty(), undefined],
  ['catalogue still loading', h => h.clearCatalog(), undefined],
  ['trashed continuation source', h => h.trashSource(), undefined],
]) test(`opening explicitly returns false for ${name}`, () => {
  const harness = secondPictureHarness(true, true);
  setup(harness);
  assert.equal(harness.openDirect(epoch), false);
  assert.equal(harness.dialog.open, false);
  assert.equal(harness.reference.value, 'selected-look.png');
});

test('a modeless dialog conflict is reported without consuming the picture', () => {
  const harness = secondPictureHarness(true, true);
  const choice = harness.choice();
  harness.dialog.open = true;
  harness.run();
  assert.equal(harness.choice(), choice);
  assert.equal(harness.pending(), null);
  assert.equal(harness.reference.value, 'selected-look.png');
  assert.match(harness.notices.at(-1).message, /Modeless dialog conflict/);
});
test('the library picker guards named-input attachment with the attachment stamp', () => {
  assert.match(pickerAttachSource, /attachStamp\(\)/, 'The picker compares attachment-relevant state, not whole-workbench wording');
  assert.doesNotMatch(pickerAttachSource, /workbenchStamp\(\)/, 'Typing a prompt while the picker copy is in flight must not refuse it');
});

test('the attachment stamp excludes wording, lineage and batch state', () => {
  assert.doesNotMatch(attachStampSource, /values\(\)|parentAssets|continuationState|#positive|#negative|#batch/, 'Controls, lineage claims and batch stay out of the attachment comparison');
  assert.match(attachStampSource, /referenceRecords/, 'Slot files, roles and availability stay in');
  assert.match(attachStampSource, /uploaded/, 'Staged named-input files stay in');
});

// A result tile's picture can sit outside the first Library page: it is resolved by ID before its review is saved (#1622).
const resultReviewSource = between('  resultPanel.onclick=async e=>{', '\n  // Number keys 1-5');
function resultReviewHarness({known, state}) {
  const context = {};
  vm.runInNewContext([
    "let pairActionBusy=false;const setupStamp=()=>'s',syncReady=()=>{},announce=(m,e)=>notices.push({m,e}),notices=[],resolveCalls=[],saved=[];",
    "const store=new Map(" + JSON.stringify(known) + ");const assetRecord=id=>store.get(id);",
    "const refreshAssets=async()=>true;",
    "const resolveAssetIDs=async ids=>{resolveCalls.push(ids);for(const id of ids)store.set(id," + JSON.stringify(state) + ");return true;};",
    "const StudioReviewChecks={cycle:(tags,c)=>[...tags,c],answer:()=>true};",
    "const mutateAssets=async payload=>{saved.push(payload);};",
    "const resultPanel={querySelectorAll:()=>[]};const q=()=>null;const document={activeElement:null};",
    resultReviewSource,
    "this.press=dataset=>resultPanel.onclick({target:{closest:()=>({dataset,disabled:false})}});",
    "this.state=()=>JSON.stringify({resolveCalls,saved,notices});",
  ].join('\n'), context);
  return context;
}

for (const [label, dataset, payload] of [
  ['check', {uxCheck: 'face', asset: 'far'}, {action: 'edit', ids: ['far'], tags: ['face']}],
  ['review', {uxReview: 'selected', asset: 'far'}, {action: 'edit', ids: ['far'], review: 'selected'}],
]) {
  test(`a result tile ${label} resolves an asset outside the first Library page before saving`, async () => {
    const harness = resultReviewHarness({known: [], state: {id: 'far', tags: []}});
    await harness.press(dataset);
    const state = JSON.parse(harness.state());
    assert.deepEqual(state.resolveCalls, [['far']]);
    assert.deepEqual(state.saved, [payload]);
    assert.deepEqual(state.notices, []);
  });
}

test('a result tile review of an already known asset makes no extra read', async () => {
  const harness = resultReviewHarness({known: [['near', {id: 'near', tags: []}]], state: null});
  await harness.press({uxReview: 'selected', asset: 'near'});
  assert.deepEqual(JSON.parse(harness.state()).resolveCalls, []);
});

// #2008: Saved setups is inside .editor for presentation, but its form does not edit the active recipe.
const editorInputSource = between("  q('#createView .editor')?.addEventListener('input'", "\n  after('renderSelected'");
const draftEventsSource = between("  for(const event of ['input','change'])q('#createView')", "\n  q('#createView').addEventListener('click'");
function editorEventHarness() {
  const listeners = {editor: {}, create: {}}, cleared = [], scheduled = [];
  let nextTimer = 100;
  const context = {
    q: selector => ({addEventListener(type, handler) { listeners[selector.endsWith('.editor') ? 'editor' : 'create'][type] = handler; }}),
    clearTimeout: timer => cleared.push(timer),
    setTimeout: (handler, delay) => { scheduled.push({handler, delay}); return ++nextTimer; },
  };
  vm.runInNewContext([
    'let pictureKept={id:"previous-picture"},draftDirty=false,draftTimer=99,undoRenders=0,readinessSyncs=0,saves=0;',
    'const renderUndo=()=>undoRenders++,syncReady=()=>readinessSyncs++,saveDraft=()=>saves++;',
    editorInputSource, draftEventsSource,
    'this.state=()=>({pictureKept:!!pictureKept,draftDirty,draftTimer,undoRenders,readinessSyncs,saves});',
  ].join('\n'), context);
  return {
    state: () => JSON.parse(JSON.stringify(context.state())), cleared, scheduled,
    fire(type, saved, id = 'saveName') {
      const event = {isTrusted: true, target: {id, closest: selector => selector === '.editor' || (saved && selector === '#workshopSaved')}};
      listeners.editor[type]?.(event); // capture on .editor, then bubble through #createView
      listeners.create[type]?.(event);
    },
  };
}

for (const id of ['saveName', 'importRecipe']) {
  test(`#2008: ${id} input and change preserve the picture undo and leave the draft untouched`, () => {
    const harness = editorEventHarness(), before = harness.state();
    harness.fire('input', true, id); harness.fire('change', true, id);
    assert.deepEqual(harness.state(), before);
    assert.deepEqual(harness.cleared, [], 'saved setup metadata must not cancel an existing real edit debounce');
    assert.deepEqual(harness.scheduled, [], 'saved setup metadata must not schedule autosave');
  });
}

test('#2008: an actual editor edit still invalidates picture undo and schedules its draft', () => {
  const harness = editorEventHarness();
  harness.fire('input', false, 'seed');
  assert.deepEqual(harness.state(), {pictureKept: false, draftDirty: true, draftTimer: 101, undoRenders: 1, readinessSyncs: 1, saves: 0});
  assert.deepEqual(harness.cleared, [99]);
  assert.equal(harness.scheduled[0].delay, 350);
  harness.fire('input', true);
  assert.equal(harness.state().draftTimer, 101, 'naming a saved setup must not postpone the real edit');
  assert.equal(harness.scheduled.length, 1);
  harness.scheduled[0].handler();
  assert.equal(harness.state().saves, 1);
  harness.fire('change', false, 'seed');
  assert.equal(harness.state().readinessSyncs, 2, 'change-only controls retain their draft owner');
});

const hasEditsStart = workshop.indexOf('    function hasEdits()');
assert.notEqual(hasEditsStart, -1);
const hasEditsSource = workshop.slice(hasEditsStart, workshop.indexOf('    const pickerChoices', hasEditsStart));
function discardHarness(inputs) {
  const prompt = {value: 'Example wording'}, negative = {value: ''};
  const context = {
    bridge: {recipe: () => ({defaults: {positive: 'Example wording', seed: 42}}), hasSources: () => false},
    q: selector => selector === '#positive' ? prompt : negative,
    editor: {querySelectorAll: () => inputs}, actions: {querySelectorAll: () => []},
  };
  vm.runInNewContext(hasEditsSource + '\nthis.hasEdits=hasEdits;', context);
  return context.hasEdits;
}
function editorField({saved = false, ...values}) {
  return {type: 'text', tagName: 'INPUT', value: '', defaultValue: '', dataset: {}, closest: selector => saved && selector === '#workshopSaved', ...values};
}

test('#2008: saved name and import file do not trigger a discard confirmation', () => {
  const name = editorField({saved: true, id: 'saveName', value: 'Next setup'});
  const file = editorField({saved: true, id: 'importRecipe', type: 'file', files: [{name: 'candidate.json'}]});
  assert.equal(discardHarness([name, file])(), false);
});

test('#2008: active recipe settings and picture files still trigger discard confirmation', () => {
  assert.equal(discardHarness([editorField({dataset: {key: 'seed'}, value: '42'})])(), false);
  assert.equal(discardHarness([editorField({dataset: {key: 'seed'}, value: '43'})])(), true);
  assert.equal(discardHarness([editorField({type: 'file', files: [{name: 'source.png'}]})])(), true);
});

const referenceLinkSource = between("  q('#uxFindReferenceRecipes').onclick=", '\n  const advanced=');
for (const accept of [false, true]) {
  test(`#2008: picture-recipe link ${accept ? 'accepts' : 'cancels'} the existing wording confirmation`, () => {
    const link = {}, reference = {}, calls = [], context = {
      selected: {defaults: {positive: 'Example wording'}},
      q: selector => selector === '#uxFindReferenceRecipes' ? link : selector === '#positive' ? {value: 'My own wording'} : selector === '#reference' ? reference : null,
      confirm: () => { calls.push('confirm'); return accept; },
      chooseIntent: intent => calls.push(intent),
      focusReadinessTarget: node => calls.push(node),
    };
    vm.runInNewContext(referenceLinkSource, context);
    link.onclick();
    assert.deepEqual(calls, accept ? ['confirm', 'edit', reference] : ['confirm']);
  });
}

const reattachSourceCode = between('  async function reattachSource(){', '\n  // One slot, two pictures:');
for (const slots of [[], [{}]]) {
  test(`#2008: picture link focuses the current ${slots.length ? 'board' : 'single-image'} recipe instead of a retained hidden input`, () => {
    const link = {}, board = {id: 'retained-board-slot'}, reference = {id: 'reference'}, focused = [];
    const context = {
      selected: {defaults: {positive: 'Example wording'}},
      q: selector => selector === '#uxFindReferenceRecipes' ? link : selector === '#positive' ? {value: 'Example wording'} : selector === '#reference' ? reference : board,
      confirm: () => { throw Error('An unchanged example needs no confirmation'); },
      chooseIntent: () => { context.selected = {reference: !slots.length, reference_slots: slots}; },
      focusReadinessTarget: node => focused.push(node),
    };
    vm.runInNewContext(referenceLinkSource, context); link.onclick();
    assert.deepEqual(focused, [slots.length ? board : reference]);
  });
}

function sourceRepairHarness() {
  const status = {textContent: ''}, runStatus = {textContent: ''}, notices = [], requests = [], attached = [], pending = [];
  const context = {
    q: selector => selector === '#status' ? runStatus : status,
    announce: (text, error) => { runStatus.textContent = text; notices.push({text, error}); },
    continuationState: {source_asset_id: 'source', source_sha256: 'hash', reference_file: 'old.png'},
    pickerBusy: false, pickerBusyOwner: null, handoffBusy: false, submitting: false, restoring: false, selectionEpoch: 1,
    privacyOptions: () => ({}), syncReady() {}, saveDraft() {}, syncCreate() {},
    post: (url, body) => { requests.push({url, body}); return new Promise((resolve, reject) => { pending.push({resolve, reject}); }); },
    StudioContinuation: {normalize: value => value, sourceInput: () => 'reference', sourceLabel: () => 'Source picture'},
    selected: {}, varyUnapplied: null, secondPanel: {hidden: false}, pendingInputs: new Set(['reference']),
    privacyRevision: 1,
    attachContinuationSource: result => attached.push(result.file),
  };
  context.StudioPrivacy = {capture: () => ({revision: context.privacyRevision})};
  vm.runInNewContext(reattachSourceCode + '\nthis.run=reattachSource;', context);
  return {context, status, runStatus, requests, attached, notices,
    finish: (index = pending.length - 1) => pending[index].resolve({file: 'restored.png', sha256: 'hash', parent_asset: 'source', context: {sha256: 'hash'}}),
    fail: (index = pending.length - 1) => pending[index].reject(Error('Source copy is unavailable.'))};
}

test('#2008: source repair reports checking then its verified result in the same dock status', async () => {
  const h = sourceRepairHarness(), run = h.context.run();
  assert.equal(h.status.textContent, 'Putting the source back. No generation is requested.');
  h.finish(); await run;
  assert.equal(h.status.textContent, 'Source picture holds the source again. No generation submitted.');
  assert.equal(h.runStatus.textContent, '', 'a repair result must not be repeated by the run-status live region');
  assert.deepEqual(h.notices, [], 'the dedicated live region owns this feedback without a duplicate announcement');
  assert.deepEqual(h.attached, ['restored.png']);
  assert.deepEqual(h.requests.map(request => request.url), ['/api/assets/reference']);
  assert.equal(h.context.pickerBusy, false);
});

test('#2008: failed and superseded source repairs never leave a false success or checking result', async () => {
  const failed = sourceRepairHarness(), first = failed.context.run();
  failed.fail(); await first;
  assert.equal(failed.status.textContent, 'Source copy is unavailable.');
  assert.equal(failed.runStatus.textContent, '', 'failure remains visible in its repair region without duplication');
  assert.deepEqual(failed.notices, []);
  assert.deepEqual(failed.attached, []);
  const stale = sourceRepairHarness(), second = stale.context.run();
  stale.context.privacyRevision++; stale.context.pickerBusyOwner = null; stale.context.pickerBusy = false;
  stale.finish(); await second;
  assert.equal(stale.status.textContent, 'The task changed while checking the source. Nothing was attached.');
  assert.deepEqual(stale.attached, []);
});

test('#2008: busy and missing-source repairs explain their refusal without a request', async () => {
  const busy = sourceRepairHarness(); busy.context.pickerBusy = true; await busy.context.run();
  assert.match(busy.status.textContent, /local operation is running/);
  assert.deepEqual(busy.requests, []);
  const missing = sourceRepairHarness(); missing.context.continuationState = null; await missing.context.run();
  assert.match(missing.status.textContent, /No continuation source is available/);
  assert.deepEqual(missing.requests, []);
});

for (const rejected of [false, true]) {
  test(`#2008: a superseded source ${rejected ? 'failure' : 'reply'} cannot overwrite a newer repair's progress`, async () => {
    const h = sourceRepairHarness(), first = h.context.run();
    h.context.privacyRevision++; h.context.pickerBusy = false; h.context.pickerBusyOwner = null;
    const second = h.context.run(), newerOwner = h.context.pickerBusyOwner;
    if (rejected) h.fail(0); else h.finish(0);
    await first;
    assert.equal(h.status.textContent, 'Putting the source back. No generation is requested.');
    assert.equal(h.context.pickerBusyOwner, newerOwner, 'the newer attachment operation retains ownership');
    assert.equal(h.context.pickerBusy, true);
    assert.deepEqual(h.attached, [], 'the stale response never attaches its source');
    h.finish(1); await second;
    assert.equal(h.status.textContent, 'Source picture holds the source again. No generation submitted.');
    assert.deepEqual(h.attached, ['restored.png']);
    assert.equal(h.context.pickerBusy, false);
  });
}

const resolveReadinessSource = between('  function resolveReadiness(action){', "\n  q('#uxBlockers').onclick=");
for (const success of [false, true]) {
  test(`#2008: environment switch ${success ? 'success' : 'refusal'} has one dock feedback owner`, () => {
    const status = {textContent: ''}, runStatus = {textContent: ''}, choice = {options: [{}], value: ''};
    let switches = 0, poll;
    const nodes = {'#uxReadinessActionStatus': status, '#status': runStatus, '#backendChoice': choice,
      '#switchBackend': {disabled: false, click: () => switches++}, '#backendStatus': {textContent: 'Another operation is running.'}};
    const context = {
      q: selector => nodes[selector], selected: {backend_id: 'hidream'},
      readinessItems: () => ({items: [{action: 'switch'}]}), envName: () => 'HiDream',
      message: text => { runStatus.textContent = text; },
      setInterval: callback => { poll = callback; return 1; }, clearInterval() {},
      backendSwitching: false, backendActive: 'primary',
    };
    vm.runInNewContext(resolveReadinessSource + '\nthis.run=()=>resolveReadiness("switch");', context);
    context.run();
    assert.equal(switches, 1, 'repair still delegates exactly once to the existing explicit switch control');
    assert.match(status.textContent, /Switching to HiDream/);
    assert.equal(runStatus.textContent, '', 'switch progress is not copied into the adjacent run status');
    if (success) context.backendActive = 'hidream';
    poll();
    assert.match(status.textContent, success ? /HiDream is running/ : /switch did not happen: Another operation is running/);
    assert.equal(runStatus.textContent, '', 'the completed switch result has a single live-region owner');
  });
}
