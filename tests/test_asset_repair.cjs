'use strict';
// #1837: the repaired-version request carries the picture's own privacy and parent, and refuses before any request for a picture it cannot repair.
const test=require('node:test'),assert=require('node:assert/strict'),R=require('../app/static/asset-repair.js');
const workspace='c'.repeat(32),hash='d'.repeat(64);
const png=(over={})=>({name:'fixed.png',type:'image/png',size:1200,...over});
const asset=(over={})=>({id:'a'.repeat(32),workspace_id:workspace,sha256:hash,media_type:'image',privacy:'regular',trashed_at:null,...over});
const idle=()=>({busy:false,pending:false,conflict:false,importing:false});

test('payload names the parent, the picture\'s privacy and a percent-encoded plain note',()=>{
  for(const privacy of ['regular','private']){
    const file=png(),{path,options}=R.request(asset({privacy}),file,'  Fixed the  eyes ✓ ',workspace);
    assert.equal(path,'/api/assets/import?workspace_id='+workspace);assert.equal(options.method,'POST');assert.equal(options.body,file);
    assert.deepEqual(options.headers,{'Content-Type':'image/png','X-Filename':'fixed.png','X-Studio-Privacy':privacy,'X-Studio-Creation-Privacy':privacy,
      'X-Parent-Asset':'a'.repeat(32),'X-Editor-Note':encodeURIComponent('Fixed the eyes ✓')});
  }
  const bare=R.request(asset(),png({name:'réparé.png'}),'   ',workspace).options.headers;
  assert.equal('X-Editor-Note' in bare,false);assert.equal(bare['X-Filename'],'repaired.png');
});

test('refusals say why, before any request',async()=>{
  const cases=[[asset({media_type:'video'}),png(),'',idle(),/Only a picture/],[asset({trashed_at:3}),png(),'',idle(),/in the Bin/],
    [asset({privacy:'secret'}),png(),'',idle(),/privacy classification/],[asset(),png({type:'image/jpeg'}),'',idle(),/Choose a PNG/],
    [asset(),png({size:0}),'',idle(),/empty/],[asset(),png({size:21*1024*1024}),'',idle(),/20 MiB/],[asset(),null,'',idle(),/Choose the repaired PNG/],
    [asset(),png(),'x'.repeat(281),idle(),/280 characters/],[asset(),png(),'',{...idle(),busy:true},/save is still pending/],
    [asset(),png(),'',{...idle(),pending:true},/earlier save/],[asset(),png(),'',{...idle(),conflict:true},/earlier save/],[asset(),png(),'',{...idle(),importing:true},/already running/],
    [null,png(),'',idle(),/Open a picture/]];
  for(const [a,file,note,state,message] of cases){
    let calls=0;
    await assert.rejects(R.submit({asset:a,file,note,state:()=>state,workspace,resolve:async()=>a,api:async()=>{calls++;},current:()=>true}),message);
    assert.equal(calls,0);
  }
});

test('success needs the recorded link and reports whether the editor still shows the picture',async()=>{
  const parent=asset(),child='b'.repeat(32);let seen;
  const api=async(path,options)=>{seen={path,options};return {asset:{id:child,lineage:[parent.id]}};};
  const args={asset:parent,file:png(),note:'',state:idle,workspace,resolve:async()=>({...parent}),current:()=>true};
  assert.deepEqual(await R.submit({...args,api}),{id:child,parent:parent.id});
  assert.equal(seen.options.headers['X-Parent-Asset'],parent.id);
  await assert.rejects(R.submit({...args,api:async()=>({asset:{id:child,lineage:[]}})}),/link to this one was not confirmed/);
  await assert.rejects(R.submit({...args,api:async()=>{throw Error('Asset not found');}}),/Asset not found/);
});

for(const [name,change] of [
  ['missing parent',()=>null],['another workspace',a=>({...a,workspace_id:'f'.repeat(32)})],
  ['different bytes',a=>({...a,sha256:'e'.repeat(64)})],['different privacy',a=>({...a,privacy:'private'})],
  ['trashed parent',a=>({...a,trashed_at:1})]
])test('confirmation refuses '+name+' without importing',async()=>{
  const parent=asset();let calls=0;
  await assert.rejects(R.submit({asset:parent,file:png(),note:'',workspace,state:idle,current:()=>true,
    resolve:async()=>change(parent),api:async()=>{calls++;return {asset:{id:'child',lineage:[parent.id]}};}}));
  assert.equal(calls,0);
});

