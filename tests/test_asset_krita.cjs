'use strict';
// #1860: Edit in Krita / Bring back from Krita. Requests carry the picture's own privacy, refusals say why before any request, an unchanged
// save imports nothing, and an import is believed only with its recorded link.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),R=require('../app/static/asset-repair.js');
const asset=(over={})=>({id:'a'.repeat(32),media_type:'image',privacy:'regular',trashed_at:null,...over});
const ready={available:true,reason:''},idle=()=>({running:false});

test('requests name the picture, its privacy and the session, and never a path',()=>{
  for(const privacy of ['regular','private']){
    const start=R.kritaRequest(asset({privacy}),'start'),back=R.kritaRequest(asset({privacy}),'back','20261030-101010-abcdef12');
    const headers={'Content-Type':'application/json','X-Studio-Privacy':privacy,'X-Studio-Creation-Privacy':privacy};
    assert.equal(start.path,'/api/assets/'+'a'.repeat(32)+'/edit-in-krita');assert.deepEqual(start.options,{method:'POST',headers,body:'{}'});
    assert.equal(back.path,start.path+'/bring-back');assert.deepEqual(back.options,{method:'POST',headers,body:'{"session":"20261030-101010-abcdef12"}'});
  }
  assert.equal(R.kritaRequest(asset(),'back').options.body,'{}');
});

test('refusals say why',()=>{
  const cases=[[null,ready,idle(),/Open a picture/],[asset({media_type:'video'}),ready,idle(),/Only a picture/],[asset({trashed_at:3}),ready,idle(),/in the Bin/],
    [asset({privacy:'secret'}),ready,idle(),/privacy classification/],[asset(),{available:false,reason:'Krita is not configured. Set "krita".'},idle(),/not configured/],
    [asset(),null,idle(),/not known yet/],[asset(),ready,{running:true},/already running/]];
  for(const [a,krita,state,message] of cases)assert.match(R.kritaBlocked(a,krita,state),message);
  assert.equal(R.kritaBlocked(asset(),ready,idle()),'');assert.equal(R.kritaBlocked(asset({privacy:'private'}),ready,idle()),'');
  assert.equal(R.kritaBlocked(asset(),null,idle(),false),'','bringing a save back does not need Krita to be launchable');
});

test('start makes no request when blocked and confirms the session it is given',async()=>{
  let calls=0;const api=async()=>{calls++;return {id:'20261030-101010-abcdef12',asset_id:asset().id};};
  for(const [a,krita,state,message] of [[asset({trashed_at:1}),ready,idle(),/Bin/],[asset(),{available:false,reason:'Krita is not configured.'},idle(),/not configured/],[asset(),ready,{running:true},/already running/]])
    await assert.rejects(R.kritaStart({asset:a,krita,state:()=>state,api}),message);
  assert.equal(calls,0);
  assert.equal((await R.kritaStart({asset:asset(),krita:ready,state:idle,api})).id,'20261030-101010-abcdef12');
  await assert.rejects(R.kritaStart({asset:asset(),krita:ready,state:idle,api:async()=>({id:'x',asset_id:'b'.repeat(32)})}),/not confirmed/);
  await assert.rejects(R.kritaStart({asset:asset(),krita:ready,state:idle,api:async()=>{throw Error('Krita is not configured.');}}),/not configured/);
});

test('bring back: unchanged imports nothing, a repeat is not imported again, an import needs its link',async()=>{
  const parent=asset(),child='b'.repeat(32),run=reply=>R.kritaBringBack({asset:parent,session:'s',state:idle,api:async()=>reply});
  const unchanged=await run({status:'unchanged'});assert.equal(unchanged.status,'unchanged');assert.match(unchanged.text,/Nothing was imported/);assert.equal(unchanged.id,undefined);
  const repeat=await run({status:'already_imported',asset_id:child});assert.deepEqual([repeat.status,repeat.id],['already_imported',child]);
  assert.deepEqual(await run({status:'imported',asset:{id:child,lineage:[parent.id]}}),{status:'imported',id:child,parent:parent.id});
  for(const bad of [{status:'imported',asset:{id:child,lineage:[]}},{status:'imported',asset:{id:child}},{status:'imported'},{status:'what'},null])
    await assert.rejects(run(bad),/not recognised/);
  let calls=0;
  await assert.rejects(R.kritaBringBack({asset:parent,session:'s',state:()=>({running:true}),api:async()=>{calls++;}}),/already running/);
  await assert.rejects(R.kritaBringBack({asset:asset({trashed_at:1}),session:'s',state:idle,api:async()=>{calls++;}}),/Bin/);
  assert.equal(calls,0);
  await assert.rejects(R.kritaBringBack({asset:parent,state:idle,api:async()=>{throw Error('Open this picture in Krita first');}}),/Open this picture/);
});

test('an answer for a picture the owner has left goes to the page notice, not the dialog',()=>{
  const done={status:'unchanged',text:'Nothing changed.'};
  for(const [name,here] of [['same picture',true],['moved on',false]]){
    const shown=[],notices=[];R.kritaReport(done,{current:()=>here,show:(...a)=>shown.push(a),notice:t=>notices.push(t)});
    assert.deepEqual([shown.length,notices.length],here?[1,0]:[0,1],name);
  }
});

test('every control the script drives exists in the page',()=>{
  const script=fs.readFileSync(path.join(__dirname,'../app/static/asset-repair.js'),'utf8'),html=fs.readFileSync(path.join(__dirname,'../app/static/index.html'),'utf8');
  const ids=[...new Set([...script.matchAll(/#(assetKrita\w*)/g)].map(m=>m[1]))];
  assert.deepEqual(ids.sort(),['assetKrita','assetKritaBack','assetKritaOpen','assetKritaStatus','assetKritaView']);
  for(const id of ids)assert.ok(html.includes('id="'+id+'"'),id);
  assert.match(html,/<button id="assetKritaOpen"[^>]*>Edit in Krita</);
});
