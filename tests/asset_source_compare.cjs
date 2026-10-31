'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),F=require('../app/static/asset-family.js');
const workspace='a'.repeat(32),hash='b'.repeat(64),sourceHash='c'.repeat(64);
const asset=(id,sha,extra={})=>({id,sha256:sha,workspace_id:workspace,media_type:'image',privacy:'regular',trashed_at:null,title:id,url:'/api/assets/'+id+'/file',...extra});
const report=()=>({version:1,asset_id:'repair',workspace_id:workspace,nodes:['source','repair'].map(id=>({id,state:'active',title:id,operation:null,seed:null,strength:null})),edges:[{parent:'source',child:'repair'}],gaps:[],truncated:false,children:null,children_truncated:false,children_scanned:0,observation_only:true,generation_submitted:false,media_bytes_verified:false});
function fixture(){
  const state={workspace,stamp:'detail-1'},records=new Map([['repair',asset('repair',hash)],['source',asset('source',sourceHash)]]),reads=[];
  const options={context:()=>({...state}),asset:()=>records.get('repair'),lookup:id=>records.get(id),resolve:async ids=>{reads.push(ids);return true;}};
  return {state,records,reads,options};
}
test('explicit recorded source choice observes both images without replacing the current asset',async()=>{
  const f=fixture(),before=structuredClone(f.records.get('repair'));
  const comparison=F.createComparison(f.options);
  assert.deepEqual(f.reads,[]);
  const pair=await comparison.choose(report(),'source');
  assert.deepEqual(f.reads,[['repair','source']]);
  assert.equal(pair.child.id,'repair');assert.equal(pair.source.id,'source');
  assert.equal(pair.child.sha256,hash);assert.equal(pair.source.sha256,sourceHash);assert.equal(pair.current(),true);
  assert.deepEqual(f.records.get('repair'),before);
  comparison.cancel();assert.equal(pair.current(),false);
});
test('no source is selected automatically, including a family with several parents',async()=>{
  const f=fixture(),r=report();r.nodes.push({...r.nodes[0],id:'other'});r.edges.push({parent:'other',child:'repair'});
  f.records.set('other',asset('other','d'.repeat(64)));
  const comparison=F.createComparison(f.options);
  await assert.rejects(comparison.choose(r),/Choose a recorded direct source/);assert.deepEqual(f.reads,[]);
  const pair=await comparison.choose(r,'other');assert.equal(pair.source.id,'other');
  assert.deepEqual(f.reads,[['repair','other']]);
});
for(const [name,change] of [
  ['wrong Workspace',r=>r.workspace_id='d'.repeat(32)],['wrong child',r=>r.asset_id='other'],
  ['unrecorded source',r=>r.edges=[]],['transitive ancestor',r=>r.edges=[{parent:'source',child:'intermediate'}]],
  ['bounded incomplete family',r=>r.truncated=true],['family gap',r=>r.gaps=[{id:'earlier',reason:'depth'}]],
  ['duplicate parent',r=>r.edges.push({...r.edges[0]})],['self parent',r=>r.edges=[{parent:'repair',child:'repair'}]],
  ['missing source',r=>r.nodes[0].state='missing'],['trashed source',r=>r.nodes[0].state='trashed'],
  ['false byte-verification claim',r=>r.media_bytes_verified=true]
])test(name+' refuses before resolving images',async()=>{
  const f=fixture(),r=report();change(r);await assert.rejects(F.createComparison(f.options).choose(r,'source'));assert.deepEqual(f.reads,[]);
});
for(const [name,change] of [
  ['missing',f=>f.records.delete('source')],['trashed',f=>f.records.get('source').trashed_at=0],
  ['video',f=>f.records.get('source').media_type='video'],['private source of regular child',f=>f.records.get('source').privacy='private'],
  ['foreign Workspace',f=>f.records.get('source').workspace_id='d'.repeat(32)],
  ['missing hash',f=>delete f.records.get('source').sha256],['untrusted media URL',f=>f.records.get('source').url='https://foreign.example/image.png'],
  ['wrong asset media URL',f=>f.records.get('source').url='/api/assets/other/file']
])test('resolved '+name+' is unavailable rather than a comparison pair',async()=>{
  const f=fixture();change(f);await assert.rejects(F.createComparison(f.options).choose(report(),'source'));
});
test('private pictures use their existing scoped media and cannot mix with regular sources',async()=>{
  const f=fixture();for(const a of f.records.values()){a.privacy='private';a.url+='?privacy=private';}
  const pair=await F.createComparison(f.options).choose(report(),'source');assert.match(pair.source.url,/privacy=private$/);
  f.records.get('source').privacy='regular';await assert.rejects(F.createComparison(f.options).choose(report(),'source'),/same privacy/);
});
for(const boundary of ['Workspace A-B-A','privacy A-B-A','detail changed','closed','child hash changed'])test('held resolution is discarded after '+boundary,async()=>{
  const f=fixture();let release;f.options.resolve=()=>new Promise(resolve=>release=resolve);
  const comparison=F.createComparison(f.options),pending=comparison.choose(report(),'source');
  if(boundary==='closed')comparison.cancel();else if(boundary==='child hash changed')f.records.get('repair').sha256='e'.repeat(64);
  else f.state.stamp=boundary+' epoch 3';
  release(true);assert.equal(await pending,null);
});
test('the newest deliberate source choice wins when earlier resolution arrives late',async()=>{
  const f=fixture(),r=report();r.nodes.push({...r.nodes[0],id:'other'});r.edges.push({parent:'other',child:'repair'});
  f.records.set('other',asset('other','d'.repeat(64)));const releases=[];
  f.options.resolve=()=>new Promise(resolve=>releases.push(resolve));
  const comparison=F.createComparison(f.options),old=comparison.choose(r,'source'),latest=comparison.choose(r,'other');
  releases[1](true);const pair=await latest;assert.equal(pair.source.id,'other');releases[0](true);assert.equal(await old,null);assert.equal(pair.current(),true);
});
test('a late read failure after navigation neither returns a pair nor reports into the new context',async()=>{
  const f=fixture();let reject;f.options.resolve=()=>new Promise((_,r)=>reject=r);
  const pending=F.createComparison(f.options).choose(report(),'source');f.state.stamp='another detail';reject(Error('offline'));
  assert.equal(await pending,null);
});
