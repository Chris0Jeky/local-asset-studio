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

const openHandoffSource = between('  function openHandoff(', "\n  q('#uxDestination').onchange=destinationDetails;");
const useSecondPictureSource = between('  const useSecondPicture=', "\n  q('#uxSecondRestyle').onclick=");
const pullIntoSlotSource = between('  async function pullIntoSlot(', "\n  q('#uxSourceAssets').onclick=");

function secondPictureHarness(sourceExists) {
  const context = {};
  const asset = sourceExists
    ? "[{id:'source',title:'Source',review:'unreviewed',sha256:'a'.repeat(64),media_type:'image',trashed_at:null}]"
    : '[]';
  vm.runInNewContext([
    "let secondPicture={asset:{id:'style',title:'Style'}},pendingStyle=null;",
    "const continuationState={source_asset_id:'source'};",
    "const boardDestination=()=>({id:'restyle-recipe'});",
    "const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',innerHTML:'',textContent:''});return nodes.get(selector);};",
    "const dismissSecondPicture=()=>{};const syncReady=()=>{};",
    "let handoffEpoch=0,sourceContext=null,handoffBaseline=null,handoffIntent='edit',handoffId=null;",
    "const assetDetailsDirty=()=>false;const warnUnsavedAsset=()=>{};",
    "const catalog={presets:[]};const notices=[];const announce=(message,error=false)=>notices.push({message,error});",
    `const assetState={assets:${asset}};`,
    "const workbenchStamp=()=> 'stamp';const assetPreview=()=>'<img>';const escape=value=>String(value);",
    "const handoffRecipes=()=>{};const destinationDetails=()=>{};",
    "const handoff={open:false,showModal(){this.open=true;}};",
    "const readSource=()=>new Promise(()=>{});",
    openHandoffSource,
    useSecondPictureSource,
    "this.run=useSecondPicture('restyle');this.pending=()=>pendingStyle;this.dialog=handoff;this.notices=notices;",
    "this.openDirect=()=>openHandoff('source','restyle-recipe',undefined,'restyle');",
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
    "const selected={continuation_capability:{}};const StudioContinuation={sourceInput:()=> 'last_reference'};",
    "const post=()=>new Promise((resolve,reject)=>{finish=resolve;fail=reject;});",
    "const workbenchStamp=()=>stamp;let renderCount=0,replaceCount=0,saveCount=0,syncCount=0;",
    "const renderReferenceSlots=()=>{renderCount++};const replaceParentAsset=()=>{replaceCount++};",
    "const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});",
    pullIntoSlotSource,
    "this.start=()=>pullIntoSlot(0,'style-asset');this.setStamp=value=>{stamp=value};",
    "this.finish=value=>finish(value);this.fail=error=>fail(error);",
    "this.snapshot=()=>JSON.stringify(referenceRecords[0]);",
    "this.counts=()=>[renderCount,replaceCount,saveCount,syncCount];this.notices=notices;",
  ].join('\n'), context);
  return context;
}

test('a delayed copy cannot overwrite a newer workbench state', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.setStamp('after');
  harness.finish({parent_asset:'style-asset',file:'style.png'});
  assert.equal(await pending, false);
  assert.deepEqual(JSON.parse(harness.snapshot()), {parent_asset:'old-parent',file:'old.png',missing:false});
  assert.deepEqual(Array.from(harness.counts()), [0,0,0,0]);
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /workbench changed/);
});

test('a failed copy is reported without an unhandled rejection', async () => {
  const harness = pullHarness();
  const pending = harness.start();
  harness.fail(new Error('offline'));
  assert.equal(await pending, false);
  assert.deepEqual(Array.from(harness.counts()), [0,0,0,0]);
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
  const context = {};
  vm.runInNewContext([
    "let secondPicture={asset:{id:'replacement',title:'Replacement'}},continuationState={source_asset_id:'source'};",
    "const selected={id:'recipe'};let stamp='before',finish,uploaded='old-upload',draftDirty=false;",
    "const notices=[];const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',files:[]});return nodes.get(selector);};",
    "const window={confirm:()=>true};const dismissSecondPicture=()=>{secondPicture=null};",
    "const selectPreset=()=>{stamp='reset'};const workbenchStamp=()=>stamp;",
    "const post=()=>new Promise(resolve=>{finish=resolve});",
    "let replaceCount=0,saveCount=0,syncCount=0;",
    "const replaceParentAsset=()=>{replaceCount++};const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});const secondName=item=>item.asset.title;",
    "const legacyReferenceChange=null;const DataTransfer=function(){};const Event=function(){};",
    replaceSecondPictureSource,
    "this.start=()=>q('#uxSecondReplace').onclick();this.setStamp=value=>{stamp=value};this.finish=value=>finish(value);",
    "this.state=()=>JSON.stringify({uploaded,draftDirty,replaceCount,saveCount,syncCount});this.notices=notices;",
  ].join('\n'), context);
  return context;
}

test('a delayed replacement copy cannot overwrite a newer workbench state', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.setStamp('changed');
  harness.finish({file:'replacement.png'});
  await pending;
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'old-upload',draftDirty:false,replaceCount:0,saveCount:0,syncCount:0,
  });
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /workbench changed/);
});

test('a current replacement copy commits once', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.finish({file:'replacement.png'});
  await pending;
  assert.deepEqual(JSON.parse(harness.state()), {
    uploaded:'replacement.png',draftDirty:true,replaceCount:1,saveCount:1,syncCount:1,
  });
  assert.equal(harness.notices.length, 1);
  assert.equal(harness.notices[0].error, false);
  assert.match(harness.notices[0].message, /now the reference/);
});
