const test=require('node:test'),assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const {Controller,verify}=require('../app/static/setup-apply.js');
const clone=x=>JSON.parse(JSON.stringify(x)),hash=async text=>createHash('sha256').update(text).digest('hex'),WS='a'.repeat(32),ID='history-line';
function fixture(){
  const saved={version:1,updatedAt:0,templateHash:null,pendingInputs:[],recipe:{preset:'fixture',controls:{positive:'old wording',seed:'18446744073709551615'},batch:2,references:[],parent_assets:[],parent_by_input:{}}};
  let current=clone(saved),stamp=0,serial=0,head=3,context={workspace_id:WS,scope:'regular',privacy:'regular',revision:0,epoch:0},open=true;
  current.recipe.controls.positive='my unsaved wording';
  const initial=clone(current),records=new Map(),receipts=new Map(),calls=[],messages=[],storage=new Map();
  function record(draft){const core={draft:clone(draft),inputs:[],runtime:{backend_id:'primary'},graph_sha256:'b'.repeat(64)};const record_json=JSON.stringify(core);return {...core,record_json,record_sha256:createHash('sha256').update(record_json).digest('hex')};}
  records.set(1,record(saved));records.set(2,record({...saved,updatedAt:2}));records.set(3,record({...saved,updatedAt:3}));
  function revision(n){return {...clone(records.get(n)),workspace_id:WS,draft_id:ID,revision:n,head_revision:head,generation_submitted:false};}
  async function request(path,q){
    calls.push({path,q:clone(q||null)});
    if(!q){if(path.includes('/requests/'))return clone(receipts.get(path.split('/').at(-1)));return {...revision(+path.split('/').at(-1)),inputs_available:true};}
    if(q.expected_revision!==head)throw Error('shared revision changed');
    const rec=q.action==='replace'?record(q.draft):clone(records.get(q.revision));records.set(++head,rec);
    const core={request_id:q.request_id,workspace_id:q.workspace_id,draft_id:ID,action:q.action,status:'committed',revision:head};
    const receipt_json=JSON.stringify(core),r={...revision(head),...core,receipt_json,receipt_sha256:await hash(receipt_json)};receipts.set(q.request_id,r);return clone(r);
  }
  const state={version:1,workspace_id:WS,draft_id:ID,revision:3,pending:null};storage.set('studio-shared-setup-v1',JSON.stringify(state));
  const opts={request,storage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},uuid:()=>`request-${++serial}`,validate:(r,q)=>verify(r,q,hash),emit:e=>messages.push(e),context:()=>clone(context),
    draft:{capture:()=>clone(current),stamp:()=>String(stamp),busy:()=>false,adopt(d,s){assert.equal(s,String(stamp));current=clone(d);stamp++;}}};
  const target={workspace_id:WS,draft_id:ID,revision:1,head_revision:3,record_sha256:records.get(1).record_sha256};
  return {opts,target,calls,messages,records,receipts,storage,initial,saved,current:()=>current,head:()=>head,setHead:n=>head=n,context,
    change(){current.recipe.controls.positive='later local edit';stamp++;},close(){open=false;},matches:()=>open,
    review:c=>c.reviewRestore(target,()=>open),writes:()=>calls.filter(c=>c.q),setCurrent:d=>{current=d;stamp++;}};
}
test('review is GET-only; explicit restore checkpoints the complete local draft then appends the exact old record',async()=>{
  const f=fixture(),c=new Controller(f.opts),original=clone([...f.records]);const r=await f.review(c);
  assert.equal(f.writes().length,0);assert.deepEqual(f.current(),f.initial);assert.equal(c.state.revision,3);
  await c.restoreHistory(r);
  assert.deepEqual(f.writes().map(x=>[x.q.action,x.q.expected_revision]),[['replace',3],['restore',4]]);
  assert.deepEqual(f.records.get(4).draft,f.initial);assert.deepEqual(f.records.get(5),f.records.get(1));assert.deepEqual([...f.records].slice(0,3),original);
  assert.deepEqual(f.current(),f.saved);assert.equal(c.state.revision,5);assert.equal(c.state.pending,null);assert.deepEqual(c.state.backup,f.initial);
});
test('cancelled review performs no command',async()=>{const f=fixture(),c=new Controller(f.opts),r=await f.review(c);f.close();await c.restoreHistory(r);assert.equal(f.writes().length,0);assert.deepEqual(f.current(),f.initial);});
test('private or All context, private local draft, pending Files and insufficient two-revision budget refuse before any request',async()=>{
  for(const alter of [f=>f.context.privacy='private',f=>f.context.scope='all',f=>{const d=clone(f.initial);d.recipe.privacy='private';f.setCurrent(d);},f=>{const d=clone(f.initial);d.pendingInputs=['reference'];f.setCurrent(d);},f=>f.target.head_revision=255]){
    const f=fixture();alter(f);const c=new Controller(f.opts);await assert.rejects(f.review(c));assert.equal(f.calls.length,0);
  }
});
test('active editor, pending receipt and a foreign Workspace refuse the review',async()=>{
  for(const alter of [(f,c)=>f.opts.draft.busy=()=>true,(f,c)=>c.state.pending={request_id:'uncertain'},(f,c)=>f.context.workspace_id='c'.repeat(32)]){const f=fixture(),c=new Controller(f.opts);alter(f,c);await assert.rejects(f.review(c));assert.equal(f.calls.length,0);}
});
test('foreign identities, stale head and malformed or changed source hashes cannot become an approved review',async()=>{
  for(const edit of [r=>r.workspace_id='c'.repeat(32),r=>r.draft_id='other',r=>r.revision=2,r=>r.head_revision=4,r=>r.record_sha256='0'.repeat(64),r=>r.inputs_available=false]){
    const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);edit(r);return r;};const c=new Controller(f.opts);await assert.rejects(f.review(c));assert.equal(f.writes().length,0);
  }
});
test('edits, context A-B-A and a closed review during dependency reads never authorize writes',async()=>{
  for(const alter of [(f,c)=>f.change(),(f,c)=>f.context.revision+=2,(f,c)=>f.context.epoch+=2,(f,c)=>f.close(),(f,c)=>c.invalidateRestore()]){
    const f=fixture(),request=f.opts.request;let c;f.opts.request=async(p,q)=>{const r=await request(p,q);alter(f,c);return r;};c=new Controller(f.opts);await assert.rejects(f.review(c));assert.equal(f.writes().length,0);
  }
});
test('a new head or changed dependency at confirmation refuses without checkpointing',async()=>{
  for(const changed of ['head','dependency']){const f=fixture(),c=new Controller(f.opts),r=await f.review(c);if(changed==='head')f.setHead(4);else c.request=async()=>{throw Error('staged input changed');};await c.restoreHistory(r);assert.equal(f.writes().length,0);assert.deepEqual(f.current(),f.initial);}
});
test('late edit or privacy/Workspace epoch change after checkpoint retains it and sends no restore',async()=>{
  for(const alter of [f=>f.change(),f=>f.context.revision+=2,f=>f.context.epoch+=2,f=>f.close()]){const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='replace')alter(f);return r;};const c=new Controller(f.opts),r=await f.review(c);await c.restoreHistory(r);assert.equal(f.writes().length,1);assert.deepEqual(f.records.get(4).draft,f.initial);assert.match(f.messages.map(x=>x.message).join(' '),/checkpoint|saved.*revision 4/i);}
});
test('a failed restoration retains the checkpoint and editor with an honest partial outcome',async()=>{const f=fixture(),request=f.opts.request;f.opts.request=(p,q)=>q?.action==='restore'?Promise.reject(Error('graph changed')):request(p,q);const c=new Controller(f.opts),r=await f.review(c);await c.restoreHistory(r);assert.equal(f.head(),4);assert.deepEqual(f.current(),f.initial);assert.equal(c.state.pending.action,'restore');assert.match(f.messages.map(x=>x.message).join(' '),/revision 4/);});
test('lost checkpoint or restore reply recovers by GET only and never continues or adopts automatically',async()=>{
  for(const action of ['replace','restore']){const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action===action)throw Error('lost reply');return r;};let c=new Controller(f.opts),r=await f.review(c);await c.restoreHistory(r);const count=f.writes().length,pending=clone(c.state.pending);assert.equal(pending.action,action);assert.deepEqual(f.current(),f.initial);c=new Controller({...f.opts,request});await c.recover();assert.equal(f.writes().length,count);assert.equal(c.state.pending,null);assert.equal(c.state.revision,action==='replace'?4:5);assert.deepEqual(f.current(),f.initial);assert.match(f.calls.at(-1).path,new RegExp('/requests/'+pending.request_id+'$'));}
});
test('a committed restoration cannot replace an editor changed while the command was in flight',async()=>{const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='restore')f.change();return r;};const c=new Controller(f.opts),r=await f.review(c);await c.restoreHistory(r);assert.equal(f.head(),5);assert.equal(c.state.revision,5);assert.equal(f.current().recipe.controls.positive,'later local edit');});
test('a substituted restored record leaves the original request pending instead of trusting the receipt',async()=>{const f=fixture(),request=f.opts.request;f.opts.request=async(p,q)=>{const r=await request(p,q);if(q?.action==='restore'){const wrong=clone(f.records.get(2));Object.assign(r,wrong);}return r;};const c=new Controller(f.opts),r=await f.review(c);await c.restoreHistory(r);assert.equal(c.state.pending.action,'restore');assert.deepEqual(f.current(),f.initial);});
test('storage failure, another tab journal and held Web Lock prevent the first command',async()=>{
  for(const alter of [(f,c)=>c.storage.setItem=()=>{throw Error('quota');},(f,c)=>f.storage.set(c.key,'foreign journal'),(f,c)=>c.withLock=async()=>{throw Error('other tab lock');}]){const f=fixture(),c=new Controller(f.opts),r=await f.review(c);alter(f,c);await c.restoreHistory(r);assert.equal(f.writes().length,0);assert.deepEqual(f.current(),f.initial);}
});
