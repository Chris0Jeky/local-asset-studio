'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../app/static/studio-workbench.js'),'utf8');
const C=require('../app/static/continuation-core.js'),U=require('../app/static/studio-core.js');
function section(start,end){const a=code.indexOf(start),b=code.indexOf(end,a+start.length);assert.ok(a>=0&&b>a,start);return code.slice(a,b);}
function box(extra={}){
  const nodes=new Map(),b={StudioContinuation:C,U,selected:{id:'plain'},catalog:{presets:[]},jobs:[],assetState:{assets:[]},
    pendingInputs:[],uploaded:null,lastUploaded:null,continuationState:null,continuationSource:null,secondPicture:null,
    sharedAdoptionError:'',varyUnapplied:null,missingByPreset:{},online:true,schemaAvailable:true,workerAlive:true,
    submitting:false,handoffBusy:false,pickerBusy:false,restoring:false,pairActionBusy:false,poseBusy:false,varyBusy:false,
    tileBusy:false,parallaxBusy:false,planBusy:false,polishBusy:new Set(),makeVaryBusy:new Set(),referencePending:0,
    referencesReady:()=>true,posePositionDirty:()=>false,poseHeldArtifact:()=>null,poseSizeHold:()=>'',i2vModeBlocker:()=>'',
    continuationBlockerItems:()=>[],continuationActions:{},backendActive:'primary',parentAssets:[],values:()=>({}),attachedReferencePayload:()=>[],
    notices:[],announce:(...args)=>b.notices.push(args),syncReady:()=>{},assetDetailsDirty:()=>false,warnUnsavedAsset:()=>{},
    assetDetailEpoch:1,assetDetailContextCurrent:()=>true,applied:0,beginTile:()=>b.applied++,
    showView:()=>{},saveDraft:()=>{},syncCreate:()=>{},updateReady:()=>{},scheduleTimeEstimate:()=>{},recipeChanged:()=>{},
    q:s=>{if(!nodes.has(s))nodes.set(s,{value:'',files:[],open:false,disabled:false});return nodes.get(s);},...extra};
  vm.createContext(b);return b;
}
const ready=section('  function readinessItems(){','\n  function syncReady(){');
const busy=section('  // sendBusy counts only','\n  // Each engine');
const generate=section('  const generateFromCreate=', '\n  function parallaxBoxes(');

test('plan and one-press sends block Generate readiness and its handler until settled',()=>{
  for(const flag of ['planBusy','polishBusy','makeVaryBusy']){
    const b=box({generated:0});b.q('#generate').onclick=()=>b.generated++;
    vm.runInContext(ready+'\n'+busy+'\n'+generate+'\nthis.readinessItems=readinessItems;this.combineBusy=combineBusy;',b);
    if(flag==='planBusy')b[flag]=true;else b[flag].add('asset');
    assert.ok(b.readinessItems().items.some(i=>i.code==='busy'),flag+' must disable Generate');
    assert.ok(b.combineBusy(),flag+' must block engine switches');
    b.q('#generate').onclick();assert.equal(b.generated,0,flag+' must block programmatic Generate');
    if(flag==='planBusy')b[flag]=false;else b[flag].clear();
    b.q('#generate').onclick();assert.equal(b.generated,1,'settled action allows Generate');
  }
});

