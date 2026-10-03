'use strict';
// Execute the shipped module and click handler; only DOM/transport/engine seams are inert.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../app/static/looks.js'),'utf8');
const app=fs.readFileSync(require.resolve('../app/static/app.js'),'utf8');
function appFunction(name){const start=app.indexOf('function '+name+'('),end=app.indexOf('\nfunction ',start+10);assert(start>=0);return app.slice(start,end<0?app.length:end);}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function fixture(){
  const listeners={},inputs={},requests=[],statuses=[],option={dataset:{lookOption:'rain'},checked:false};
  const node=id=>inputs[id]||(inputs[id]={value:'',textContent:'',hidden:false,disabled:false,dataset:{},classList:{toggle(){}},
    before(){},addEventListener(type,fn){(this.listeners??={})[type]=fn;},closest:()=>true,
    dispatchEvent(event){this.listeners?.[event.type]?.(event);emit(event.type,this);},
    cloneNode(){return {...this};},checkValidity(){return true;}});
  function emit(type,target=node('#positive')){for(const fn of listeners[type]||[])fn({target,type});}
  ['#createView','#positive','#negative','#batch','#lookSelect','#lookScene','#lookName','#lookOptions','#lookReset','#uxFills'].forEach(node);
  node('#positive').value='default';node('#batch').value='1';
  const look={id:'look-a',name:'Look A',revision:1,usable:true,body:{preset_id:'demo',options:[{id:'rain',default:false,label:'Rain'}]},lineage:[]};
  let reads=0,applied=0,stamp='baseline';const pending=deferred();
  const ctx={console,Event:class{constructor(type){this.type=type;}},esc:String,
    document:{querySelector:node,querySelectorAll:()=>[option],createElement:()=>node('#lookBlock'),addEventListener(type,fn){(listeners[type]??=[]).push(fn);}},
    selected:{id:'demo',defaults:{positive:'default'}},parentAssets:[],
    values:()=>({positive:node('#positive').value,negative:node('#negative').value}),
    StudioSetupDraft:{stamp:()=>JSON.stringify([stamp,ctx.selected.id,ctx.values()])},
    api:async()=>{reads++;return {looks:[look,{...look,id:'look-b',name:'Look B'}]};},
    post:(path,payload)=>{requests.push({path,payload});return pending.promise;},
    selectPreset(id){applied++;ctx.selected={id,defaults:{positive:'default'}};ctx.StudioLooks.clearApplication();emit('studio:recipe');},
    getControl:key=>node(key),confirm:()=>true,message:text=>statuses.push(text),updateReady(){},updateLoraHints(){},scheduleTimeEstimate(){},recipeChanged:()=>emit('studio:recipe'),
    $:node,attachedReferencePayload:()=>[],referenceRecords:[],parentByInput:{},
  };
  ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source,ctx);
  vm.runInContext(appFunction('continuationBlockerItems')+'\n'+appFunction('checkedSetupControls'),ctx);
  await Promise.resolve();await Promise.resolve();
  node('#lookSelect').value='look-a';node('#lookScene').value='a room';emit('change',node('#lookSelect'));
  return {ctx,node,option,requests,statuses,pending,emit,reads:()=>reads,applied:()=>applied,stamp:value=>{stamp=value;},
    start:()=>node('#lookPrepare').onclick(),result:()=>({preset_id:'demo',look:{id:'look-a',name:'Look A'},controls:{positive:'prepared',negative:''}})};
}
let count=0,failed=0;
async function test(name,fn){try{await fn();count++;console.log('PASS '+name);}catch(e){failed++;console.error('FAIL '+name+'\n'+e.stack);}}
(async()=>{
  await test('pending request synchronously holds actual Generate and named-setup admission',async()=>{
    const f=await fixture(),work=f.start();
    assert.match(f.ctx.StudioLooks.applicationBlocker('demo'),/prepar/i);
    assert.equal(f.ctx.continuationBlockerItems()[0].code,'look');
    assert.throws(()=>f.ctx.checkedSetupControls(),/prepar/i);
    assert.match(f.ctx.StudioLooks.applicationBlocker('other-recipe'),/prepar/i);
    f.pending.resolve(f.result());await work;
    assert.equal(f.applied(),1);assert.equal(f.node('#positive').value,'prepared');
    assert.equal(f.ctx.StudioLooks.applicationBlocker('demo'),'');
    assert.equal(f.requests.length,1);assert.equal(f.requests[0].path,'/api/looks/prepare');
  });
  for(const [name,mutate] of [
    ['scene',f=>{f.node('#lookScene').value='changed';f.emit('input',f.node('#lookScene'));}],
    ['selected Look',f=>{f.node('#lookSelect').value='look-b';f.emit('change',f.node('#lookSelect'));}],
    ['optional line',f=>{f.option.checked=true;f.emit('change',f.option);}],
    ['edit then undo',f=>{f.node('#positive').value='new';f.emit('input');f.node('#positive').value='default';f.emit('input');}],
    ['recipe event with identical fields',f=>f.emit('studio:recipe')],
    ['programmatic input change without an event',f=>{f.node('#positive').value='new';}],
    ['source/backend/selection stamp',f=>f.stamp('changed')],
  ])await test('delayed success cannot overwrite changed '+name,async()=>{
    const f=await fixture(),work=f.start();mutate(f);const words=f.node('#positive').value;
    f.pending.resolve(f.result());await work;
    assert.equal(f.applied(),0);assert.equal(f.node('#positive').value,words);
    assert.match(f.node('#lookStatus').textContent,/changed|not applied/i);
    assert(!f.statuses.some(text=>text.includes('press Generate')));
    assert.equal(f.ctx.StudioLooks.applicationBlocker('demo'),'');
  });
  await test('stale 409 does not reload or replace the current Look selection',async()=>{
    const f=await fixture(),work=f.start(),reads=f.reads();f.node('#lookSelect').value='look-b';f.emit('change',f.node('#lookSelect'));
    f.pending.reject(Object.assign(new Error('obsolete conflict'),{status:409}));await work;
    assert.equal(f.reads(),reads);assert.equal(f.node('#lookSelect').value,'look-b');assert.equal(f.applied(),0);
    assert(!f.node('#lookStatus').textContent.includes('obsolete conflict'));
  });
  await test('stable rejection releases the temporary hold but keeps existing recovery',async()=>{
    const f=await fixture();f.ctx.StudioLooks.restoreApplication({version:1,preset_id:'demo',controls:['sampler']},'demo');
    const work=f.start();f.pending.reject(new Error('network unavailable'));await work;
    assert.match(f.node('#lookStatus').textContent,/network unavailable/);
    assert.match(f.ctx.StudioLooks.applicationBlocker('demo'),/sampler/);assert.equal(f.applied(),0);
  });
  await test('a current application exception is not misreported as a stale response',async()=>{
    const f=await fixture(),work=f.start();f.ctx.getControl=()=>{throw new Error('control lookup failed');};
    f.pending.resolve({...f.result(),controls:{steps:4}});await work;
    assert.match(f.node('#lookStatus').textContent,/control lookup failed/);
    assert.equal(f.ctx.StudioLooks.applicationBlocker('demo'),'');
  });
  await test('only the current preparation token may release shared admission',async()=>{
    const f=await fixture(),L=f.ctx.StudioLooks,old=L.beginPreparation(),current=L.beginPreparation();
    assert.equal(L.finishPreparation(old),false);assert.match(L.applicationBlocker('demo'),/prepar/i);
    assert.equal(L.finishPreparation(current),true);assert.equal(L.applicationBlocker('demo'),'');
  });
  console.log(`${count} passed, ${failed} failed; inert transport, no generation endpoint`);if(failed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
