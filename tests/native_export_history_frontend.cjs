'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/workspace.js'),'utf8');
const code=source.slice(source.indexOf('let assetExportHistory=null;'),source.indexOf('function openAsset('));
function setup(){
  const nodes=new Map(),requests=[];
  const $=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',open:false,hidden:false,disabled:false,addEventListener(name,fn){this[name]=fn;}});return nodes.get(id);};
  const ctx=vm.createContext({$,Date,encodeURIComponent,esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    assetState:{workspace_id:'w'},assetDetailEpoch:1,assetWorkspaceEpoch:1,assetPrivacyEpoch:1,
    api:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))});
  const run=s=>vm.runInContext(s,ctx);
  run("let activeAsset={id:'a',media_type:'image',privacy:'regular'};function assetDetailContextCurrent(id,epoch){return $('#assetDialog').open&&activeAsset.id===id&&assetDetailEpoch===epoch;}");
  run(code);$('#assetDialog').open=true;run('resetAssetExports(activeAsset)');
  const result=(plans=[],extra={})=>({workspace_id:'w',asset_id:'a',plans,next_offset:null,unavailable:false,...extra});
  const plan=(extra={})=>({id:'a'.repeat(32),name:'Export <literal>',status:'planned',created_at:1,available:true,source_sha256:'b'.repeat(64),plan_sha256:'c'.repeat(64),artifacts:[],...extra});
  return {$,run,ctx,requests,result,plan};
}
test('explicit expansion reads once and keeps prepared distinct from recorded files',async()=>{
  const s=setup();assert.equal(s.requests.length,0);s.$('#assetNotes').value='Keep this unsaved note';
  const pending=s.run('loadAssetExports()');await s.run('loadAssetExports()');assert.equal(s.requests.length,1);
  assert.match(s.requests[0].url,/\/api\/assets\/a\/native-exports\?workspace_id=w&offset=0/);
  s.requests[0].resolve(s.result([s.plan(),s.plan({id:'d'.repeat(32),status:'failed',historical_source:true,artifacts:[{name:'export.zip',available:true,url:'/recorded?sha256=abc'}]})]));await pending;
  const html=s.$('#assetExportsList').innerHTML;
  assert.match(html,/Prepared/);assert.match(html,/No produced files recorded/);assert.match(html,/Failed/);
  assert.match(html,/Uses an earlier saved version/);assert.match(html,/Export &lt;literal>/);assert.doesNotMatch(html,/<literal>/);
  assert.match(html,/href="\/\?plan=a{32}#production" target="_blank" rel="noopener"/);
  assert.match(html,/href="\/recorded\?sha256=abc" download/);assert.equal(s.$('#assetNotes').value,'Keep this unsaved note');
  assert.ok(s.requests.every(r=>!r.options.method||r.options.method==='GET'));
});
test('late results cannot enter another asset, closed dialog, Workspace or privacy scope',async()=>{
  for(const change of ["activeAsset={id:'b',media_type:'image'};assetDetailEpoch++;resetAssetExports(activeAsset)","$('#assetDialog').open=false;resetAssetExports()",'assetState.workspace_id="other";resetAssetExports()', 'assetPrivacyEpoch++;resetAssetExports()']){
    const s=setup(),pending=s.run('loadAssetExports()');s.run(change);s.requests[0].resolve(s.result([s.plan({name:'late private canary'})]));await pending;
    assert.doesNotMatch(s.$('#assetExportsList').innerHTML,/canary/);
  }
});
test('private pictures do not request history and reopening resets the previous result',async()=>{
  const s=setup();s.run("resetAssetExports({id:'private',media_type:'image',privacy:'private'})");
  await s.run('loadAssetExports()');assert.equal(s.requests.length,0);assert.equal(s.$('#assetNativeExports').hidden,true);
  s.run('resetAssetExports(activeAsset)');const p=s.run('loadAssetExports()');s.requests[0].resolve(s.result([s.plan()]));await p;
  s.run('resetAssetExports(activeAsset)');assert.equal(s.$('#assetExportsList').innerHTML,'');assert.equal(s.$('#assetNativeExports').open,false);
});
test('failure and foreign response preserve existing entries and allow explicit refresh',async()=>{
  const s=setup();let p=s.run('loadAssetExports()');s.requests[0].resolve(s.result([s.plan()]));await p;
  const before=s.$('#assetExportsList').innerHTML;
  p=s.run('loadAssetExports(true)');s.requests[1].resolve(s.result([s.plan({name:'foreign'})],{workspace_id:'other'}));await p;
  assert.equal(s.$('#assetExportsList').innerHTML,before);assert.match(s.$('#assetExportsStatus').textContent,/different picture or Workspace/);
  p=s.run('loadAssetExports(true)');s.requests[2].reject(Error('offline'));await p;
  assert.equal(s.$('#assetExportsList').innerHTML,before);assert.equal(s.$('#assetExportsRefresh').disabled,false);
});
test('more is explicit, refresh replaces the page, and unavailable evidence is not called absent output',async()=>{
  const s=setup();let p=s.run('loadAssetExports()');s.requests[0].resolve(s.result([s.plan()],{next_offset:'20'}));await p;
  assert.equal(s.requests.length,1);assert.equal(s.$('#assetExportsMore').hidden,false);
  p=s.run('loadAssetExports()');assert.match(s.requests[1].url,/offset=20$/);s.requests[1].resolve(s.result([s.plan({available:false})]));await p;
  assert.match(s.$('#assetExportsList').innerHTML,/Recorded files cannot be checked/);
  p=s.run('loadAssetExports(true)');s.requests[2].resolve(s.result());await p;
  assert.equal(s.$('#assetExportsList').innerHTML,'');assert.equal(s.$('#assetExportsMore').hidden,true);
});
