const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const storage=()=>{const values=new Map();return{getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)};};
function harness(){
  const listeners={},events=[],requests=[];
  const ctx={console,URL,Headers,Proxy,Promise,sessionStorage:storage(),localStorage:storage(),
    location:{href:'http://127.0.0.1:8191/'},CustomEvent:class{constructor(type,o){this.type=type;this.detail=o.detail;}},
    document:{querySelector:()=>null,querySelectorAll:()=>[],addEventListener:(k,fn)=>(listeners[k]??=[]).push(fn),dispatchEvent:e=>{events.push(e);for(const fn of listeners[e.type]||[])fn(e);}},
    fetch:async(path,options)=>{requests.push({path,options});return{ok:true,status:200,json:async()=>({value:'reply'})};}};
  ctx.window=ctx;ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('app/static/privacy.js','utf8'),ctx);
  return{ctx,p:ctx.StudioPrivacy,requests,events};
}
(async()=>{
  const {p,ctx,requests}=harness();assert.equal(p.creation(),'regular');assert.equal(p.scope(),'regular');
  p.setSession(true);assert.equal(p.creation(),'private');assert.equal(p.scope(),'private');
  p.setScope('all');assert.equal(p.creation(),'private');assert.equal(p.scope(),'all');
  p.setCreation('regular');assert.equal(p.creation(),'regular');p.submitted();assert.equal(p.creation(),'private');
  assert.equal(p.storageKey('draft','private'),'draft.private');assert.equal(p.storageKey('draft','regular'),'draft');
  await p.fetch('/api/jobs',{method:'POST',headers:{'X-Studio-Privacy':'regular','X-Studio-Creation-Privacy':'private'}});
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Privacy'),'regular');assert.equal(requests.at(-1).options.headers.get('X-Studio-Creation-Privacy'),'private');
  const response=await p.fetch('/api/jobs');p.setScope('regular');await assert.rejects(response.json(),/view changed/i);
  const mutation=await p.fetch('/api/jobs',{method:'POST'});p.setScope('private');assert.equal((await mutation.json()).value,'reply');
  assert.equal(p.mediaUrl('/api/image/run/0',{privacy:'private'}),'/api/image/run/0?privacy=private');
  assert.equal(p.mediaUrl('/api/assets/a/thumb?w=256',{privacy:'private'}),'/api/assets/a/thumb?w=256&privacy=private');
  assert.equal(p.allows({privacy:'private'},'regular'),false);assert.equal(p.allows({privacy:'bad'},'all'),false);
  await p.fetch('https://example.test/image');assert.equal(requests.at(-1).options,undefined);
  const captured=p.capture();p.setCreation('regular');p.submitted(captured);assert.equal(p.creation(),'regular');
  assert.throws(()=>p.setScope('bad'));assert.throws(()=>p.setCreation('all'));
  p.setScope('all');
  await p.fetch('/api/assets/a/file?privacy=private');
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Privacy'),'private','an explicit media query supplies the missing read header');
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Creation-Privacy'),'regular','the read query cannot change creation classification');
  await p.fetch('/api/assets/a/file?privacy=private',{headers:{'X-Studio-Privacy':'private'}});
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Privacy'),'private');
  for(const [path,headers] of [
    ['/api/assets/a/file?privacy=private',{'X-Studio-Privacy':'regular'}],
    ['/api/assets/a/file?privacy=private&privacy=private',{}],
    ['/api/assets/a/file?privacy=private&%70rivacy=all',{}],
    ['/api/assets/a/file?privacy=',{}],
    ['/api/assets/a/file?privacy=PRIVATE',{}],
    ['/api/jobs',{'X-Studio-Privacy':'all, private'}],
    ['/api/jobs',{'X-Studio-Creation-Privacy':'all'}],
  ]){const count=requests.length;await assert.rejects(p.fetch(path,{headers}));assert.equal(requests.length,count,'invalid scope must be refused before transport');}
  const queriedMutation=await p.fetch('/api/assets/reference?privacy=regular',{method:'POST',headers:{'X-Studio-Creation-Privacy':'private'}});
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Privacy'),'regular');
  assert.equal(requests.at(-1).options.headers.get('X-Studio-Creation-Privacy'),'private');
  p.setScope('private');assert.equal((await queriedMutation.json()).value,'reply','a mutation keeps its acknowledgment after a scope change');
  const upload=await p.fetch('/api/uploads/private.png?privacy=private');p.setScope('regular');
  await assert.rejects(upload.json(),/view changed/i,'uploaded media has the same stale-read boundary as asset media');
  vm.runInContext(fs.readFileSync('app/static/studio-core.js','utf8'),ctx);
  const draft={version:1,updatedAt:1,recipe:{preset:'demo',privacy:'private',controls:{positive:'private draft canary'},references:[]}};
  assert.equal(ctx.StudioUX.normalizeDraft(draft).recipe.privacy,'private');
  assert.equal(ctx.StudioUX.normalizeDraft({...draft,recipe:{...draft.recipe,privacy:'all'}}),null);
  assert.equal(ctx.StudioUX.normalizeDraft({...draft,recipe:{...draft.recipe,privacy:undefined}}).recipe.privacy,undefined);
  console.log('Privacy browser contracts passed: session/draft/scope, explicit headers, late reads, mutation acknowledgment, media and invalid values.');
})().catch(error=>{console.error(error);process.exitCode=1;});
