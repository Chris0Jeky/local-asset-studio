'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/workspace.js'),'utf8');
const code=source.slice(source.indexOf('let assetAcceptance=null;'),source.indexOf('function openAsset('));
const SHA='a'.repeat(64);
function setup(){
  const nodes=new Map(),requests=[];
  const $=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',open:false,hidden:false,disabled:false,title:'',addEventListener(name,fn){this[name]=fn;}});return nodes.get(id);};
  const ctx=vm.createContext({$,Date,encodeURIComponent,JSON,Object,esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    assetState:{workspace_id:'w'},assetDetailEpoch:1,assetWorkspaceEpoch:1,assetPrivacyEpoch:1,
    api:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))});
  const run=s=>vm.runInContext(s,ctx);
  run("let activeAsset={id:'a',media_type:'image',privacy:'regular',sha256:'"+SHA+"'};function assetDetailContextCurrent(id,epoch){return $('#assetDialog').open&&activeAsset.id===id&&assetDetailEpoch===epoch;}");
  run(code);$('#assetDialog').open=true;run('resetAssetAcceptance(activeAsset)');
  const row=(extra={})=>({id:'r1',asset_id:'a',sha256:SHA,use:'Game sprite',note:'',reviewer:'local-user',accepted_at:1,withdrawn_at:null,...extra});
  const result=(acceptances=[],extra={})=>({workspace_id:'w',asset_id:'a',sha256:SHA,acceptances,...extra});
  return {$,run,requests,row,result};
}
test('a read that lands after a write cannot replace the saved rows with its older snapshot',async()=>{
  const s=setup(),read=s.run('loadAssetAcceptance()');
  s.$('#assetAcceptUse').value='Game sprite';s.$('#assetAcceptGo').onclick();
  assert.equal(s.requests.length,2);assert.equal(s.requests[1].options.method,'POST');
  s.requests[1].resolve(s.result([s.row()]));await new Promise(r=>setImmediate(r));
  s.requests[0].resolve(s.result([]));await read;   // the older, empty snapshot arrives last
  assert.match(s.$('#assetAcceptList').innerHTML,/Game sprite/);assert.equal(s.run('assetAcceptance.rows.length'),1);
});
test('the POST names the displayed bytes and Workspace and says so honestly when nothing changed',async()=>{
  const s=setup();s.$('#assetAcceptUse').value='Game sprite';s.$('#assetAcceptNote').value='a changed note';s.$('#assetAcceptGo').onclick();
  const body=JSON.parse(s.requests[0].options.body);
  assert.deepEqual([body.reviewer,body.sha256,body.workspace_id,body.use,body.action],['local-user',SHA,'w','Game sprite','accept']);
  s.requests[0].resolve(s.result([s.row()],{unchanged:true}));await new Promise(r=>setImmediate(r));
  assert.match(s.$('#assetAcceptStatus').textContent,/Already accepted for this use/);assert.doesNotMatch(s.$('#assetAcceptStatus').textContent,/Recorded/);
});
test('a response for other bytes is refused and the control stays usable',async()=>{
  const s=setup();s.$('#assetAcceptUse').value='Game sprite';s.$('#assetAcceptGo').onclick();
  s.requests[0].resolve(s.result([s.row()],{sha256:'b'.repeat(64)}));await new Promise(r=>setImmediate(r));
  assert.match(s.$('#assetAcceptStatus').textContent,/different picture or Workspace/);assert.equal(s.$('#assetAcceptList').innerHTML,'');
});
test('a failed send does not leave the list empty when it dropped the first read',async()=>{
  const s=setup(),read=s.run('loadAssetAcceptance()');
  s.$('#assetAcceptUse').value='Game sprite';s.$('#assetAcceptGo').onclick();
  s.requests[1].reject(Error('offline'));await new Promise(r=>setImmediate(r));
  s.requests[0].resolve(s.result([s.row()]));await read;   // dropped: it is older than the failed write
  assert.match(s.$('#assetAcceptStatus').textContent,/Not saved/);assert.equal(s.requests.length,3);assert.equal(s.requests[2].options?.method,undefined);
  s.requests[2].resolve(s.result([s.row()]));await new Promise(r=>setImmediate(r));
  assert.match(s.$('#assetAcceptList').innerHTML,/Game sprite/);
});
