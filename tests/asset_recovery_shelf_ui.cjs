/* Execute shipped shelf controls; storage replies are controlled, no browser/HTTP claim. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const test=require('node:test');
const vm=require('node:vm');

function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function harness(overrides={}){
  const nodes=new Map(),downloads=[],confirmations=[],http=[];
  class Element{
    constructor(){this.hidden=false;this.disabled=false;this.checked=false;this.open=false;this.isConnected=true;this.textContent='';this.listeners={};this.parentElement={after(){}};this.classList={toggle(){}};}
    set id(value){this._id=value;nodes.set(value,this);}get id(){return this._id;}
    set innerHTML(value){this._html=value;for(const match of value.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)){const child=new Element();child.id=match[1];child.hidden=/\bhidden\b/.test(match[0]);}}
    get innerHTML(){return this._html||'';}
    setAttribute(){}before(){}after(){}append(){}remove(){}
    addEventListener(name,fn){this.listeners[name]=fn;}
    focus(){document.activeElement=this;}
    showModal(){this.open=true;}close(){this.open=false;this.listeners.close?.();}
  }
  const document={activeElement:null,body:new Element(),getElementById:id=>nodes.get(id),createElement:()=>new Element()};
  for(const id of ['assetCommandRecovery','saveAssetDetails','assetDialog']){const n=new Element();n.id=id;}
  let confirms=true;
  const store={list:async()=>[],raw:async()=>null,legacyRaw:async()=>null,export:async()=>'current bundle',acceptLegacy:async()=>{},...overrides};
  const context=vm.createContext({console,setTimeout,clearTimeout,TextDecoder,document,localStorage:{},sessionStorage:{getItem:()=>null},navigator:{locks:{}},
    StudioAssetRecoveryShelf:{create:()=>store,LIMITS:{records:20,total:2*1024*1024}},
    StudioAssetRecoveryShelfSession:{create:()=>({enabled:false})},
    assetRecovery:{},assetState:{workspace_id:'w'},assetDetailBusy:false,assetLibraryBusy:false,
    assetLibraryPending:null,assetRetainedDetail:null,assetRecoveryError:null,
    esc:value=>String(value),renderLibraryRecovery(){},api:(...args)=>{http.push(args);throw Error('Unexpected HTTP');},
    window:{confirm:message=>{confirmations.push(message);return confirms;}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/asset-recovery-shelf-ui.js'),'utf8'),context);
  nodes.get('assetRecoveryShelfDialog').open=true;
  context.download=(text,name)=>downloads.push({text,name});
  vm.runInContext('assetShelfDownload=download',context);
  return {context,document,nodes,store,downloads,confirmations,http,setConfirm:value=>{confirms=value;},refresh:()=>vm.runInContext('assetShelfRefresh()',context)};
}

test('raw evidence waits for exact asynchronous bytes before downloading',async()=>{
  const pending=deferred(),h=harness({raw:()=>pending.promise});
  h.nodes.get('assetShelfRawExport').onclick();await settle();
  assert.deepEqual(h.downloads,[],'an unresolved storage promise must never be exported');
  pending.resolve('  {"version":99,"retained":"<script>literal</script>"}\n');await settle();
  assert.deepEqual(h.downloads,[{text:'  {"version":99,"retained":"<script>literal</script>"}\n',name:'unverified-asset-review-recovery.json'}]);
  assert.deepEqual(h.http,[]);
});

test('raw read failure downloads nothing and keeps the original reason visible',async()=>{
  const h=harness({raw:async()=>{throw Error('Synthetic current-store refusal');}});
  h.nodes.get('assetShelfRawExport').onclick();await settle();
  assert.deepEqual(h.downloads,[]);assert.match(h.nodes.get('assetShelfStatus').textContent,/Synthetic current-store refusal/);
  assert.equal(h.nodes.get('assetShelfEnabled').disabled,false);
});

test('a refused shelf read is unavailable, not a false empty shelf',async()=>{
  const h=harness({list:async()=>{throw Error('Synthetic read refusal');}});await h.refresh();
  assert.doesNotMatch(h.nodes.get('assetShelfRecords').innerHTML,/No recovery records/);
  assert.doesNotMatch(h.nodes.get('assetShelfCount').textContent,/0 of/);
  assert.match(h.nodes.get('assetShelfStatus').textContent,/Synthetic read refusal/);
  assert.equal(h.nodes.get('assetShelfRawExport').hidden,false);
  h.store.list=async()=>[];await h.refresh();
  assert.match(h.nodes.get('assetShelfRecords').innerHTML,/No recovery records/);
  assert.match(h.nodes.get('assetShelfCount').textContent,/0 of 20/);
});

test('legacy quarantine leaves both explicit exports reachable without a write',async()=>{
  const error=Object.assign(Error('Older-version recovery changed; both copies remain.'),{code:'asset_recovery_legacy_changed',review:{token:1}});
  const h=harness({list:async()=>{throw error;},raw:async()=>'current exact bytes',legacyRaw:async()=>' legacy exact bytes\n'});
  await h.refresh();
  assert.equal(h.nodes.get('assetShelfLegacyExport').hidden,false);
  assert.equal(h.nodes.get('assetShelfAcceptLegacy').hidden,false);
  h.nodes.get('assetShelfRawExport').onclick();await settle();
  h.nodes.get('assetShelfLegacyExport').onclick();await settle();
  assert.deepEqual(h.downloads,[{text:'current exact bytes',name:'unverified-asset-review-recovery.json'},{text:' legacy exact bytes\n',name:'older-asset-review-recovery.json'}]);
  assert.deepEqual(h.http,[]);assert.deepEqual(h.confirmations,[]);
});

test('continuing with current shelf requires confirmation and does not import or delete',async()=>{
  let acknowledgements=0;const review={token:1};
  const error=Object.assign(Error('Older-version recovery changed'),{code:'asset_recovery_legacy_changed',review});
  const h=harness({list:async()=>{throw error;},acceptLegacy:async received=>{assert.equal(received,review);acknowledgements++;h.store.list=async()=>[];}});
  await h.refresh();
  h.setConfirm(false);h.nodes.get('assetShelfAcceptLegacy').onclick();await settle();assert.equal(acknowledgements,0);
  h.setConfirm(true);h.nodes.get('assetShelfAcceptLegacy').onclick();await settle();assert.equal(acknowledgements,1);
  assert.match(h.confirmations.at(-1),/older/i);assert.match(h.confirmations.at(-1),/export/i);
  assert.match(h.confirmations.at(-1),/reload/i);assert.match(h.confirmations.at(-1),/merged or deleted/i);
  assert.deepEqual(h.http,[]);assert.deepEqual(h.downloads,[]);
});

test('a pending acknowledgement cannot replace status in a reopened dialog',async()=>{
  for(const reject of [false,true]){
    const pending=deferred(),review={token:1};
    const error=Object.assign(Error('Older-version recovery changed'),{code:'asset_recovery_legacy_changed',review});
    const h=harness({list:async()=>{throw error;},acceptLegacy:()=>pending.promise});await h.refresh();
    h.nodes.get('assetShelfAcceptLegacy').onclick();await settle();
    h.nodes.get('assetRecoveryShelfDialog').close();h.nodes.get('assetRecoveryShelfDialog').open=true;
    h.store.list=async()=>[];await h.refresh();
    h.nodes.get('assetShelfStatus').textContent='Newer dialog status';
    if(reject)pending.reject(Error('Late acknowledgement refusal'));else pending.resolve();await settle();
    assert.equal(h.nodes.get('assetShelfStatus').textContent,'Newer dialog status');
    assert.equal(h.nodes.get('assetShelfAcceptLegacy').hidden,true);
  }
});

test('successful acknowledgement returns its own focus without taking newer focus',async()=>{
  for(const newerFocus of [false,true]){
    const pending=deferred(),review={token:1};
    const error=Object.assign(Error('Older-version recovery changed'),{code:'asset_recovery_legacy_changed',review});
    const h=harness({list:async()=>{throw error;},acceptLegacy:async()=>{h.store.list=()=>pending.promise;}});await h.refresh();
    h.nodes.get('assetShelfAcceptLegacy').focus();h.nodes.get('assetShelfAcceptLegacy').onclick();await settle();
    // Model the browser moving focus from a now-hidden control to the body.
    if(newerFocus)h.nodes.get('assetShelfImport').focus();else h.document.activeElement=h.document.body;
    pending.resolve([]);await settle();
    assert.equal(h.document.activeElement.id,newerFocus?'assetShelfImport':'assetShelfRefresh');
  }
});

test('unrelated corruption never offers a legacy acknowledgement',async()=>{
  const h=harness({list:async()=>{throw Error('Unsupported future shelf state');},legacyRaw:async()=>'older bytes'});await h.refresh();
  assert.equal(h.nodes.get('assetShelfAcceptLegacy').hidden,true);
  assert.equal(h.nodes.get('assetShelfLegacyExport').hidden,false);
});

test('an older refresh cannot reveal acknowledgement or replace a newer successful read',async()=>{
  const held=deferred(),h=harness({list:()=>held.promise});const stale=h.refresh();
  await settle();h.store.list=async()=>[];await h.refresh();
  held.reject(Object.assign(Error('Old quarantine'),{code:'asset_recovery_legacy_changed'}));await stale;
  assert.match(h.nodes.get('assetShelfRecords').innerHTML,/No recovery records/);
  assert.equal(h.nodes.get('assetShelfAcceptLegacy').hidden,true);
  assert.doesNotMatch(h.nodes.get('assetShelfStatus').textContent,/Old quarantine/);
});
