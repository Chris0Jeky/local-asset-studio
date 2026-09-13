// Exercise the merged journal/editor, not the superseded review-recovery adapter.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const {PREFIX}=require('../app/static/asset-recovery.js');
const A='a'.repeat(32), B='b'.repeat(32);
const draft=(s,text)=>{s.el('#assetNotes').value=text;s.el('#assetNotes').emit('input');};
const retained=s=>JSON.parse(s.storage.getItem(PREFIX+'detail'));
const init=(opts={})=>{const s=setup({...opts,autoOpen:false});s.run(`assetState.workspace_id='${opts.scope||A}';for(const a of assetState.assets)a.workspace_id=assetState.workspace_id;`);if(opts.autoOpen!==false)s.run("openAsset('a')");return s;};
let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS',name);}
(async()=>{
  await test('New commands and retained drafts carry the opened Workspace identity',async()=>{
    const s=init();draft(s,'for A');const p=s.el('#saveAssetDetails').onclick();
    assert.equal(s.payload(0).workspace_id,A);assert.equal(retained(s).workspace_id,A);assert.equal(retained(s).version,2);
    s.accept(0);await p;
  });
  await test('Background library replacement cannot retarget an open draft',async()=>{
    const s=init();draft(s,'A draft');s.run(`assetState.workspace_id='${B}'`);
    await s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,0);assert.equal(retained(s).workspace_id,A);assert.equal(s.el('#assetNotes').value,'A draft');
  });
  await test('Reload in another Workspace preserves exact bytes but cannot open or retry',async()=>{
    const s=init();draft(s,'A only');const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const raw=s.storage.getItem(PREFIX+'detail'),n=init({storage:s.storage,scope:B});
    assert.equal(n.el('#assetDialog').open,false);assert.equal(n.writes.length,0);assert.equal(n.reads.length,0);assert.equal(s.storage.getItem(PREFIX+'detail'),raw);
    assert.match(n.el('#assetCommandRecovery').innerHTML,/different workspace/i);
  });
  await test('Legacy unscoped recovery remains inspectable without inferred identity',async()=>{
    const s=init();draft(s,'legacy draft');const old=retained(s);old.version=1;delete old.workspace_id;delete old.metadata.workspace_id;s.storage.setItem(PREFIX+'detail',JSON.stringify(old));
    const n=init({storage:s.storage});assert.equal(n.el('#assetDialog').open,false);assert.equal(n.writes.length,0);assert.match(n.el('#assetCommandRecovery').innerHTML,/legacy draft/);
    assert.equal(JSON.parse(s.storage.getItem(PREFIX+'detail')).version,1);
  });
  await test('Historical receipt preserves newer saved values in a conflict, not a false clean form',async()=>{
    const s=init();draft(s,'sent N');const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const n=init({storage:s.storage});const observed=n.run('checkAssetSave()');
    assert.match(n.reads[0].url,new RegExp('workspace_id='+A));
    const current={...JSON.parse(n.run('JSON.stringify(activeAsset)')),metadata_revision:2,notes:'saved N+1',workspace_id:A};
    n.reads[0].resolve({...s.receipt(0),workspace_id:A,current:[current]});await observed;
    assert.equal(n.run('assetDetailPending'),null);assert.equal(n.run('!!assetDetailConflict'),true);
    assert.equal(n.el('#assetNotes').value,'sent N');assert.match(n.el('#assetDetailConflict').innerHTML,/saved N\+1/);
    assert.doesNotMatch(n.el('#assetDetailConflict').innerHTML,/Nothing in your save was applied/);
    draft(n,'newer unsaved typing');n.run('resolveAssetConflict(true)');assert.equal(n.writes.length,0);assert.equal(n.run('activeAsset.metadata_revision'),2);assert.equal(n.el('#assetNotes').value,'newer unsaved typing');
  });
  await test('Cross-workspace receipt response cannot clear pending recovery',async()=>{
    const s=init();draft(s,'keep');const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const observing=s.run('checkAssetSave()');s.reads[0].resolve({...s.receipt(0),workspace_id:B});await observing;
    assert.ok(s.run('assetDetailPending'));assert.equal(retained(s).operation.command.workspace_id,A);assert.equal(s.el('#assetNotes').value,'keep');
  });
  await test('Rejected wrong-Workspace POST retains its identity for return to correct store',async()=>{
    const s=init();draft(s,'keep');const p=s.el('#saveAssetDetails').onclick();
    s.writes[0].reject(Object.assign(Error('different Workspace'),{status:409,data:{code:'asset_workspace_conflict',workspace_id:B}}));await p;
    assert.ok(s.run('assetDetailPending'));assert.equal(retained(s).operation.body,s.writes[0].options.body);
  });
  await test('Library retry and status reads cannot cross Workspace after refresh',async()=>{
    const s=init();const p=s.run("mutateAssets({ids:['a','b'],action:'edit',favorite:true})");s.writes[0].reject(Error('lost'));await assert.rejects(p);
    s.run(`assetState.workspace_id='${B}'`);await assert.rejects(s.run('performLibraryCommand(assetLibraryPending,true)'));
    await assert.rejects(s.run('performLibraryCommand(assetLibraryPending)'));assert.equal(s.reads.length,0);assert.equal(s.writes.length,1);
  });
  await test('Malformed scoped journal never authorizes a differently scoped command',async()=>{
    const s=init();draft(s,'keep');const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const record=retained(s);record.workspace_id=B;s.storage.setItem(PREFIX+'detail',JSON.stringify(record));
    const n=init({storage:s.storage});await n.el('#saveAssetDetails').onclick();assert.equal(n.writes.length,0);assert.equal(JSON.parse(s.storage.getItem(PREFIX+'detail')).workspace_id,B);
  });
  await test('Legacy library selection stays unbound at page load',async()=>{
    const s=init();s.run("assetSelection=new Set(['a','b'])");const p=s.run("mutateAssets({ids:['a','b'],action:'edit',favorite:true})");s.writes[0].reject(Error('lost'));await assert.rejects(p);
    const record=JSON.parse(s.storage.getItem(PREFIX+'library'));record.version=1;delete record.workspace_id;delete record.operation.command.workspace_id;record.operation.body=JSON.stringify(record.operation.command);s.storage.setItem(PREFIX+'library',JSON.stringify(record));
    const n=setup({storage:s.storage,autoOpen:false});assert.equal(n.run('assetSelection.size'),0);assert.equal(n.writes.length,0);
  });
  await test('Library status checks retain the original selection, not a later page selection',async()=>{
    const s=init();s.run("assetSelection=new Set(['a','b'])");const p=s.run("mutateAssets({ids:['a','b'],action:'edit',favorite:true})");s.writes[0].reject(Error('lost'));await assert.rejects(p);
    s.run('assetSelection.clear()');const observing=s.run('performLibraryCommand(assetLibraryPending,true)');s.reads[0].resolve({status:'unknown',workspace_id:A,request_id:s.payload(0).request_id});await assert.rejects(observing);
    assert.deepEqual(JSON.parse(s.storage.getItem(PREFIX+'library')).selection,['a','b']);
  });
  console.log('Asset Workspace scope contracts passed:',passed);
})().catch(error=>{console.error(error);process.exitCode=1;});
