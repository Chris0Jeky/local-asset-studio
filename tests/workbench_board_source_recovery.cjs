const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');

function between(start, end) {
  const first = source.indexOf(start);
  assert.notEqual(first, -1, `missing source marker: ${start}`);
  const last = source.indexOf(end, first);
  assert.notEqual(last, -1, `missing source marker: ${end}`);
  return source.slice(first, last);
}

const restoreDraftSource = between(
  '  async function restoreDraft(draft){',
  "\n  q('#uxRestoreDraft').onclick=",
);
const pickerSource = between(
  "  q('#uxSourceAssets').onclick=async e=>{",
  "\n  picker.addEventListener('cancel'",
);

function restoreHarness({transportFailure = false} = {}) {
  const context = {};
  vm.runInNewContext([
    "let selected={id:'board',reference_slots:[{id:'style'}],last_reference:true};",
    "let uploaded='slot.png',lastUploaded='keep.png',restoring=false,selectionEpoch=7,recipeTemplateHash=null,draftDirty=true;",
    "let pendingInputs=new Set();const released=[],requests=[],notices=[];",
    "const catalog={presets:[{id:'board'}]};",
    "const applySaved=()=>{};const syncReady=()=>{};const syncCreate=()=>{};",
    transportFailure
      ? "const post=async(path,body)=>{requests.push({path,body});throw Error('offline');};"
      : "const post=async(path,body)=>{requests.push({path,body});return body.files.map(file=>({file,available:file!=='keep.png'}));};",
    "const releaseInputParent=name=>released.push(name);",
    "const announce=(message,error=false)=>notices.push({message,error});",
    restoreDraftSource,
    "this.restore=()=>restoreDraft({recipe:{preset:'board'},templateHash:'template',pendingInputs:[]});",
    "this.state=()=>JSON.stringify({uploaded,lastUploaded,pending:[...pendingInputs],released,requests,notices,restoring,draftDirty});",
  ].join('\n'), context);
  return context;
}

test('restoring a board draft rechecks and releases an unavailable picture-to-keep copy', async () => {
  const harness = restoreHarness();
  await harness.restore();
  const state = JSON.parse(harness.state());
  assert.deepEqual(state.requests, [{path:'/api/references/check',body:{files:['keep.png']}}]);
  assert.equal(state.uploaded, 'slot.png', 'the role-slot mirror is not the board continuation source');
  assert.equal(state.lastUploaded, null);
  assert.deepEqual(state.pending, ['lastReference']);
  assert.deepEqual(state.released, ['lastReference']);
  assert.equal(state.restoring, false);
  assert.equal(state.draftDirty, false);
  assert.equal(state.notices.at(-1).error, false);
  assert.match(state.notices.at(-1).message, /Draft restored/);
});

test('an unavailable board-source check preserves the role slot and marks only the named source uncertain', async () => {
  const harness = restoreHarness({transportFailure:true});
  await harness.restore();
  const state = JSON.parse(harness.state());
  assert.deepEqual(state.requests, [{path:'/api/references/check',body:{files:['keep.png']}}]);
  assert.equal(state.uploaded, 'slot.png');
  assert.equal(state.lastUploaded, null);
  assert.deepEqual(state.pending, ['lastReference']);
  assert.deepEqual(state.released, [], 'an unknown availability result must retain its lineage claim');
  assert.equal(state.notices.at(-1).error, true);
  assert.match(state.notices.at(-1).message, /availability could not be checked: offline/);
});

function pickerHarness(sourceInput) {
  const context = {};
  vm.runInNewContext([
    "let pickerBusy=false,continuationState=null,uploaded='existing-source.png',lastUploaded=null,draftDirty=false;",
    "const selected={reference_slots:[{id:'style'}],reference_board:null,continuation_capability:{}};",
    "const referenceRecords=[{parent_asset:'old-parent',file:null,missing:true}];",
    `const StudioContinuation={sourceInput:()=>${JSON.stringify(sourceInput)},sourceLabel:()=> 'Source'};`,
    "const pendingInputs=new Set(),notices=[];",
    "const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',innerHTML:'',textContent:'',onclick:null});return nodes.get(selector);};",
    "q('#uxSourceSlot').value='0';",
    "const button={dataset:{uxPull:'asset-2'},disabled:false};const event={target:{closest:()=>button}};",
    "const post=async()=>({file:'slot.png',parent_asset:'asset-2'});const workbenchStamp=()=> 'stamp';",
    "let renderCount=0,replaceCount=0,saveCount=0,syncCount=0;",
    "const renderReferenceSlots=()=>{renderCount++};const replaceParentAsset=()=>{replaceCount++};",
    "const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};const syncReady=()=>{};",
    "const nextEmptySlot=()=>-1;const sourceSlotOptions=()=>'';",
    "const picker={closed:false,close(){this.closed=true}};",
    "const announce=(message,error=false)=>notices.push({message,error});",
    pickerSource,
    "this.run=()=>q('#uxSourceAssets').onclick(event);",
    "this.state=()=>JSON.stringify({uploaded,slot:referenceRecords[0],pickerClosed:picker.closed,buttonDisabled:button.disabled,renderCount,replaceCount,saveCount,syncCount,notices});",
  ].join('\n'), context);
  return context;
}

test('slot zero does not overwrite uploaded when the continuation source belongs to lastReference', async () => {
  const harness = pickerHarness('last_reference');
  await harness.run();
  const state = JSON.parse(harness.state());
  assert.equal(state.uploaded, 'existing-source.png');
  assert.equal(state.slot.file, 'slot.png');
  assert.equal(state.slot.missing, false);
  assert.equal(state.pickerClosed, true);
  assert.equal(state.buttonDisabled, false);
  assert.deepEqual([state.renderCount,state.replaceCount,state.saveCount,state.syncCount],[1,1,1,1]);
});

test('slot zero still mirrors uploaded for a reference-owned slot recipe', async () => {
  const harness = pickerHarness('reference');
  await harness.run();
  const state = JSON.parse(harness.state());
  assert.equal(state.uploaded, 'slot.png');
  assert.equal(state.slot.file, 'slot.png');
  assert.deepEqual([state.renderCount,state.replaceCount,state.saveCount,state.syncCount],[1,1,1,1]);
});
