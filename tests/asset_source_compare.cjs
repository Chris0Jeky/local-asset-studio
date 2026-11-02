'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),F=require('../app/static/asset-family.js');
const workspace='a'.repeat(32),hash='b'.repeat(64),sourceHash='c'.repeat(64);
test('a held comparison render preserves focus moved into Notes',async()=>{
  // Exercise the actual private renderer without adding a browser dependency to this contract suite.
  const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../app/static/asset-family.js'),'utf8');
  const start=source.indexOf('    async function chooseSource(parent){'),end=source.indexOf('\n    function clear(){',start);
  assert(start>0&&end>start);
  let release;
  const notes={tagName:'TEXTAREA'},box={replaceChildren(){},append(){}},line={};
  const d={activeElement:{tagName:'BUTTON'},createElement:()=>({addEventListener(){},append(){}})};
  const title={focus(){d.activeElement=title;}};
  const scope={d,dialog:{open:true},comparisonReport:{},comparisonPanel:{hidden:false,querySelectorAll:()=>[]},
    shownPair:null,shownSession:null,choiceEpoch:0,options:{comparisonContext:()=>({session:'same-detail'})},
    comparison:{choose:()=>new Promise(resolve=>{release=resolve;})},
    q:selector=>({'#assetSourceImages':box,'#assetSourceStatus':line,'#assetSourceTitle':title}[selector])};
  const vm=require('node:vm');vm.createContext(scope);vm.runInContext(source.slice(start,end)+'\nthis.chooseSource=chooseSource;',scope);
  const pending=scope.chooseSource('source');d.activeElement=notes;
  release({current:()=>true,child:{title:'child',url:'/child'},source:{title:'source',url:'/source'}});
  await pending;
  assert.equal(d.activeElement,notes,'Delayed image display must not move typing into K/W/X review shortcuts');
});
const asset=(id,sha,extra={})=>({id,sha256:sha,workspace_id:workspace,media_type:'image',privacy:'regular',trashed_at:null,title:id,url:'/api/assets/'+id+'/file',...extra});
const report=()=>({version:1,asset_id:'repair',workspace_id:workspace,nodes:['source','repair'].map(id=>({id,state:'active',title:id,operation:null,seed:null,strength:null})),edges:[{parent:'source',child:'repair'}],gaps:[],truncated:false,children:null,children_truncated:false,children_scanned:0,observation_only:true,generation_submitted:false,media_bytes_verified:false});
function fixture(){
  const state={workspace,stamp:'detail-1'},records=new Map([['repair',asset('repair',hash)],['source',asset('source',sourceHash)]]),reads=[];
  const options={context:()=>({...state}),asset:()=>records.get('repair'),lookup:id=>records.get(id),resolve:async ids=>{reads.push(ids);return true;}};
  return {state,records,reads,options};
}
test('explicit recorded source choice observes both images without replacing the current asset',async()=>{
  const f=fixture(),before=structuredClone(f.records.get('repair'));
  const comparison=F.createComparison(f.options);
  assert.deepEqual(f.reads,[]);
  const pair=await comparison.choose(report(),'source');
  assert.deepEqual(f.reads,[['repair','source']]);
  assert.equal(pair.child.id,'repair');assert.equal(pair.source.id,'source');
  assert.equal(pair.child.sha256,hash);assert.equal(pair.source.sha256,sourceHash);assert.equal(pair.current(),true);
  assert.deepEqual(f.records.get('repair'),before);
  comparison.cancel();assert.equal(pair.current(),false);
});
test('no source is selected automatically, including a family with several parents',async()=>{
  const f=fixture(),r=report();r.nodes.push({...r.nodes[0],id:'other'});r.edges.push({parent:'other',child:'repair'});
  f.records.set('other',asset('other','d'.repeat(64)));
  const comparison=F.createComparison(f.options);
  await assert.rejects(comparison.choose(r),/Choose a recorded direct source/);assert.deepEqual(f.reads,[]);
  const pair=await comparison.choose(r,'other');assert.equal(pair.source.id,'other');
  assert.deepEqual(f.reads,[['repair','other']]);
});
for(const [name,change] of [
  ['wrong Workspace',r=>r.workspace_id='d'.repeat(32)],['wrong child',r=>r.asset_id='other'],
  ['unrecorded source',r=>r.edges=[]],['transitive ancestor',r=>r.edges=[{parent:'source',child:'intermediate'}]],
  ['bounded incomplete family',r=>r.truncated=true],['family gap',r=>r.gaps=[{id:'earlier',reason:'depth'}]],
  ['duplicate parent',r=>r.edges.push({...r.edges[0]})],['self parent',r=>r.edges=[{parent:'repair',child:'repair'}]],
  ['missing source',r=>r.nodes[0].state='missing'],['trashed source',r=>r.nodes[0].state='trashed'],
  ['false byte-verification claim',r=>r.media_bytes_verified=true]
])test(name+' refuses before resolving images',async()=>{
  const f=fixture(),r=report();change(r);await assert.rejects(F.createComparison(f.options).choose(r,'source'));assert.deepEqual(f.reads,[]);
});
for(const [name,change] of [
  ['missing',f=>f.records.delete('source')],['trashed',f=>f.records.get('source').trashed_at=0],
  ['video',f=>f.records.get('source').media_type='video'],['private source of regular child',f=>f.records.get('source').privacy='private'],
  ['foreign Workspace',f=>f.records.get('source').workspace_id='d'.repeat(32)],
  ['missing hash',f=>delete f.records.get('source').sha256],['untrusted media URL',f=>f.records.get('source').url='https://foreign.example/image.png'],
  ['wrong asset media URL',f=>f.records.get('source').url='/api/assets/other/file']
])test('resolved '+name+' is unavailable rather than a comparison pair',async()=>{
  const f=fixture();change(f);await assert.rejects(F.createComparison(f.options).choose(report(),'source'));
});
test('private pictures use their existing scoped media and cannot mix with regular sources',async()=>{
  const f=fixture();for(const a of f.records.values()){a.privacy='private';a.url+='?privacy=private';}
  const pair=await F.createComparison(f.options).choose(report(),'source');assert.match(pair.source.url,/privacy=private$/);
  f.records.get('source').privacy='regular';await assert.rejects(F.createComparison(f.options).choose(report(),'source'),/same privacy/);
});
for(const boundary of ['Workspace A-B-A','privacy A-B-A','detail changed','receipt changed','closed','child hash changed'])test('held resolution is discarded after '+boundary,async()=>{
  const f=fixture();let release;f.options.resolve=()=>new Promise(resolve=>release=resolve);
  const comparison=F.createComparison(f.options),pending=comparison.choose(report(),'source');
  if(boundary==='closed')comparison.cancel();else if(boundary==='child hash changed')f.records.get('repair').sha256='e'.repeat(64);
  else f.state.stamp=boundary+' epoch 3';
  release(true);assert.equal(await pending,null);
});
test('the newest deliberate source choice wins when earlier resolution arrives late',async()=>{
  const f=fixture(),r=report();r.nodes.push({...r.nodes[0],id:'other'});r.edges.push({parent:'other',child:'repair'});
  f.records.set('other',asset('other','d'.repeat(64)));const releases=[];
  f.options.resolve=()=>new Promise(resolve=>releases.push(resolve));
  const comparison=F.createComparison(f.options),old=comparison.choose(r,'source'),latest=comparison.choose(r,'other');
  releases[1](true);const pair=await latest;assert.equal(pair.source.id,'other');releases[0](true);assert.equal(await old,null);assert.equal(pair.current(),true);
});
test('a late read failure after navigation neither returns a pair nor reports into the new context',async()=>{
  const f=fixture();let reject;f.options.resolve=()=>new Promise((_,r)=>reject=r);
  const pending=F.createComparison(f.options).choose(report(),'source');f.state.stamp='another detail';reject(Error('offline'));
  assert.equal(await pending,null);
});