test('a save started during parent confirmation refuses before importing',async()=>{
  const parent=asset(),state=idle();let release,calls=0;
  const pending=R.submit({asset:parent,file:png(),note:'',workspace,state:()=>state,current:()=>true,
    resolve:()=>new Promise(done=>release=done),api:async()=>{calls++;return {asset:{id:'child',lineage:[parent.id]}};}});
  state.busy=true;release(parent);
  await assert.rejects(pending,/save is still pending/);assert.equal(calls,0);
});

function pageFixture(){
  const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
  const elements=new Map(),posts=[],notices=[];
  for(const id of ['assetRepair','assetDialog','assetRepairOpen','assetRepairFile','assetRepairNote','assetRepairImport','assetRepairStatus','assetDetailMedia'])
    elements.set('#'+id,{open:id==='assetDialog',hidden:true,value:'',dataset:{},files:[png()],addEventListener(){},classList:{toggle(){}}});
  const context={document:{querySelector:selector=>elements.get(selector)||null},
    MutationObserver:class{observe(){}},activeAsset:asset(),assetState:{workspace_id:workspace},
    assetDetailEpoch:1,assetWorkspaceEpoch:1,assetPrivacyEpoch:1,assetReceiptEpoch:1,
    assetDetailBusy:false,assetDetailPending:null,assetDetailConflict:null,scope:'regular',latest:asset(),
    assetPrivacyScope:()=>context.scope,
    assetDetailContextCurrent:(id,epoch)=>elements.get('#assetDialog').open&&context.activeAsset.id===id&&context.assetDetailEpoch===epoch,
    resolveAssetIDs:()=>new Promise(done=>{context.release=()=>done(true);}),assetRecord:()=>context.latest,
    api:async(url,options)=>{posts.push({url,options});return {asset:{id:'child',lineage:['a'.repeat(32)]}};},
    refreshAssets:async()=>{},message:text=>notices.push(text)};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/asset-repair.js'),'utf8'),context);
  return {context,elements,posts,notices,press:()=>elements.get('#assetRepairImport').onclick()};
}

for(const [name,change] of [
  ['workspace A-B-A',c=>{c.assetState.workspace_id='e'.repeat(32);c.assetWorkspaceEpoch++;c.assetState.workspace_id=workspace;c.assetWorkspaceEpoch++;}],
  ['privacy A-B-A',c=>{c.scope='private';c.assetPrivacyEpoch++;c.scope='regular';c.assetPrivacyEpoch++;}],
  ['detail navigation',c=>c.assetDetailEpoch++],['closed dialog',(_,els)=>els.get('#assetDialog').open=false],
  ['source hash replacement',c=>c.activeAsset.sha256='f'.repeat(64)]
])test('actual repair page sends no import after held confirmation and '+name,async()=>{
  const f=pageFixture(),pending=f.press();
  assert.equal(f.posts.length,0,'Import must wait for the current parent observation');
  assert.equal(typeof f.context.release,'function','The real page must request parent confirmation');
  change(f.context,f.elements);f.context.release();await pending;
  assert.equal(f.posts.length,0);assert.equal(f.elements.get('#assetRepairOpen').hidden,true);
});

test('actual repair page imports under its captured workspace after confirmation',async()=>{
  const f=pageFixture(),pending=f.press();assert.equal(f.posts.length,0);
  f.context.release();await pending;
  assert.equal(f.posts.length,1);assert.equal(f.posts[0].url,'/api/assets/import?workspace_id='+workspace);
  assert.equal(f.elements.get('#assetRepairOpen').dataset.id,'child');
});

test('completion after the library refresh re-checks the picture and never speaks in an unrelated dialog',async()=>{
  const done={id:'b'.repeat(32),parent:'a'.repeat(32)};
  for(const [name,moves] of [['stays',false],['navigates during the refresh',true]]){
    let viewing=true;const shown=[],notices=[];
    await R.settle(done,{refresh:async()=>{if(moves)viewing=false;},current:()=>viewing,show:(id,text)=>shown.push([id,text]),notice:text=>notices.push(text)});
    if(moves){assert.deepEqual(shown,[],name);assert.equal(notices.length,1);assert.doesNotMatch(notices[0],/of this one/);}
    else{assert.equal(shown.length,1,name);assert.equal(shown[0][0],done.id);assert.deepEqual(notices,[]);}
  }
  let viewing=true;const shown=[];
  await R.settle(done,{refresh:async()=>{throw Error('offline');},current:()=>viewing,show:(...a)=>shown.push(a),notice:()=>assert.fail('a failed refresh is not a navigation')});
  assert.equal(shown.length,1);
});
