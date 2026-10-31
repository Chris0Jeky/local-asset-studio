'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app/static/continue-card.js'),'utf8');
const A='a'.repeat(32),B='b'.repeat(32),P='c'.repeat(32),S='d'.repeat(32);
function harness(){
  const handlers={},events={},result={textContent:'',innerHTML:''},refresh={disabled:false,addEventListener:(n,f)=>handlers['refresh:'+n]=f};
  const card={open:false,querySelector:s=>s.includes('result')?result:refresh,addEventListener:(n,f)=>handlers[n]=f};
  const privacy={scope:'regular',privacy:'regular',revision:0},calls=[],opens=[],dialog={open:false};
  let read=async()=>data(),draft='original',leave=true;
  const sandbox={document:{querySelector:s=>s==='#makeContinue'?card:dialog,addEventListener:(n,f)=>(events[n]??=[]).push(f),dispatchEvent:e=>(events[e.type]||[]).forEach(f=>f(e))},
    StudioPrivacy:{capture:()=>({...privacy}),allows:(a,s)=>s==='all'||a?.privacy===s},
    assetState:{workspace_id:A},assetWorkspaceEpoch:0,assetDetailEpoch:0,
    api:async(...args)=>{calls.push(args);return read();},refreshAssets:async()=>{},openAsset:async(id,owns)=>{if(owns())opens.push(id);},
    assetDetailCanLeave:()=>leave,assetDetailValues:()=>({draft}),CustomEvent:class{constructor(type,options={}){this.type=type;this.detail=options.detail;}},console};
  vm.runInNewContext(source,sandbox);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  return {card,result,refresh,sandbox,privacy,calls,opens,events,setRead:f=>read=f,setDraft:v=>draft=v,setLeave:v=>leave=v,
    async expand(){card.open=true;handlers.toggle();await settle();},async refreshNow(){handlers['refresh:click']();await settle();},
    click:kind=>{const event={prevented:false,preventDefault(){this.prevented=true;},target:{closest:s=>s===`[data-continue-${kind}]`?{}:null}};return Promise.resolve(handlers.click(event)).then(()=>event);},
    change(type){sandbox.document.dispatchEvent({type,detail:{previous:A}});},settle};
}
function data(){return {workspace_id:A,scope:'regular',kept:{state:'ready',asset:{id:'kept-old',title:'Older kept picture',created_at:1,privacy:'regular'}},native:{state:'ready',scope:'regular',plan:{id:P,name:'Saved export',created_at:2,status:'completed'}},scene:{state:'ready',scope:'regular',plan:{id:S,name:'Saved scene',created_at:3,revision:2,status:'failed',render:{revision:2,status:'failed'},completed_revision:1}}};}
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
test('collapsed card is inert; expansion reads exact scope and presents created/recorded links',async()=>{
  const h=harness();assert.equal(h.calls.length,0);await h.expand();assert.equal(h.calls.length,1);
  assert.equal(h.calls[0][0],'/api/workspace/continue?workspace_id='+A);assert.equal(h.calls[0][1].headers['X-Studio-Privacy'],'regular');
  assert.match(h.result.innerHTML,/Older kept picture/);assert.match(h.result.innerHTML,/Created /);assert.match(h.result.innerHTML,/Recorded state: completed/);
  assert.match(h.result.innerHTML,new RegExp('/\\?plan='+P+'#production'));assert.match(h.result.innerHTML,/target="_blank"/);
  await h.click('asset');assert.deepEqual(h.opens,['kept-old']);assert.ok(h.calls.every(([,o])=>!o.method));
});
test('refresh discards an older pending observation',async()=>{
  const h=harness(),wait=deferred();h.setRead(()=>wait.promise);await h.expand();h.setRead(async()=>{const d=data();d.kept.asset.title='Fresh';return d;});await h.refreshNow();
  wait.resolve(data());await h.settle();assert.match(h.result.innerHTML,/Fresh/);assert.doesNotMatch(h.result.innerHTML,/Older kept/);
});
test('privacy A-B-A invalidates late data and hides previous links',async()=>{
  const h=harness(),wait=deferred();h.setRead(()=>wait.promise);await h.expand();
  h.privacy.scope='private';h.privacy.revision++;h.change('studio:privacy-change');h.privacy.scope='regular';h.privacy.revision++;h.change('studio:privacy-change');
  wait.resolve(data());await h.settle();assert.equal(h.card.open,false);assert.equal(h.result.innerHTML,'');await h.click('asset');assert.equal(h.opens.length,0);
});
test('workspace A-B-A and foreign responses cannot restore links',async()=>{
  const h=harness(),wait=deferred();h.setRead(()=>wait.promise);await h.expand();
  h.sandbox.assetState.workspace_id=B;h.sandbox.assetWorkspaceEpoch++;h.change('studio:workspace-change');
  h.sandbox.assetState.workspace_id=A;h.sandbox.assetWorkspaceEpoch++;h.change('studio:workspace-change');wait.resolve(data());await h.settle();
  assert.equal(h.result.innerHTML,'');h.setRead(async()=>({...data(),workspace_id:B}));await h.expand();assert.match(h.result.textContent,/unavailable/);
});
test('unsafe IDs and escaped labels never become navigation',async()=>{
  const h=harness();h.setRead(async()=>{const d=data();d.kept.asset.id='../escape';d.native.plan.id='javascript:bad';return d;});await h.expand();
  assert.doesNotMatch(h.result.innerHTML,/data-continue-asset|data-continue-plan/);
  h.setRead(async()=>{const d=data();d.kept.asset.title='<img src=x onerror=bad>';return d;});await h.refreshNow();assert.match(h.result.innerHTML,/&lt;img/);
});
test('Private never renders Regular exports and All names the boundary',async()=>{
  const h=harness();h.privacy.scope='private';h.privacy.revision++;h.setRead(async()=>({...data(),scope:'private'}));await h.expand();
  assert.doesNotMatch(h.result.innerHTML,/Saved export|data-continue-plan|Older kept/);assert.match(h.result.innerHTML,/not read in Private/);
  h.privacy.scope='all';h.privacy.revision++;h.setRead(async()=>({...data(),scope:'all'}));await h.refreshNow();assert.match(h.result.innerHTML,/Exports here are Regular-only/);
});
test('partial errors and capped observations never say empty',async()=>{
  const h=harness();h.setRead(async()=>({...data(),kept:{state:'unavailable'},native:{state:'incomplete',scope:'regular'}}));await h.expand();
  assert.match(h.result.innerHTML,/Kept picture unavailable/);assert.match(h.result.innerHTML,/not established/);assert.doesNotMatch(h.result.innerHTML,/No eligible|No kept/);
});
test('dirty draft and late navigation preserve the current editor',async()=>{
  const h=harness();await h.expand();let needs=0;h.events['studio:continue-needs']=[()=>needs++];h.setLeave(false);await h.click('needs');assert.equal(needs,0);
  h.setLeave(true);await h.click('needs');assert.equal(needs,1);
  const wait=deferred();h.sandbox.document.querySelector('#assetDialog').open=true;h.sandbox.refreshAssets=()=>wait.promise;
  const clicked=h.click('asset');h.setDraft('new edits');wait.resolve();await clicked;assert.equal(h.opens.length,0);
});
test('scope changes during a navigation read do not open an asset',async()=>{
  const h=harness();await h.expand();const wait=deferred();h.sandbox.refreshAssets=()=>wait.promise;const clicked=h.click('asset');
  h.privacy.revision++;h.change('studio:privacy-change');wait.resolve();await clicked;assert.equal(h.opens.length,0);
});
test('scene links retain exact identity and distinguish saved and completed revisions',async()=>{
  const h=harness();await h.expand();
  assert.match(h.result.innerHTML,new RegExp('/av.html\\?project='+S));assert.match(h.result.innerHTML,/Saved revision 2/);
  assert.match(h.result.innerHTML,/Latest recorded render: failed · revision 2/);assert.match(h.result.innerHTML,/revision 1 \(older than saved revision 2\)/);
  h.sandbox.document.querySelector('#assetDialog').open=true;h.setDraft('Retained Library notes');h.setLeave(false);
  const click=await h.click('scene');assert.equal(click.prevented,false);assert.deepEqual(h.opens,[]);
  assert.equal(h.sandbox.assetDetailValues().draft,'Retained Library notes');assert.equal(h.sandbox.document.querySelector('#assetDialog').open,true);assert.equal(h.calls.length,1);
  h.privacy.revision++;assert.equal((await h.click('scene')).prevented,true);
});
test('invalid or excluded scene evidence never becomes a destination',async()=>{
  const h=harness();
  for(const change of [d=>d.scene.plan.id='../escape',d=>d.scene.plan.revision=-1,d=>d.scene.plan.completed_revision=3,d=>d.scene.plan.render.revision=3,d=>d.scene.plan.status=[]]){
    h.setRead(async()=>{const d=data();change(d);return d;});await h.expand();assert.doesNotMatch(h.result.innerHTML,/data-continue-scene/);assert.match(h.result.innerHTML,/Saved-scene history unavailable/);
  }
  h.privacy.scope='private';h.privacy.revision++;h.setRead(async()=>({...data(),scope:'private'}));await h.expand();
  assert.doesNotMatch(h.result.innerHTML,/Saved scene|data-continue-scene/);assert.match(h.result.innerHTML,/Scenes are Regular-only/);
  h.privacy.scope='all';h.privacy.revision++;h.setRead(async()=>({...data(),scope:'all',scene:{state:'incomplete',scope:'regular'}}));await h.expand();
  assert.match(h.result.innerHTML,/Latest scene not established/);assert.match(h.result.innerHTML,/Scenes here are Regular-only/);
});