const polish=section('  const polishBusy=new Set();','\n  // #1497 Vary from Make:');
test('Polish refuses a concurrent Create send before copying or posting',async()=>{
  const b=box({submitting:true,readSource:async()=>{throw Error('should not read');}});
  vm.runInContext(busy+'\n'+polish+'\nthis.polish=polish;',b);
  await assert.rejects(b.polish('asset','face'),/Wait|finish|already/);
});
test('Create draft state (typed pose, pending upload) blocks Create but not a Make Polish',async()=>{
  const b=box({posePositionDirty:()=>true,referencePending:1,readSource:async()=>{throw Error('read reached');}});
  vm.runInContext(busy+'\n'+polish+'\nthis.polish=polish;this.combineBusy=combineBusy;',b);
  assert.ok(b.combineBusy(),'Create stays blocked');
  await assert.rejects(b.polish('asset','face'),/read reached/,'Make is not told to wait when nothing is in flight');
});
test('a held Polish send blocks Generate and another polish kind, then releases on error',async()=>{
  let rejectRead;const b=box({generated:0,readSource:()=>new Promise((_,reject)=>{rejectRead=reject;})});
  b.q('#generate').onclick=()=>b.generated++;
  vm.runInContext(ready+'\n'+busy+'\n'+polish+'\n'+generate+'\nthis.polish=polish;this.readinessItems=readinessItems;',b);
  const first=b.polish('asset','face');
  assert.ok(b.readinessItems().items.some(i=>i.code==='busy'));
  b.q('#generate').onclick();assert.equal(b.generated,0);
  await assert.rejects(b.polish('asset','details'),/Wait|finish|already/);
  rejectRead(Error('synthetic read failure'));await assert.rejects(first,/synthetic read failure/);
  b.q('#generate').onclick();assert.equal(b.generated,1);
});

test('backend change during Tile prepare refuses the late attachment',async()=>{
  let release;const b=box({post:()=>new Promise(resolve=>{release=resolve;})});
  vm.runInContext(busy+'\n'+section('  function workbenchStamp(){','\n  // Slot and picker')+'\n'+
    section('  async function prepareTile(button){',"\n  document.addEventListener('click',e=>{const button=e.target.closest('[data-ux-tile]')")+'\nthis.prepareTile=prepareTile;',b);
  const pending=b.prepareTile({dataset:{uxTile:'asset'},parentElement:{querySelector:()=>null}});
  b.backendActive='other';release({file:'rolled.png',plan:{source_asset_id:'asset',rolled_file:'rolled.png'}});await pending;
  assert.equal(b.applied,0,'a reply checked under another backend must not replace Create');
  assert.match(b.notices.at(-1)[0],/changed/);
  const control=b.prepareTile({dataset:{uxTile:'asset'},parentElement:{querySelector:()=>null}});
  release({file:'rolled.png',plan:{source_asset_id:'asset',rolled_file:'rolled.png'}});await control;
  assert.equal(b.applied,1,'unchanged backend still permits preparation');
  // A switch that has started but not finished leaves backendActive unchanged; the late reply is still refused.
  const switching=b.prepareTile({dataset:{uxTile:'asset'},parentElement:{querySelector:()=>null}});
  b.backendSwitching=true;release({file:'rolled.png',plan:{source_asset_id:'asset',rolled_file:'rolled.png'}});await switching;
  assert.equal(b.applied,1,'a reply that lands mid-switch must not replace Create');
});

test('shipped Combine boards have no per-picture guidance editor (finding 4 guard)',()=>{
  const catalog=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../presets/catalog.json'),'utf8'));
  const boards=catalog.presets.filter(p=>p.continuation_operation==='combine');assert.ok(boards.length);
  assert.ok(boards.every(p=>p.reference_board),'every engine-switch/rerun destination uses board policy');
  const refsCode=fs.readFileSync(require('node:path').join(__dirname,'../app/static/references.js'),'utf8');
  const b=box({selected:boards[0],referenceRecords:[{role:'pose',file:'pose.png',contribution:'',avoid:''}],
    document:{activeElement:null},referenceRenderedRecords:new Map(),boardSummaryLabel:()=>'',esc:String,referenceRoles:[],updateReady:()=>{}});
  b.$=b.q;b.q('#referenceCards').querySelectorAll=()=>[];
  const a=refsCode.indexOf('function renderReferenceSlots('),end=refsCode.indexOf('\nfunction ',a+1);
  assert.ok(a>=0&&end>a);vm.runInContext(refsCode.slice(a,end)+'\nrenderReferenceSlots();',b);
  assert.doesNotMatch(b.q('#referenceCards').innerHTML,/data-ref-contribution|data-ref-avoid/);
  const refs=[{role:'pose',file:'pose.png',contribution:'hands at her face',avoid:'the clothes',parent_asset:'pose'},
    {role:'style',file:'style.png',contribution:'soft shading',avoid:'the face',parent_asset:'style'}];
  const target={reference_slots:[{role:'composition'},{role:'style'}]};
  const kept=C.combineReferences(target,refs);
  assert.equal(kept[0].file,'pose.png');assert.equal(kept[0].contribution,'','board metadata matches compile_board');
});

