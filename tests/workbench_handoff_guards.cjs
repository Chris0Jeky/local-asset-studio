const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');
const references = fs.readFileSync(path.join(__dirname, '../app/static/references.js'), 'utf8');
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
    "let referenceEpoch=0,referencePending=0;const updateReady=()=>{};const $=()=>({textContent:''});",
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
    "let pickerBusy=false,handoffBusy=false,submitting=false,restoring=false,referencePending=0;let secondPicture={asset:{id:'replacement',sha256:'b'.repeat(64),title:'Replacement'}},continuationState={version:1,intent:'edit',preset_id:'recipe',reference_file:'a'.repeat(32)+'_old.png',source_asset_id:'source',source_sha256:'a'.repeat(64),template_sha256:'c'.repeat(64)};",
    "const selected={id:'recipe'};let selectionEpoch=0,referenceEpoch=0,stamp='before',astamp='before',finish,fail,uploaded='old-upload',draftDirty=false;",
    "const notices=[];const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',files:[]});return nodes.get(selector);};",
    "const window={confirm:()=>true};const dismissSecondPicture=()=>{secondPicture=null};",
    "const selectPreset=()=>{stamp='reset';astamp='reset';selectionEpoch++;continuationState=null};const workbenchStamp=()=>stamp;const attachStamp=()=>astamp;",
    "const post=()=>new Promise((resolve,reject)=>{finish=resolve;fail=reject});",
    "let replaceCount=0,saveCount=0,syncCount=0;const attachContinuationSource=result=>{uploaded=result.file;replaceCount++};",
    "const replaceParentAsset=()=>{replaceCount++};const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});const secondName=item=>item.asset.title;const syncReady=()=>{};",
    "const legacyReferenceChange=null;const DataTransfer=function(){};const Event=function(){};",
    replaceSecondPictureSource,
    "this.start=()=>q('#uxSecondReplace').onclick();this.setStamp=value=>{stamp=value;astamp=value};this.editWording=()=>{stamp='typed wording'};this.finish=value=>finish(value);this.fail=error=>fail(error);this.draft=()=>JSON.stringify({stamp,continuationState,secondPicture});",
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

test('wording-only edits do not cancel source replacement', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.editWording();
  harness.finish(replacement());
  await pending;
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'b'.repeat(32)+'_replacement.png',draftDirty:true,replaceCount:1,saveCount:1,syncCount:1,
  });
  assert.equal(harness.notices.at(-1).error, false);
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
