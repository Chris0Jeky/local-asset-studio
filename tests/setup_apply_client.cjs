const test=require('node:test'),assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const {Controller}=require('../app/static/setup-apply.js');
const clone=x=>JSON.parse(JSON.stringify(x)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function fixture(){
  const before={version:1,updatedAt:0,templateHash:null,pendingInputs:[],recipe:{preset:'before',controls:{positive:'mine'},batch:1,references:[],parent_assets:[],parent_by_input:{}}};
  const next=clone(before);next.recipe.preset='after';next.recipe.controls.positive='reviewed';
  let current=clone(before),stamp=0,serial=0;const writes=[],reads=[],messages=[],store=new Map(),receipts={};
  const storage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)};
  const draft={capture:()=>clone(current),stamp:()=>String(stamp),busy:()=>false,adopt:(d,s)=>{assert.equal(String(stamp),s);current=clone(d);stamp++;}};
  const record=d=>{const core={draft:clone(d),inputs:[],runtime:{backend_id:'primary'}};const text=JSON.stringify(core);return {...core,record_json:text,record_sha256:createHash('sha256').update(text).digest('hex')};};
  async function request(path,q){
    if(!q){reads.push(path);if(path.endsWith('setup-drafts'))return {workspace_id:'a'.repeat(32),drafts:[]};if(path.includes('/requests/'))return clone(receipts[path.split('/').at(-1)]);return {...record(next),workspace_id:'a'.repeat(32),draft_id:'saved',revision:2,head_revision:2,generation_submitted:false,inputs_available:true};}
    writes.push(clone(q));const revision=q.action==='create'?1:q.expected_revision+1;
    const r={...record(q.action==='apply'?next:q.action==='restore'?before:q.draft),workspace_id:q.workspace_id,draft_id:'saved',revision,head_revision:revision,request_id:q.request_id,action:q.action,status:'committed',generation_submitted:false,previous_revision:q.expected_revision};
    receipts[q.request_id]=clone(r);return r;
  }
  const opts={request,storage,draft,emit:x=>messages.push(x),uuid:()=>`req-${++serial}`,validate:async(r,q)=>{assert.equal(r.generation_submitted,false);if(q)assert.equal(r.request_id,q.request_id);return r;}};
  return {before,next,opts,writes,reads,messages,receipts,store,change:()=>{stamp++;current.recipe.controls.positive='later';},current:()=>current,
          report:{before,proposal_json:'exact reviewed report',proposal_sha256:'b'.repeat(64),intent:{preset_id:'after'}},clone};
}
test('explicit apply checkpoints then applies and adopts; undo restores a new revision',async()=>{
  const f=fixture(),c=new Controller(f.opts);await c.apply(f.report,()=>true);
  assert.deepEqual(f.writes.map(x=>x.action),['create','apply']);assert.deepEqual(f.current(),f.next);
  assert.equal(c.state.revision,2);await c.undo();assert.deepEqual(f.current(),f.before);assert.equal(c.state.revision,3);
});
test('local change while checkpoint awaits prevents every apply/copy request',async()=>{
  const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='create')f.change();return r;};
  const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.deepEqual(f.writes.map(x=>x.action),['create']);assert.equal(f.current().recipe.controls.positive,'later');
});
test('local change after saved application keeps current editor and allows explicit recovery',async()=>{
  const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='apply')f.change();return r;};
  const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.equal(c.state.revision,2);assert.equal(f.current().recipe.controls.positive,'later');assert.equal(c.state.pending,null);
});
test('response loss persists the original command and recovery is one GET without adoption',async()=>{
  const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='apply')throw Error('lost reply');return r;};
  let c=new Controller(f.opts);await c.apply(f.report,()=>true);const id=c.state.pending.request_id;assert.equal(f.writes.length,2);assert.deepEqual(f.current(),f.before);
  c=new Controller({...f.opts,request});await c.recover();assert.equal(c.state.pending,null);assert.equal(c.state.revision,2);assert.equal(f.writes.length,2);assert.equal(f.reads.at(-1).split('/').at(-1),id);assert.deepEqual(f.current(),f.before);
});
test('storage failure stops before any mutating request',async()=>{
  const f=fixture();f.opts.storage.setItem=()=>{throw Error('quota');};const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.equal(f.writes.length,0);assert.deepEqual(f.current(),f.before);
});
test('a second tab cannot replace this tab journal while it sends a command',async()=>{
  const f=fixture(),c=new Controller(f.opts);f.opts.storage.setItem(c.key,'other-tab');await c.apply(f.report,()=>true);assert.equal(f.writes.length,0);assert.equal(f.opts.storage.getItem(c.key),'other-tab');
});
test('failed staging stays visible without adopting or automatically retrying',async()=>{
  const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>q?.action==='apply'?{request_id:q.request_id,workspace_id:q.workspace_id,draft_id:q.draft_id,action:'apply',status:'failed',generation_submitted:false,staged:[{file:'retained.png'}],message:'second copy failed'}:request(p,q);
  const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.deepEqual(f.current(),f.before);assert.equal(c.state.revision,1);assert.equal(c.state.last.status,'failed');
});
test('a changed or closed review does not start application after checkpoint',async()=>{
  const f=fixture(),request=f.opts.request;let open=true;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q)open=false;return r;};
  const c=new Controller(f.opts);await c.apply(f.report,()=>open);assert.equal(f.writes.length,1);assert.deepEqual(f.current(),f.before);
});
test('undo refuses to overwrite edits made after the last adoption',async()=>{
  const f=fixture(),c=new Controller(f.opts);await c.apply(f.report,()=>true);f.change();await c.undo();assert.equal(f.writes.length,2);assert.equal(f.current().recipe.controls.positive,'later');
});
test('pending local File inputs refuse application before checkpoint',async()=>{
  const f=fixture();f.before.pendingInputs=['reference'];f.opts.draft.capture=()=>clone(f.before);const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.equal(f.writes.length,0);
});
test('a busy origin lock refuses commands before touching the recovery journal',async()=>{
  const f=fixture();f.opts.withLock=async()=>{throw Error('another tab owns setup operation');};
  const c=new Controller(f.opts);await c.apply(f.report,()=>true);assert.equal(f.writes.length,0);assert.equal(f.store.size,0);
});
test('deferred script loading waits for the workbench owner instead of losing the apply UI',()=>{
  const {mount}=require('../app/static/setup-apply.js'),events=[];
  mount({document:{querySelector:()=>null,addEventListener:(...args)=>events.push(args)}});
  assert.equal(events.length,1);assert.equal(events[0][0],'studio:setup-draft-ready');assert.equal(events[0][2].once,true);
});
test('browser verifier refuses a committed receipt with an unexpected revision',async()=>{
  const {verify}=require('../app/static/setup-apply.js'),f=fixture(),q={action:'create',workspace_id:'a'.repeat(32),request_id:'wire',draft:f.before};
  const r=await f.opts.request('/api/workflow-studio/setup-drafts',q);r.revision=r.head_revision=2;
  const receipt={request_id:r.request_id,workspace_id:r.workspace_id,action:r.action,draft_id:r.draft_id,status:r.status,revision:r.revision};
  r.receipt_json=JSON.stringify(receipt);const hash=async text=>createHash('sha256').update(text).digest('hex');r.receipt_sha256=await hash(r.receipt_json);
  await assert.rejects(verify(r,q,hash),/revision/i);
});