test('a board handoff clears both native file inputs before attaching its source (finding 2 guard)',()=>{
  const app=fs.readFileSync(require('node:path').join(__dirname,'../app/static/app.js'),'utf8');
  const extract=(start,end)=>{const a=app.indexOf(start),b=app.indexOf(end,a+start.length);assert.ok(a>=0&&b>a);return app.slice(a,b);};
  const b=box({$:s=>b.q(s),catalog:{presets:[{id:'board',last_reference:true,continuation_capability:{source_input:'last_reference'}}]},
    recipeChanged:()=>{},renderPresets:()=>{},renderSelected:()=>{},message:()=>{},resetReferenceSlots:()=>{},referenceHint:()=>'',
    setHandoffParent:()=>{},claimInputParent:()=>{},parentByInput:{},referenceRecords:[]});
  // A native file input drops its FileList when its value is cleared.
  for(const id of ['reference','lastReference']){const input=b.q('#'+id);input.files=[{name:'extra.png'}];
    Object.defineProperty(input,'value',{set(value){if(value==='')this.files=[];},get(){return this.files.length?'extra.png':'';}});}
  vm.runInContext(extract('function clearReference()','\nfunction ')+'\n'+extract('function selectPreset(','\nasync function refreshHealth')+'\n'+
    extract('function attachContinuationSource(','\nfunction beginContinuation(')+
    "\nselectPreset('board',true,true);attachContinuationSource({file:'source.png',context:{asset_id:'source'}});",b);
  assert.equal(b.q('#reference').files.length,0,'the extra file cannot reach uploadInput');
  assert.equal(b.q('#lastReference').files.length,0);
  assert.equal(b.lastUploaded,'source.png');
});

test('Vary and Polish refuse unsettled jobs but allow saved partial, completed or imported pictures',async()=>{
  const b=box({readSource:async()=>({asset_id:'asset',job_id:'job'})});
  b.StudioContinuation={...C,varyPlan:()=>({kind:'img2img',route:{id:'vary',name:'Vary'}}),polishRoute:()=>({ok:true,preset:{id:'polish'}})};
  vm.runInContext(section('  function varyPlanFor(','\n  // Rebuilt only when')+'\n'+polish+'\nthis.varyPlanFor=varyPlanFor;this.polishPlan=polishPlan;',b);
  for(const status of ['queued','running','uncertain','failed']){
    b.jobs=[{id:'job',status}];
    assert.equal(b.varyPlanFor('plain','job','asset').kind,'none',status+' Vary');
    // Make's own reading of the run wins over a shared jobs list that has not refreshed yet.
    if(status==='running')assert.equal(b.varyPlanFor('plain','job','asset','image','completed').kind,'img2img','Make status completed');
    await assert.rejects(b.polishPlan('asset','face'),/completed source run/,status+' Polish must be retryable, not cached');
  }
  for(const jobs of [[{id:'job',status:'completed'}],[{id:'job',status:'partial'}],[]]){
    b.jobs=jobs;assert.equal(b.varyPlanFor('plain','job','asset').kind,'img2img');
    assert.equal((await b.polishPlan('asset','face')).ok,true);
  }
});