for(const [name,change] of [
  ['child hash',f=>f.records.get('repair').sha256='e'.repeat(64)],
  ['source hash',f=>f.records.get('source').sha256='e'.repeat(64)],
  ['both privacy classifications',f=>{for(const a of f.records.values()){a.privacy='private';a.url+='?privacy=private';}}]
])test('receipt revalidation refuses changed '+name+' instead of adopting a different pair',async()=>{
  const f=fixture(),comparison=F.createComparison(f.options),previous=await comparison.choose(report(),'source');
  f.state.stamp='receipt-2';change(f);
  await assert.rejects(comparison.choose(report(),'source',previous),/changed|same privacy/);
});
test('receipt revalidation accepts new child metadata only with the original pair identities and hashes',async()=>{
  const f=fixture(),comparison=F.createComparison(f.options),previous=await comparison.choose(report(),'source');
  Object.assign(f.records.get('repair'),{title:'Saved title',notes:'Saved notes',review:'needs_work',metadata_revision:1});
  f.state.stamp='receipt-2';const renewed=await comparison.choose(report(),'source',previous);
  assert.equal(previous.current(),false);assert.equal(renewed.current(),true);
  assert.equal(renewed.child.title,'Saved title');assert.equal(renewed.child.sha256,hash);assert.equal(renewed.source.sha256,sourceHash);
});

