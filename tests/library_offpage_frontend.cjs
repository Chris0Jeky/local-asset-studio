// Execute the shipped owners with controllable observations; page absence is not missing metadata.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {setup}=require('./asset_detail_contracts.cjs');
const Checks=require('../app/static/review-checks.js'),Continuation=require('../app/static/continuation-core.js');
const Family=require('../app/static/asset-family-adapter.js');
const scope='1'.repeat(32),stamp={epoch:'a'.repeat(32),revision:1};
const source=name=>fs.readFileSync(path.join(__dirname,'../app/static/',name),'utf8');
const workbench=source('studio-workbench.js');
const section=(text,start,end)=>{const at=text.indexOf(start),to=text.indexOf(end,at);assert.ok(at>=0&&to>at,'shipped section '+start);return text.slice(at,to);};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const asset=(id,extra={})=>({id,workspace_id:scope,title:id,notes:'',tags:[],review:'unreviewed',favorite:false,trashed_at:null,
  media_type:'image',preset_id:'combine',job_id:'run',metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,...extra});
let passed=0,failed=0;
async function test(name,run){try{await run();passed++;console.log('PASS',name);}catch(error){failed++;console.error('FAIL',name,'\n'+error.stack);}}
function combine({page=[],known=[],ids=['far'],jobs}={}){
  const records=new Map(known.map(a=>[a.id,a])),calls=[],saves=[],notices=[],panel={hidden:false,innerHTML:'',querySelector:()=>null,querySelectorAll:()=>[]};
  const line={textContent:''},preset={id:'combine',name:'Combine',continuation_capability:{operation:'combine'}};
  const context={console,JSON,Date,StudioReviewChecks:Checks,StudioContinuation:{...Continuation,combineKind:()=>true,sameCombinePair:()=>true},
    selected:preset,catalog:{presets:[preset]},referenceRecords:[],lastUploaded:null,resultMarkup:'',pairActionBusy:false,
    resultPanel:panel,assetState:{workspace_id:scope,assets:page},assetWorkspaceEpoch:1,
    assetRecord:id=>records.get(id),assetRecords:()=>[...records.values()],jobs:jobs||[{id:'run',status:'completed',preset_id:'combine',outputs:ids.map((id,i)=>({asset_id:id,media_type:'image',seed:i+1}))}],
    currentPair:()=>({}),combineBusy:()=>false,escape:String,durationLabel:String,submitting:false,poseBusy:false,posePositionDirty:()=>false,
    setupVersion:1,setupStamp:()=>String(context.setupVersion),q:()=>line,document:{activeElement:null},announce:(text,error)=>notices.push({text,error}),
    refreshAssets:async()=>true,resolveAssetIDs:async requested=>{calls.push([...requested]);for(const id of requested)records.set(id,asset(id,{review:'selected',tags:['check:pose=yes']}));return true;},
    mutateAssets:async payload=>saves.push(JSON.parse(JSON.stringify(payload)))};
  context.syncReady=()=>vm.runInContext('syncCombineResults()',context);
  vm.createContext(context);
  vm.runInContext(section(workbench,'  function engineChecks(', '\n'),context);
  vm.runInContext(section(workbench,'  function syncCombineResults(', '  // Number keys 1-5'),context);
  const render=()=>{vm.runInContext('syncCombineResults()',context);return panel.innerHTML;};
  const press=dataset=>panel.onclick({target:{closest:()=>({dataset,disabled:false})}});
  return {context,records,calls,saves,notices,line,panel,render,press};
}
function family(){
  const state={workspace:scope,workspaceEpoch:1,assetId:'far',assetEpoch:1,fields:{notes:''},dirty:false,pending:false,conflict:false,metadataBusy:false,specialized:false};
  const records=new Map(),calls=[],picked=[];let ownerStamp='draft';
  const options={state:()=>state,owner:{stamp:()=>ownerStamp,busy:()=>false},asset:id=>records.get(id),
    resolve:async ids=>{calls.push([...ids]);for(const id of ids)records.set(id,asset(id));return true;},picker:async(...args)=>picked.push(args)};
  return {state,records,calls,picked,options,adapter:Family.create(options),changeDraft:()=>{ownerStamp='new draft';}};
}
function figures(){
  const parent=asset('parent'),records=new Map([['parent',parent]]),calls=[];
  const context={console,setTimeout,Date,REFRESH_ATTEMPTS:2,REFRESH_IDLE_TIMEOUT_MS:50,REFRESH_POLL_MS:1,
    assetState:{workspace_id:scope,assets:[parent]},assetRefreshing:false,globals:{asset:()=>parent},
    assetRecord:id=>records.get(id),refreshAssets:async()=>true,
    resolveAssetIDs:async ids=>{calls.push([...ids]);for(const id of ids)records.set(id,asset(id));return true;}};
  vm.createContext(context);
  vm.runInContext('globalThis.refreshSplit=({'+section(source('addressable-figures.js'),'      async refresh(', '\n      open(id)')+'}).refresh;',context);
  return {context,records,calls,refresh:ids=>context.refreshSplit(ids,scope)};
}
function pickerWorld(){
  const elements=new Map(),calls=[],escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const q=id=>{if(!elements.has(id))elements.set(id,{value:'',innerHTML:''});return elements.get(id);};
  const context=vm.createContext({q,escape,esc:escape,picker:{open:true},assetPreview:()=>'<span>Preview</span>',
    assetReadURL:(path,query)=>path+'?'+new URLSearchParams(query),api:url=>{const gate=deferred();calls.push({...gate,url});return gate.promise;}});
  vm.runInContext(section(source('workspace.js'),'function unavailableAssetDetails(', '\n'),context);
  vm.runInContext(section(workbench,'  let sourcePage=', '  function syncSourceAvailability('),context);
  return {q,calls,run:code=>vm.runInContext(code,context)};
}
(async()=>{
  await test('Combine does not call an off-page output unreviewed or display invented unanswered checks',()=>{
    const s=combine(),html=s.render();assert.match(html,/Saved review not loaded/);assert.match(html,/data-ux-check-load="far"/);
    assert.doesNotMatch(html,/>Unreviewed<|data-ux-check="\w+" data-asset="far"/);
  });
  await test('Combine tiles and engine totals use canonical resolved metadata with an explicit loaded scope',()=>{
    const s=combine({page:[asset('far')],known:[asset('far',{metadata_revision:2,review:'selected',tags:['check:pose=yes']})]});
    const html=s.render();assert.match(html,/>Kept</);assert.match(html,/class="review-check is-yes" data-ux-check="pose"/);
    assert.equal(vm.runInContext('engineChecks(selected)',s.context),'Loaded checks: pose 1/1');
    assert.match(html,/Loaded checks: pose 1\/1/);
  });
  await test('A resolved zero-timestamp Trash observation removes the Combine output',()=>{
    const s=combine({known:[asset('far',{trashed_at:0,tags:['check:pose=yes']})]});assert.doesNotMatch(s.render(),/class="ux-result-tile"/);assert.equal(vm.runInContext('engineChecks(selected)',s.context),'Loaded checks: none');
  });
  await test('Loading Combine checks is one bounded observation and makes no command or generation',async()=>{
    const s=combine();s.render();await s.press({uxCheckLoad:'far',asset:'far'});
    assert.deepEqual(s.calls,[['far']]);assert.deepEqual(s.saves,[]);assert.match(s.render(),/>Kept</);assert.match(s.line.textContent,/Loaded saved/);
  });
  for(const change of ['setup','workspace','workspace-aba'])await test('A held Combine review cannot save after '+change+' changes',async()=>{
    const s=combine({known:[asset('far')]}),gate=deferred();s.context.refreshAssets=()=>gate.promise;
    const pending=s.press({uxReview:'selected',asset:'far'});await flush();
    if(change==='setup')s.context.setupVersion++;else if(change==='workspace')s.context.assetState.workspace_id='2'.repeat(32);else s.context.assetWorkspaceEpoch+=2;
    gate.resolve(true);await pending;assert.deepEqual(s.saves,[]);assert.match(s.line.textContent,/changed/);
  });
  await test('An invalidated Combine checks observation cannot claim success',async()=>{
    const s=combine();s.context.resolveAssetIDs=async ids=>{s.calls.push([...ids]);return false;};
    await s.press({uxCheckLoad:'far',asset:'far'});assert.deepEqual(s.calls,[['far']]);assert.deepEqual(s.saves,[]);
    assert.match(s.line.textContent,/changed|could not/i);assert.doesNotMatch(s.line.textContent,/^Loaded saved/);
  });
  // #1204: the Grid on the Combine runs strip. Recipes are rows, seeds are columns; names of runs from a plan wait behind Reveal.
  const run=(id,preset,status,seed,asset,extra={})=>({id,status,preset_id:preset,preset_name:preset.toUpperCase()+' ENGINE',created_at:Number(id.slice(1)),controls:{seed:String(seed)},message:preset.toUpperCase()+' ENGINE said so',outputs:asset?[{asset_id:asset,media_type:'image',seed}]:[],...extra});
  const grid=(jobs,known=['a1','a2','a3','a4'])=>{const s=combine({jobs,known:known.map(id=>asset(id))});s.render();s.press({uxGrid:''});return s;};
  const names=html=>[...html.matchAll(/role="rowheader"[^>]*>([^<]*)</g)].map(m=>m[1]),heads=html=>[...html.matchAll(/role="columnheader"[^>]*>([^<]*)</g)].map(m=>m[1]);
  const plain=[run('r1','combine','completed',42,'a1'),run('r2','combine','completed',43,'a2'),run('r3','alt','completed',42,'a3'),run('r4','alt','failed',43,null)];
  await test('Combine Grid puts recipes in rows and seeds in columns, one cell each, and offers no rerun',()=>{
    const s=combine({jobs:plain,known:['a1','a2','a3'].map(id=>asset(id))});assert.match(s.render(),/aria-pressed="false"/);assert.doesNotMatch(s.panel.innerHTML,/role="grid"/);
    s.press({uxGrid:''});const html=s.panel.innerHTML;
    assert.match(html,/aria-pressed="true"/);assert.deepEqual(names(html),['ALT ENGINE','Combine']);assert.deepEqual(heads(html),['Recipe','Seed 42','Seed 43']);
    assert.equal((html.match(/role="gridcell"/g)||[]).length,4);assert.doesNotMatch(html,/data-ux-rerun|Reveal/);assert.match(html,/data-ux-review="selected" data-asset="a3"/);
    const failed=/data-ux-cell="0:1"[^>]*>(.*?)<\/div>/.exec(html)[1];assert.match(failed,/Failed/);assert.match(failed,/No picture/);assert.doesNotMatch(failed,/<button|<img/);
  });
  await test('Combine Grid is offered only when a run has a picture, and leaving it restores the list',()=>{
    const s=combine({jobs:[run('r1','alt','failed',42,null)],known:[]});assert.doesNotMatch(s.render(),/data-ux-grid/);
    const t=grid(plain);assert.match(t.panel.innerHTML,/role="grid"/);t.press({uxGrid:''});assert.doesNotMatch(t.panel.innerHTML,/role="grid"/);assert.match(t.panel.innerHTML,/ux-run-group/);
  });
  await test('Combine Grid shows the newest of repeated runs in one equal cell and says how many there are',()=>{
    const html=grid([run('r1','combine','completed',42,'a1'),run('r2','combine','completed',42,'a2')]).panel.innerHTML;
    assert.equal((html.match(/role="gridcell"/g)||[]).length,1);assert.match(html,/Newest of 2 pictures/);assert.equal((html.match(/<img /g)||[]).length,1);assert.match(html,/data-asset="a2"/);
  });
  await test('Combine Grid hides the recipe names of planned runs until Reveal, and hides them again on leaving',()=>{
    const planned={project_id:'p'.repeat(32)},jobs=[run('r1','combine','completed',42,'a1'),run('r3','alt','completed',42,'a3',planned),run('r4','alt','failed',43,null,planned),run('r5','alt','not_submitted',44,null,planned)];
    const s=grid(jobs);let html=s.panel.innerHTML;
    assert.deepEqual(names(html),['Combine','Candidate A']);assert.doesNotMatch(html,/ALT ENGINE|alt result/);assert.match(html,/data-ux-reveal/);
    assert.doesNotMatch(html,/data-ux-result-recipe="r5"/);assert.match(html,/data-ux-problem="r4"/);assert.match(html,/A planned run/);
    s.press({uxReveal:''});html=s.panel.innerHTML;assert.deepEqual(names(html),['Combine','ALT ENGINE']);assert.doesNotMatch(html,/data-ux-reveal/);assert.match(html,/ALT ENGINE said so/);
    s.press({uxGrid:''});s.press({uxGrid:''});html=s.panel.innerHTML;assert.deepEqual(names(html),['Combine','Candidate A']);assert.doesNotMatch(html,/ALT ENGINE/);
  });
  await test('Combine Grid keeps one tab stop on the held cell',()=>{
    const s=grid(plain,['a1','a2','a3']);assert.equal((s.panel.innerHTML.match(/tabindex="0"/g)||[]).length,1);assert.match(s.panel.innerHTML,/tabindex="0" data-ux-cell="0:0"/);
    s.panel.gridFocus='1:1';s.render();assert.match(s.panel.innerHTML,/tabindex="0" data-ux-cell="1:1"/);assert.equal((s.panel.innerHTML.match(/tabindex="0"/g)||[]).length,1);
    s.panel.gridFocus='9:9';s.render();assert.match(s.panel.innerHTML,/tabindex="0" data-ux-cell="0:0"/);
  });
  await test('Family reference resolves its explicit off-page image through the existing picker',async()=>{
    const s=family();await s.adapter.reference('far');assert.deepEqual(s.calls,[['far']]);assert.equal(s.picked.length,1);
    assert.equal(s.picked[0][0].id,'far');assert.equal(s.picked[0][1](),true);s.changeDraft();assert.equal(s.picked[0][1](),false);
  });
  for(const change of ['editor','workspace-aba','draft'])await test('A held family observation preserves newer '+change+' state',async()=>{
    const s=family(),gate=deferred();s.options.resolve=ids=>{s.calls.push([...ids]);return gate.promise;};s.adapter=Family.create(s.options);
    const result=s.adapter.reference('far').then(()=>null,e=>e);await flush();assert.equal(s.calls.length,1);
    if(change==='editor')s.state.fields.notes='newer words';else if(change==='workspace-aba')s.state.workspaceEpoch+=2;else s.changeDraft();
    s.records.set('far',asset('far'));gate.resolve(true);assert.match((await result).message,/changed|kept/i);assert.equal(s.picked.length,0);
  });
  await test('Confirmed figure children resolve outside the visible page without changing page rows',async()=>{
    const s=figures();assert.deepEqual(JSON.parse(JSON.stringify(await s.refresh(['child-a','child-b']))),{ok:true});
    assert.deepEqual(s.calls,[['child-a','child-b']]);assert.deepEqual(s.context.assetState.assets.map(a=>a.id),['parent']);
  });
  await test('Figure child resolution cannot target a different Workspace after refresh',async()=>{
    const s=figures();s.context.refreshAssets=async()=>{s.context.assetState.workspace_id='2'.repeat(32);return true;};
    const result=await s.refresh(['child']);assert.equal(result.ok,false);assert.match(result.error,/Workspace changed/);assert.deepEqual(s.calls,[]);
  });
  await test('A figure refresh cannot start a child observation after a Workspace ABA transition',async()=>{
    const s=figures();s.context.assetWorkspaceEpoch=1;s.context.refreshAssets=async()=>{s.context.assetWorkspaceEpoch+=2;return true;};
    const result=await s.refresh(['child']);assert.equal(result.ok,false);assert.match(result.error,/Workspace changed/);assert.deepEqual(s.calls,[]);
  });
  await test('A figure child removed after its receipt is not presented as available',async()=>{
    const s=figures();s.context.resolveAssetIDs=async ids=>{s.calls.push([...ids]);s.records.set('child',null);return true;};
    const result=await s.refresh(['child']);assert.equal(result.ok,false);assert.equal(s.calls.length,1);
  });
  await test('A failed off-page queue move leaves the editor and queue position together',async()=>{
    const s=setup();s.run("assetPaging={catalogue:{epoch:'a'.repeat(32),revision:1}};assetState.assets=assetState.assets.filter(a=>a.id==='a');assetQueue={ids:['a','b'],index:0}");
    const move=s.run('assetQueueStep(1)');await flush();assert.equal(s.run('assetQueue.index'),0);assert.equal(s.run('activeAsset.id'),'a');
    s.writes[0].resolve({workspace_id:scope,items:[{id:'b',state:'missing',asset:null}]});assert.equal(await move,false);
    assert.equal(s.run('assetQueue.index'),0);assert.equal(s.run('activeAsset.id'),'a');
  });
  await test('Leaving a queue while its off-page read is pending prevents late editor navigation',async()=>{
    const s=setup();s.run("assetPaging={catalogue:{epoch:'a'.repeat(32),revision:1}};assetState.assets=assetState.assets.filter(a=>a.id==='a');assetQueue={ids:['a','b'],index:0}");
    const move=s.run('assetQueueStep(1)');await flush();s.run('assetQueue=null;renderAssetQueue()');
    s.writes[0].resolve({workspace_id:scope,items:[{id:'b',state:'active',asset:asset('b')}]});await move;await flush();
    assert.equal(s.run('assetQueue'),null);assert.equal(s.run('activeAsset.id'),'a');
  });
  await test('An older off-page queue move cannot rewind a newer completed transition',async()=>{
    const s=setup();s.run("assetPaging={catalogue:{epoch:'a'.repeat(32),revision:1}};assetState.assets=assetState.assets.filter(a=>a.id==='a');assetQueue={ids:['a','b'],index:0}");
    const first=s.run('assetQueueStep(1)'),second=s.run('assetQueueStep(1)');await flush();assert.equal(s.writes.length,2);
    const reply={workspace_id:scope,items:[{id:'b',state:'active',asset:asset('b')}]};s.writes[1].resolve(reply);assert.equal(await second,true);assert.equal(s.run('activeAsset.id'),'b');assert.equal(s.run('assetQueue.index'),1);
    s.writes[0].resolve(reply);assert.equal(await first,false);assert.equal(s.run('activeAsset.id'),'b');assert.equal(s.run('assetQueue.index'),1);
  });
  await test('An all-unavailable source-picker page names its observed rows and retains continuation',async()=>{
    const s=pickerWorld(),p=s.run('readSources(false)');s.calls[0].resolve({assets:[],unavailable_assets:[{id:'large',code:'asset_read_limit',error:'Too <large>'}],next_cursor:'next'});assert.equal(await p,true);s.run('renderSources()');
    assert.doesNotMatch(s.q('#uxSourceAssets').innerHTML,/No matching saved images|Import an image|data-ux-pull/);assert.match(s.q('#uxSourceAssets').innerHTML,/details unavailable/i);
    assert.match(s.q('#uxSourcePaging').innerHTML,/0 available of 1 observed saved images loaded/);assert.match(s.q('#uxSourcePaging').innerHTML,/large/);assert.match(s.q('#uxSourcePaging').innerHTML,/Too &lt;large&gt;/);assert.match(s.q('#uxSourcePaging').innerHTML,/More saved images/);assert.equal(s.calls.length,1);
  });
  await test('A mixed source-picker page offers only complete rows and keeps refused details separate',async()=>{
    const s=pickerWorld(),p=s.run('readSources(false)');s.calls[0].resolve({assets:[asset('safe',{review:'selected'})],unavailable_assets:[{id:'unsafe',code:'asset_read_limit',error:'Too large'}]});assert.equal(await p,true);s.run('renderSources()');
    assert.match(s.q('#uxSourceAssets').innerHTML,/data-ux-pull="safe"/);assert.match(s.q('#uxSourceAssets').innerHTML,/>Kept</);assert.doesNotMatch(s.q('#uxSourceAssets').innerHTML,/data-ux-pull="unsafe"/);assert.match(s.q('#uxSourcePaging').innerHTML,/1 available of 2 observed saved images loaded/);
  });
  await test('Explicit picker continuation retains unavailable evidence and a new search replaces it',async()=>{
    const s=pickerWorld();let p=s.run('readSources(false)');s.calls[0].resolve({assets:[asset('safe')],unavailable_assets:[{id:'old',code:'asset_read_limit',error:'Old reason'}],next_cursor:'next'});await p;
    p=s.run('readSources(true)');assert.match(s.calls[1].url,/cursor=next/);s.calls[1].resolve({assets:[],unavailable_assets:[{id:'new',code:'asset_read_limit',error:'New reason'}]});await p;s.run('renderSources()');assert.match(s.q('#uxSourcePaging').innerHTML,/1 available of 3 observed saved images loaded/);assert.match(s.q('#uxSourcePaging').innerHTML,/Old reason/);assert.match(s.q('#uxSourcePaging').innerHTML,/New reason/);
    s.q('#uxSourceSearch').value='fresh';p=s.run('readSources(false)');assert.doesNotMatch(s.calls[2].url,/cursor=/);s.calls[2].resolve({assets:[asset('fresh')],unavailable_assets:[]});await p;s.run('renderSources()');assert.doesNotMatch(s.q('#uxSourcePaging').innerHTML,/Old reason|New reason/);assert.doesNotMatch(s.q('#uxSourceAssets').innerHTML,/data-ux-pull="safe"/);assert.match(s.q('#uxSourceAssets').innerHTML,/data-ux-pull="fresh"/);
  });
  console.log('Library off-page contracts: '+passed+' passed, '+failed+' failed');if(failed)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
