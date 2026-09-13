// Actual Workspace script, inert DOM and controllable I/O. Browser layout is a separate test.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/workspace.js'), 'utf8');
const recoverySource = fs.readFileSync(path.join(__dirname, '../app/static/asset-recovery.js'), 'utf8');
const deferred = () => {let resolve, reject; const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function setup(options={}) {
  const elements=new Map(), handlers=[], writes=[], reads=[], timers=new Map();let timerId=0, approve=false, requests=0;
  const storage=options.storage||{values:new Map(),getItem(key){if(this.failRead)throw Error('storage disabled');return this.values.get(key)??null;},setItem(key,value){if(this.failWrite)throw Error('quota');this.values.set(key,value);},removeItem(key){if(this.failClear)throw Error('storage disabled');this.values.delete(key);}};
  const el=id=>{
    if(!elements.has(id))elements.set(id,{value:'',open:false,disabled:false,innerHTML:'',textContent:'',dataset:{},events:{},classList:{toggle(){}},
      addEventListener(name,fn){(this.events[name]??=[]).push(fn);},
      emit(name,event={}){for(const fn of this.events[name]||[])fn(event);},
      showModal(){this.open=true;},close(){this.open=false;this.emit('close');},focus(){},scrollIntoView(){}});
    return elements.get(id);
  };
  const context=vm.createContext({console,AbortController,Set,JSON,Date,crypto:require("node:crypto").webcrypto,sessionStorage:storage,
    $:el,esc:value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),window:{confirm(){requests++;return approve;}},
    document:{querySelectorAll:()=>[],addEventListener(name,fn,capture){handlers.push({name,fn,capture});}},
    setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},
    api:async(url,options={})=>{
      const d=deferred(),record={...d,url,options};
      (options.method==='POST'?writes:reads).push(record);
      options.signal?.addEventListener('abort',()=>{const error=new Error('aborted');error.name='AbortError';d.reject(error);});
      return d.promise;
    },message(){},renderJobs(){},jobsSignature:'',jobs:[]
  });
  const run=code=>vm.runInContext(code,context);
  run(recoverySource);run(source);
  run(`refreshAssets=async()=>{};assetState.assets=['a','b'].map(id=>({id,title:id,notes:'original',tags:['tag'],review:'unreviewed',favorite:false,media_type:'video',preset_id:'wan22-i2v',job_id:'job-'+id,metadata_revision:0,source:{},lineage:[],bytes:1}));`);
  if(options.autoOpen!==false)run("openAsset('a')");
  const payload=index=>JSON.parse(writes[index].options.body);
  const receipt=index=>{const p=payload(index);return {status:'applied',request_id:p.request_id,updated:p.ids,action:p.action,revisions:Object.fromEntries(p.ids.map(id=>[id,p.expected_revisions[id]+1])),applied:p.action==='edit'?Object.fromEntries(['title','notes','tags','favorite','review'].filter(k=>k in p).map(k=>[k,p[k]])):['trash','restore'].includes(p.action)?{trashed_at:p.action==='trash'?123:null}:{collection_id:p.collection_id}};};
  return {el,run,writes,reads,timers,storage,payload,metadata:index=>{const {request_id,expected_revisions,...fields}=payload(index);return fields;},receipt,accept:index=>writes[index].resolve(receipt(index)),confirmations:()=>requests,approve(value){approve=value;},
    async diagnostic(job='job-a') {const target={closest:selector=>selector==='[data-i2v-diagnostic]'?{dataset:{i2vDiagnostic:job}}:null};for(const h of handlers)if(h.name==='click'&&!h.capture)await h.fn({target});},
    capturedHandoff(){let prevented=false;for(const h of handlers)if(h.name==='click'&&h.capture)h.fn({target:{closest:()=>true},preventDefault(){prevented=true;},stopImmediatePropagation(){}});return prevented;}
  };
}
let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS',name);}
async function main(){
  await test('Favorite is independent from all edited fields',async()=>{
    const s=setup();s.el('#assetTitle').value='draft';s.el('#assetTags').value='x, y';s.el('#assetNotes').value='notes';s.el('#assetReview').value='selected';
    const p=s.el('#assetFavorite').onclick();assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['a'],action:'edit',favorite:true});
    s.accept(0);await p;assert.equal(s.el('#assetTitle').value,'draft');assert.equal(s.el('#assetTags').value,'x, y');assert.equal(s.el('#assetNotes').value,'notes');assert.equal(s.el('#assetReview').value,'selected');assert.equal(s.run('assetDetailDirty()'),true);
  });
  await test('Close, Escape and lineage require discard consent; same asset is inert',async()=>{
    const s=setup();s.el('#assetNotes').value='draft';s.el('#closeAssetDialog').onclick();assert.equal(s.el('#assetDialog').open,true);
    let prevented=false;s.el('#assetDialog').emit('cancel',{preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(s.el('#assetDialog').open,true);
    s.run("openAsset('b')");assert.equal(s.run('activeAsset.id'),'a');assert.equal(s.confirmations(),3);
    s.run("openAsset('a')");assert.equal(s.el('#assetNotes').value,'draft');assert.equal(s.confirmations(),3);
    s.approve(true);s.run("openAsset('b')");assert.equal(s.run('activeAsset.id'),'b');assert.equal(s.el('#assetNotes').value,'original');
  });
  await test('Missing target never clears active identity',async()=>{const s=setup();s.el('#assetNotes').value='draft';s.run("openAsset('absent')");assert.equal(s.run('activeAsset.id'),'a');assert.equal(s.el('#assetNotes').value,'draft');});
  await test('Save snapshots once; newer edits remain dirty; handoff/close waits',async()=>{
    const s=setup();s.el('#assetNotes').value='snapshot';const p=s.el('#saveAssetDetails').onclick();s.el('#assetNotes').value='newer';await s.el('#saveAssetDetails').onclick();
    assert.equal(s.writes.length,1);assert.equal(s.el('#saveAssetDetails').disabled,true);assert.equal(s.capturedHandoff(),true);s.el('#closeAssetDialog').onclick();assert.equal(s.el('#assetDialog').open,true);
    s.accept(0);await p;assert.equal(s.el('#assetDialog').open,true);assert.equal(s.el('#assetNotes').value,'newer');assert.equal(s.run('activeAsset.notes'),'snapshot');assert.equal(s.run('assetDetailDirty()'),true);assert.match(s.el('#assetDetailStatus').textContent,/unsaved/);assert.equal(s.el('#saveAssetDetails').disabled,false);
  });
  await test('Clean save normalizes metadata and keeps review semantics',async()=>{
    const s=setup();s.el('#assetTitle').value='  title  ';s.el('#assetTags').value=' a , a,b ';s.el('#assetNotes').value='  notes  ';s.el('#assetReview').value='needs_work';
    const p=s.el('#saveAssetDetails').onclick();assert.deepEqual(s.metadata(0),{ids:['a'],action:'edit',title:'title',notes:'notes',tags:['a','b'],review:'needs_work'});s.accept(0);await p;
    assert.equal(s.run('assetDetailDirty()'),false);assert.equal(s.el('#assetDialog').open,true);assert.equal(s.run('activeAsset.review'),'needs_work');s.el('#closeAssetDialog').onclick();assert.equal(s.confirmations(),0);
  });
  await test('Success does not wait for a hung library read',async()=>{const s=setup();s.el('#assetNotes').value='Snapshot';s.run('refreshAssets=()=>new Promise(()=>{})');const p=s.el('#saveAssetDetails').onclick();s.accept(0);await p;assert.equal(s.el('#saveAssetDetails').disabled,false);assert.equal(s.timers.size,0);});
  await test('Timeout aborts actual signal, releases controls and never retries',async()=>{
    const s=setup();s.el('#assetNotes').value='keep';const p=s.el('#saveAssetDetails').onclick();[...s.timers.values()][0]();await p;
    assert.equal(s.writes[0].options.signal.aborted,true);assert.equal(s.el('#assetNotes').value,'keep');assert.equal(s.el('#saveAssetDetails').disabled,false);assert.match(s.el('#assetDetailStatus').textContent,/not confirmed.*timed out/);assert.equal(s.writes.length,1);assert.equal(s.timers.size,0);
  });
  await test('Write failure stays inside dialog; explicit retry can succeed',async()=>{
    const s=setup();s.el('#assetNotes').value='keep';let p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('disk full'));await p;assert.match(s.el('#assetDetailStatus').textContent,/disk full/);assert.equal(s.run('assetDetailDirty()'),true);
    p=s.el('#saveAssetDetails').onclick();s.accept(1);await p;assert.equal(s.run('assetDetailDirty()'),false);assert.equal(s.writes.length,2);
  });
  await test('Trash cancellation writes nothing and confirmed trash stays recoverable',async()=>{
    const s=setup();s.el('#assetNotes').value='draft';await s.el('#assetTrash').onclick();assert.equal(s.writes.length,0);assert.equal(s.el('#assetDialog').open,true);
    s.approve(true);const p=s.el('#assetTrash').onclick();assert.deepEqual(s.metadata(0),{ids:['a'],action:'trash'});assert.equal(s.el('#assetNotes').disabled,true);s.accept(0);await p;assert.equal(s.el('#assetDialog').open,false);assert.equal(s.el('#assetNotes').disabled,false);
  });
  for(const failure of [false,true])for(const navigation of ['other','aba','reopen'])await test(`Diagnostic ${failure?'failure':'success'} is scoped across ${navigation}`,async()=>{
    const s=setup();const p=s.diagnostic();assert.equal(s.reads.length,1);
    if(navigation==='reopen'){s.el('#assetDialog').close();s.run("openAsset('a')");}else{s.run("openAsset('b')");if(navigation==='aba')s.run("openAsset('a')");}
    const html=s.el('#assetDiagnostic').innerHTML;
    failure?s.reads[0].reject(Error('old failure')):s.reads[0].resolve({source:{filename:'old'}});await p;assert.equal(s.el('#assetDiagnostic').innerHTML,html);assert.equal(s.writes.length,0);
  });
  await test('Current diagnostic errors retain retry; stale job controls are inert',async()=>{
    const s=setup();await s.diagnostic('wrong-job');assert.equal(s.reads.length,0);const p=s.diagnostic();s.reads[0].reject(Error('missing video'));await p;assert.match(s.el('#assetDiagnostic').innerHTML,/job-a/);assert.match(s.el('#assetDiagnostic').innerHTML,/missing video/);
  });
  await test('A later diagnostic request wins within the same asset session',async()=>{
    const s=setup();const a=s.diagnostic(),b=s.diagnostic();s.reads[1].resolve({source:{filename:'new result'}});await b;const html=s.el('#assetDiagnostic').innerHTML;s.reads[0].resolve({source:{filename:'old result'}});await a;assert.equal(s.el('#assetDiagnostic').innerHTML,html);assert.match(html,/new result/);
  });
  console.log(`Asset detail contracts passed: ${passed}`);
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
module.exports={setup};