function privateFunction(file,name,next){
  const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../app/static/'+file),'utf8');
  const start=source.indexOf('function '+name+'('),end=source.indexOf('\n'+next,start);
  assert(start>=0&&end>start,'The actual '+name+' implementation must exist');return source.slice(start,end);
}
test('only the existing confirmed child details-save path notifies the comparison after advancing receipt epoch',()=>{
  const events=[],focus={id:'saveAssetDetails'};
  const scope={assetReceiptEpoch:4,assetDetailPending:null,assetDetailConflict:null,
    applyAssetReceipt:()=>{scope.assetReceiptEpoch++;return true;},updateAssetCard(){},renderAssets(){},refreshAssets(){},
    document:{dispatchEvent:event=>events.push(event)},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}}};
  const vm=require('node:vm');vm.createContext(scope);
  vm.runInContext(privateFunction('workspace.js','syncAssetAfterSave','function applyAssetSaveReceipt')+'\nthis.sync=syncAssetAfterSave;',scope);
  const operation={id:'repair',epoch:3,kind:'details',command:{workspace_id:workspace,action:'edit',ids:['repair']}};
  scope.sync(operation,{},focus);
  assert.equal(events.length,1);assert.equal(events[0].type,'studio:asset-detail-saved');
  assert.equal(events[0].detail.asset_id,'repair');assert.equal(events[0].detail.workspace_id,workspace);
  assert.equal(events[0].detail.receipt_epoch,5);assert.equal(events[0].detail.detail_epoch,3);assert.equal(events[0].detail.focus,focus);
  for(const change of [{kind:'favorite'},{kind:'trash'},{kind:'archive'},{command:{...operation.command,ids:['repair','source']}}])scope.sync({...operation,...change},{},focus);
  scope.assetDetailConflict={};scope.sync(operation,{},focus);
  scope.assetDetailConflict=null;scope.assetDetailPending={};scope.sync(operation,{},focus);
  assert.equal(events.length,1,'Unrelated, mixed, conflicted or still-pending commands must not authorize preserving a pair');
});
test('the actual adapter adopts only an accepted receipt refresh before its queued presentation observer',()=>{
  const listeners=new Map(),observers=[],dialog={open:true};let installed,opened=0,cleared=0,accepted=true,notified;
  const family={opened(){opened++;},clear(){cleared++;},decorateResults(){},refreshAfterSave(receipt){notified=receipt;return accepted?Promise.resolve():false;}};
  const scope={document:{querySelector:s=>s==='#assetDialog'?dialog:s==='#gallery'?{}:null,addEventListener:(name,fn)=>listeners.set(name,fn)},
    MutationObserver:class{constructor(fn){observers.push(fn);}observe(){}},addEventListener(){},confirm(){return true;},
    StudioAssetFamily:{install:options=>{installed=options;return family;}},StudioSetupDraft:{stamp:()=>'',busy:()=>false},
    assetState:{workspace_id:workspace},activeAsset:asset('repair',hash),assetWorkspaceEpoch:1,assetPrivacyEpoch:0,assetReceiptEpoch:0,assetDetailEpoch:1,
    assetPrivacyScope:()=> 'regular',assetDetailValues:()=>({}),assetDetailDirty:()=>false,assetDetailPending:null,assetDetailConflict:null,assetDetailBusy:false,
    continuationState:null,tileState:null,parallaxState:null,api(){},message(){}};
  const vm=require('node:vm');vm.createContext(scope);
  vm.runInContext(require('node:fs').readFileSync(require('node:path').join(__dirname,'../app/static/asset-family-adapter.js'),'utf8'),scope);
  assert.equal(opened,1);const before=installed.comparisonContext(),receipt={asset_id:'repair'};
  scope.assetReceiptEpoch++;listeners.get('studio:asset-detail-saved')({detail:receipt});observers[0]();
  assert.equal(notified,receipt);assert.equal(opened,1,'The receipt continuation must not be immediately cleared by MutationObserver');
  const after=installed.comparisonContext();assert.notEqual(after.stamp,before.stamp);assert.equal(after.session,before.session);
  accepted=false;scope.assetReceiptEpoch++;listeners.get('studio:asset-detail-saved')({detail:{}});observers[0]();
  assert.equal(opened,2,'An unconfirmed or invalidated pair must follow ordinary clear-and-observe behavior');
  scope.assetPrivacyEpoch+=2;listeners.get('studio:privacy-change')();assert.equal(cleared,1);assert.equal(opened,3);
  assert.notEqual(installed.comparisonContext().session,after.session,'Privacy A-B-A changes the stable detail session too');
});

