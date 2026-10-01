const test=require('node:test');
const assert=require('node:assert/strict');
const A=require('../app/static/asset-family-adapter.js');
const F=require('../app/static/asset-family.js');
const scope='a'.repeat(32),hash='b'.repeat(64);
function fixture(){
  let state={workspace:scope,workspaceEpoch:1,assetId:'one',assetEpoch:1,fields:{notes:''},dirty:false,
    pending:false,conflict:false,metadataBusy:false,specialized:false};
  let stamp='draft-1',busy=false,backend='primary',adopted=[],finished=[],picked=[];
  const owner={stamp:()=>stamp,busy:()=>busy,adopt:(...args)=>adopted.push(args)};
  const result={asset_id:'one',workspace_id:scope,recipe:{preset_id:'p',controls:{seed:1},parent_assets:['parent'],references:[]},
    controls:{positive:'resolved words',seed:'18446744073709551615'}};
  const options={owner,state:()=>state,presets:()=>[{id:'p',seed:['1','seed'],positive:['2','text']}],backend:()=>backend,
    asset:id=>({id,media_type:'image',trashed_at:null}),finish:(...args)=>finished.push(args),picker:async(...args)=>picked.push(args)};
  return {options,adapter:A.create(options),result,state,owner,adopted,finished,picked,
    stamp:value=>stamp=value,busy:value=>busy=value,backend:value=>backend=value};
}
test('recall delegates one complete draft to the existing owner exactly once',()=>{
  const f=fixture(),before=JSON.stringify(f.result);
  f.adapter.apply(f.result,{template_sha256:hash},'words');
  assert.equal(f.adopted.length,1);const [draft,stamp,backend]=f.adopted[0];
  assert.equal(stamp,'draft-1');assert.equal(backend,'primary');
  assert.equal(draft.recipe.batch,1);assert.equal(draft.recipe.preset,'p');
  assert.equal(draft.recipe.controls.seed,'18446744073709551615');
  assert.deepEqual(draft.recipe.parent_assets,['parent']);assert.deepEqual(draft.pendingInputs,[]);
  assert.equal(draft.templateHash,hash);assert.equal(f.finished.length,1);assert.equal(JSON.stringify(f.result),before);
});
for(const key of ['dirty','pending','conflict','metadataBusy','specialized'])test('refuse active '+key+' before adoption',()=>{
  const f=fixture();f.state[key]=true;
  assert.throws(()=>f.adapter.apply(f.result,{template_sha256:hash},'new'),/kept/);
  assert.equal(f.adopted.length,0);assert.equal(f.finished.length,0);
});
test('refuse busy Create before adoption',()=>{
  const f=fixture();f.busy(true);
  assert.throws(()=>f.adapter.apply(f.result,{template_sha256:hash},'words'),/finish/);assert.equal(f.adopted.length,0);
});
for(const change of [{workspace_id:'c'.repeat(32)},{asset_id:'other'}])test('reject changed recall target '+Object.keys(change)[0],()=>{
  const f=fixture();assert.throws(()=>f.adapter.apply({...f.result,...change},{template_sha256:hash},'words'),/changed/);
  assert.equal(f.adopted.length,0);
});
test('backend and missing recipe refusals have no mutation',()=>{
  const f=fixture();f.backend('qwen21');assert.throws(()=>f.adapter.apply(f.result,{template_sha256:hash},'words'),/backend/);
  f.backend('primary');f.result.recipe.preset_id='missing';assert.throws(()=>f.adapter.apply(f.result,{template_sha256:hash},'words'),/unavailable/);
  assert.equal(f.adopted.length,0);
});
test('owner failure leaves dialog and focus untouched',()=>{
  const f=fixture();f.owner.adopt=()=>{throw Error('original owner refusal');};
  assert.throws(()=>f.adapter.apply(f.result,{template_sha256:hash},'words'),/owner refusal/);assert.equal(f.finished.length,0);
});
test('context includes workbench, metadata, selection and Workspace epochs',()=>{
  const f=fixture();let previous=f.adapter.context().stamp;
  for(const mutate of [()=>f.stamp('draft-2'),()=>f.state.assetEpoch++,()=>f.state.workspaceEpoch++,
    ()=>f.state.fields.notes='typed later',()=>f.state.pending=true,()=>f.state.specialized=true]){
    mutate();const next=f.adapter.context().stamp;assert.notEqual(next,previous);previous=next;
  }
});
test('reference opens only the existing picker and carries a fresh-work predicate',async()=>{
  const f=fixture();await f.adapter.reference('one');
  assert.equal(f.picked.length,1);assert.equal(f.picked[0][0].id,'one');assert.equal(f.picked[0][1](),true);
  f.stamp('draft-2');assert.equal(f.picked[0][1](),false);assert.equal(f.adopted.length,0);
});
for(const key of ['dirty','pending','conflict','metadataBusy'])test('reference preserves '+key+' asset editor',async()=>{
  const f=fixture();f.state[key]=true;await assert.rejects(f.adapter.reference('one'),/kept/);assert.equal(f.picked.length,0);
});
test('reference rejects missing, trashed and non-image assets',async()=>{
  for(const value of [null,{id:'one',media_type:'video',trashed_at:null},{id:'one',media_type:'image',trashed_at:0}]){
    const f=fixture();f.options.asset=()=>value;await assert.rejects(A.create(f.options).reference('one'),/active image/);
    assert.equal(f.picked.length,0);
  }
});
test('strict family envelope rejects coercible identities and false evidence flags',()=>{
  const original={version:1,asset_id:'one',workspace_id:scope,nodes:[{id:'one',state:'active',title:'One',operation:null,seed:null,strength:null}],
    edges:[],gaps:[],children:null,truncated:false,children_truncated:false,children_scanned:0,
    observation_only:true,generation_submitted:false,media_bytes_verified:false};
  F.validate(original,'one',scope);
  for(const change of [{nodes:[{...original.nodes[0],id:1}]},{edges:[{parent:1,child:'one'}]},
    {observation_only:false},{generation_submitted:true},{media_bytes_verified:true},{children_truncated:'false'},{children_scanned:5001}]){
    assert.throws(()=>F.validate({...original,...change},'one',scope),/family/);
  }
});
test('invalid request identity must not issue a recall read',async()=>{
  let reads=0;const recall=F.createRecall({context:()=>({workspace:scope,stamp:'a'}),read:async()=>{reads++;return{};}});
  await assert.rejects(recall.prepare(1,'words'),/identity/);assert.equal(reads,0);
});