async function refreshFixture(){
  const f=fixture();Object.assign(f.state,{session:'same-detail',receipt:0,detail:1});
  const comparison=F.createComparison(f.options),pair=await comparison.choose(report(),'source');
  f.state.receipt=1;f.state.stamp='receipt-1';f.reads.length=0;
  const body={},notes={id:'assetNotes',isConnected:true,disabled:false},button={id:'saveAssetDetails',isConnected:true,disabled:false};
  const d={body,activeElement:body};button.focus=()=>{d.activeElement=button;};notes.focus=()=>{d.activeElement=notes;};
  const box={clears:0,replaceChildren(){this.clears++;}},line={},family={},messages=[],painted=[],familyReads=[];
  const panel={hidden:false,contains:()=>false};
  const scope={epoch:1,choiceEpoch:1,controller:null,currentId:'repair',shownPair:pair,shownSession:'same-detail',
    comparisonReport:report(),comparisonScope:'old',comparison,recall:{cancel(){}},
    options:{...f.options,comparisonContext:f.options.context,read:async url=>{familyReads.push(url);return report();}},
    d,dialog:{open:true,contains:node=>[button,notes].includes(node)},comparisonPanel:panel,
    q:selector=>({'#assetSourceImages':box,'#assetSourceStatus':line,'#assetFamilyTree':family,'#assetFamilyStatus':{}}[selector]),
    validate:F.validate,treeMarkup:F.treeMarkup,AbortController,setTimeout:()=>1,clearTimeout(){},
    paintPair:next=>{painted.push(next);scope.shownPair=next;scope.shownSession=f.state.session;return true;},
    clearComparison:()=>{scope.choiceEpoch++;comparison.cancel();scope.shownPair=null;panel.hidden=true;box.replaceChildren();},
    say:message=>messages.push(message)};
  const vm=require('node:vm');vm.createContext(scope);
  vm.runInContext(privateFunction('asset-family.js','refreshAfterSave','    function clear()')+'\nthis.refresh=refreshAfterSave;',scope);
  const receipt={asset_id:'repair',workspace_id:workspace,detail_epoch:1,receipt_epoch:1,focus:button};
  return {...f,scope,receipt,d,notes,button,box,line,panel,painted,messages,familyReads};
}
test('a confirmed save rechecks the recorded family and exact chosen IDs before painting and returning displaced focus',async()=>{
  const f=await refreshFixture();let release;f.scope.options.read=url=>{f.familyReads.push(url);return new Promise(resolve=>release=resolve);};
  const pending=f.scope.refresh(f.receipt);
  assert.equal(f.panel.hidden,false);assert.equal(f.box.clears,1);assert.equal(f.painted.length,0);assert.deepEqual(f.reads,[]);
  release(report());await pending;
  assert.equal(f.familyReads.length,1);assert.deepEqual(f.reads,[['repair','source']]);
  assert.equal(f.painted[0].source.id,'source');assert.equal(f.d.activeElement,f.button);
});
test('revalidation completion preserves newer Notes focus instead of restoring the old Save focus',async()=>{
  const f=await refreshFixture();let release,entered;const reading=new Promise(resolve=>entered=resolve);
  f.options.resolve=()=>{entered();return new Promise(resolve=>release=resolve);};
  const pending=f.scope.refresh(f.receipt);await reading;f.notes.focus();
  release(true);await pending;
  assert.equal(f.painted.length,1);assert.equal(f.d.activeElement,f.notes);
});
for(const [name,change] of [['unconfirmed choice',f=>f.scope.shownPair=null],['changed detail session',f=>f.state.session='other-detail'],['other child',f=>f.receipt.asset_id='source'],
                           ['other Workspace',f=>f.receipt.workspace_id='d'.repeat(32)],['old receipt',f=>f.receipt.receipt_epoch=0],['old detail',f=>f.receipt.detail_epoch=0]])
test('a receipt with '+name+' cannot resume a pair',async()=>{
  const f=await refreshFixture();change(f);assert.equal(f.scope.refresh(f.receipt),false);
  assert.deepEqual(f.reads,[]);assert.deepEqual(f.familyReads,[]);assert.equal(f.painted.length,0);
});
for(const [name,change] of [
  ['source hash',f=>f.records.get('source').sha256='e'.repeat(64)],
  ['source Trash',f=>f.records.get('source').trashed_at=0],
  ['child Trash',f=>f.records.get('repair').trashed_at=0],
  ['source privacy',f=>f.records.get('source').privacy='private']
])test('fresh '+name+' invalidation clears the saved comparison',async()=>{
  const f=await refreshFixture();change(f);f.notes.focus();await f.scope.refresh(f.receipt);
  assert.equal(f.panel.hidden,true);assert.equal(f.painted.length,0);assert.equal(f.d.activeElement,f.notes);
});
test('a newer receipt supersedes an older held revalidation, including its late failure',async()=>{
  for(const failed of [false,true]){
    const f=await refreshFixture(),releases=[];
    f.scope.options.read=()=>new Promise((resolve,reject)=>releases.push({resolve,reject}));
    const old=f.scope.refresh(f.receipt);
    f.state.receipt=2;f.state.stamp='receipt-2';
    const latest=f.scope.refresh({...f.receipt,receipt_epoch:2});releases[1].resolve(report());await latest;
    f.notes.focus();if(failed)releases[0].reject(Error('old failure'));else releases[0].resolve(report());await old;
    assert.equal(f.painted.length,1);assert.equal(f.panel.hidden,false);assert.deepEqual(f.messages,[]);assert.equal(f.d.activeElement,f.notes);
  }
});
test('a newer receipt also supersedes an older selected-ID reply or failure',async()=>{
  for(const failed of [false,true]){
    const f=await refreshFixture(),releases=[];let entered;
    f.options.resolve=()=>{const pending=new Promise((resolve,reject)=>releases.push({resolve,reject}));entered();return pending;};
    const firstRead=new Promise(resolve=>entered=resolve),old=f.scope.refresh(f.receipt);await firstRead;
    f.state.receipt=2;f.state.stamp='receipt-2';
    const secondRead=new Promise(resolve=>entered=resolve),latest=f.scope.refresh({...f.receipt,receipt_epoch:2});await secondRead;
    releases[1].resolve(true);await latest;f.notes.focus();
    if(failed)releases[0].reject(Error('old selected-ID failure'));else releases[0].resolve(true);await old;
    assert.equal(f.painted.length,1);assert.equal(f.panel.hidden,false);assert.deepEqual(f.messages,[]);assert.equal(f.d.activeElement,f.notes);
  }
});
for(const boundary of ['new choice','close','Workspace A-B-A','privacy A-B-A'])test('held receipt revalidation cannot paint after '+boundary,async()=>{
  const f=await refreshFixture();let release;f.scope.options.read=()=>new Promise(resolve=>release=resolve);
  const pending=f.scope.refresh(f.receipt);
  if(boundary==='close')f.scope.clearComparison();else if(boundary==='new choice')f.scope.choiceEpoch++;
  else {f.state.session=boundary+' epoch3';f.state.stamp=boundary+' epoch3';}
  release(report());await pending;assert.equal(f.painted.length,0);assert.deepEqual(f.reads,[]);
});
