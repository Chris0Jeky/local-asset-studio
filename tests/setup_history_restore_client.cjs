const test=require('node:test'),assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const Apply=require('../app/static/setup-apply.js'),{Controller,verify}=Apply,History=require('../app/static/setup-history.js');
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

// Mount both shipped owners. Document listeners fan out synchronously in registration order,
// including the three recipe notifications emitted while the workbench adopts a shared draft.
class Element{
  constructor(tag,doc){this.tag=tag;this.doc=doc;this.children=[];this.listeners={};this.dataset={};this.hidden=false;this.disabled=false;this.open=false;this.own='';}
  set id(value){this._id=value;this.doc.ids.set(value,this);}get id(){return this._id;}
  set textContent(value){this.own=String(value);this.children=[];}get textContent(){return this.own+this.children.map(c=>typeof c==='string'?c:c.textContent).join('');}
  append(...children){for(const child of children){if(typeof child!=='string')child.parent=this;this.children.push(child);}}
  after(child){child.parent=this.parent;this.parent.children.splice(this.parent.children.indexOf(this)+1,0,child);}
  replaceChildren(...children){this.own='';this.children=[];this.append(...children);}
  setAttribute(){}addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  fire(type){const event={type,target:this};for(const fn of this.listeners[type]||[])fn(event);this.doc.dispatch(type,this);}
  click(){if(this.disabled)return;if(this.type==='checkbox')this.checked=!this.checked;this.fire(this.type==='checkbox'?'change':'click');}
  focus(){this.doc.activeElement=this;}
  closest(selector){for(let n=this;n;n=n.parent)if(selector==='#'+n.id)return n;return null;}
  all(){return this.children.flatMap(c=>typeof c==='string'?[]:[c,...c.all()]);}
  querySelectorAll(selector){assert.equal(selector,'[data-key]');return this.all().filter(n=>n.dataset.key);}
}
const settle=async()=>{for(let n=0;n<8;n++)await new Promise(resolve=>setImmediate(resolve));};
function mounted(options={}){
  const f=fixture(),doc={ids:new Map(),listeners:{},activeElement:null,querySelector(selector){return this.ids.get(selector.slice(1))||null;},createElement(tag){return new Element(tag,this);},
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);},dispatch(type,target=this){for(const fn of this.listeners[type]||[])fn({type,target});}};
  const add=(tag,id,parent)=>{const el=doc.createElement(tag);el.id=id;if(parent)parent.append(el);return el;},create=add('section','createView'),bar=add('div','uxDraftBar',create),input=add('textarea','positive',create),saved=add('details','workshopSaved',create);
  const saveName=add('input','saveName',saved),importRecipe=add('input','importRecipe',saved),reads=[],adoptionEvents=[];importRecipe.type='file';
  const base=head=>({workspace_id:WS,draft_id:ID,head_revision:head,head_record_sha256:f.records.get(head).record_sha256,observation_only:true,generation_submitted:false,staging_performed:false,dependencies_checked:false});
  function page(head=f.head()){
    const revisions=[];for(let revision=head;revision>=Math.max(1,head-19);revision--){const record=f.records.get(revision);revisions.push({revision,record_sha256:record.record_sha256,draft_sha256:record.record_sha256,graph_sha256:record.graph_sha256,record_bytes:record.record_json.length,preset_id:'fixture',backend_id:'primary',input_count:0,recorded_at:1760000000+revision});}
    return {format:'studio.setup-history-page/v2',...base(head),revisions,next_before_revision:head>20?head-19:null};
  }
  async function fetch(path,init={}){
    const url=new URL(path,'http://fixture'),params=url.searchParams;let value;
    if(url.pathname.endsWith('/history')){reads.push(path);value=options.historyRead?await options.historyRead(page,reads.length):page();}
    else if(url.pathname.endsWith('/compare')){const left=+params.get('left'),right=+params.get('right'),side={sha256:'d'.repeat(64),bytes:0,preview:'',truncated:false,omitted_bytes:0,redacted:false};
      value={format:'studio.setup-history-compare/v2',...base(f.head()),left_revision:left,right_revision:right,left_record_sha256:f.records.get(left).record_sha256,right_record_sha256:f.records.get(right).record_sha256,sections:[{section:'wording',changed:true,left:side,right:side}]};
    }else value=await f.opts.request(path,init.body?JSON.parse(init.body):undefined);
    const text=JSON.stringify(value),bytes=new TextEncoder().encode(text);let sent=false;
    return {ok:true,text:async()=>text,body:{getReader:()=>({async read(){if(sent)return {done:true};sent=true;return {done:false,value:bytes};},async cancel(){}})}};
  }
  const w={document:doc,AbortController,setTimeout,clearTimeout,fetch,localStorage:f.opts.storage,StudioSetupDraft:f.opts.draft,StudioSetupApply:{},addEventListener(){}};
  Apply.mount(w,{withLock:fn=>fn(),hashText:hash,uuid:f.opts.uuid,context:f.opts.context});History.mount(w);
  const c=w.StudioSetupApply.controller,h=w.StudioSetupHistory.history,adopt=f.opts.draft.adopt;
  f.opts.draft.adopt=(draft,stamp)=>{adopt(draft,stamp);for(let n=0;n<3;n++){adoptionEvents.push(c.historyAdoption);doc.dispatch('studio:recipe');}};
  const details=doc.querySelector('#setupHistory'),status=()=>doc.querySelector('#setupHistoryStatus').textContent;
  return {f,doc,c,h,details,reads,page,input,saveName,importRecipe,adoptionEvents,status,rows:()=>doc.querySelector('#setupHistoryList').textContent,
    async open(){details.open=true;details.fire('toggle');await settle();},async review(){await h.review(1);assert.ok(h.state.restoration);},
    close(){details.open=false;details.fire('toggle');},dispatch:(type,target)=>doc.dispatch(type,target)};
}
test('mounted restore survives every own adoption event and refreshes the list once without repeating writes',async()=>{
  const p=mounted();await p.open();await p.review();const review=p.h.state.restoration.review,epoch=p.c.restoreEpoch;
  await p.h.commitRestore();
  assert.deepEqual(p.f.writes().map(call=>call.q.action),['replace','restore']);assert.equal(p.c.state.loadedRevision,5);
  assert.equal(p.reads.length,2,'one initial read and one automatic refresh');assert.equal(p.h.state.head,5);assert.equal(p.h.state.busy,false);
  assert.match(p.rows(),/Revision 5 \(latest loaded revision\)/);assert.doesNotMatch(p.rows(),/current head/);
  assert.match(p.status(),/History refreshed through revision 5/);assert.doesNotMatch(p.status(),/context changed|Review the restore again/);
  assert.match(p.doc.querySelector('#sharedSetupStatus').textContent,/current draft was saved as revision 4.*Revision 1 was restored.*revision 5/);
  assert.equal(p.adoptionEvents.length,3);assert.ok(p.adoptionEvents.every(owner=>owner===review));assert.equal(p.c.historyAdoption,null);
  assert.equal(p.c.restoreEpoch,epoch+3,'the command owner still observes all recipe events');
});
test('Saved setups metadata preserves both restore owners, while real edits and saved setup application cancel',async()=>{
  for(const action of [p=>p.dispatch('input',p.input),p=>p.dispatch('change',p.input),p=>p.dispatch('studio:recipe')]){
    const p=mounted();await p.open();await p.review();const review=p.h.state.restoration.review,epoch=p.c.restoreEpoch;
    for(const type of ['input','change'])for(const input of [p.saveName,p.importRecipe])p.dispatch(type,input);
    assert.equal(p.c.restoreEpoch,epoch);assert.equal(p.h.state.restoration.review,review);assert.equal(review.current(),true);
    action(p);assert.equal(p.c.restoreEpoch,epoch+1);assert.equal(p.h.state.restoration,null);assert.equal(review.current(),false);
    assert.equal(p.f.writes().length,0);assert.match(p.status(),/Create or its context changed/);
  }
});
test('Saved setups metadata entered while checkpointing does not stop the reviewed restoration',async()=>{
  const p=mounted(),request=p.f.opts.request;p.f.opts.request=async(path,q)=>{const result=await request(path,q);if(q?.action==='replace')p.dispatch('input',p.saveName);return result;};
  await p.open();await p.review();await p.h.commitRestore();assert.equal(p.c.state.loadedRevision,5);assert.equal(p.h.state.head,5);assert.equal(p.f.writes().length,2);
});
test('follow-up history must include the confirmed restore, but accepts a newer shared head without adopting it',async()=>{
  for(const newest of [3,6]){
    let p;p=mounted({historyRead(page,n){if(n===1)return page();if(newest===6){p.f.records.set(6,clone(p.f.records.get(2)));p.f.setHead(6);}return page(newest);}});
    await p.open();await p.review();await p.h.commitRestore();assert.equal(p.c.state.loadedRevision,5);assert.deepEqual(p.f.current(),p.f.saved);assert.equal(p.f.writes().length,2);
    assert.equal(p.h.state.busy,false);assert.equal(p.h.restoreRefresh,null);
    if(newest===3){assert.equal(p.h.state.head,3);assert.match(p.status(),/Restore completed as revision 5.*history could not refresh.*ends before restored revision 5.*list still ends at revision 3/);assert.doesNotMatch(p.status(),/Nothing was changed/);}
    else{assert.equal(p.h.state.head,6);assert.match(p.status(),/History refreshed through revision 6/);}
  }
});
test('a failed follow-up GET preserves the committed restore and gives a truthful manual refresh path',async()=>{
  const p=mounted({historyRead(page,n){if(n===2)throw Error('History server unavailable');return page();}});
  await p.open();await p.review();await p.h.commitRestore();assert.equal(p.c.state.loadedRevision,5);assert.equal(p.h.state.head,3);assert.equal(p.f.writes().length,2);
  assert.match(p.status(),/Restore completed as revision 5.*history could not refresh.*History server unavailable.*Use Refresh history/);assert.doesNotMatch(p.status(),/Nothing was changed|Review the restore again/);
  assert.equal(p.h.state.busy,false);assert.equal(p.h.restoreRefresh,null);await p.h.load();assert.equal(p.h.state.head,5);assert.equal(p.f.writes().length,2);
});
test('closing, privacy or Workspace A-B-A, edits, new selection and refresh discard late follow-up results and errors',async()=>{
  const changes={close:p=>p.close(),privacy:p=>{p.f.context.privacy='private';p.dispatch('studio:privacy-change');p.f.context.privacy='regular';p.dispatch('studio:privacy-change');},
    workspace:p=>{p.f.context.workspace_id='b'.repeat(32);p.dispatch('studio:workspace-change');p.f.context.workspace_id=WS;p.dispatch('studio:workspace-change');},
    input:p=>p.dispatch('input',p.input),recipe:p=>p.dispatch('studio:recipe'),selection:p=>p.details.all().find(el=>el.dataset.key==='pick-2').click(),refresh:p=>p.h.load()};
  for(const [name,change] of Object.entries(changes))for(const error of [false,true]){
    let release;const held=new Promise(resolve=>release=resolve),p=mounted({async historyRead(page,n){if(n===2){await held;if(error)throw Error('late refusal');return page(3);}return page();}});
    await p.open();await p.review();const work=p.h.commitRestore();await settle();assert.ok(p.h.restoreRefresh,name);assert.equal(p.c.state.loadedRevision,5);assert.equal(p.h.state.restoration,null);
    await change(p);assert.equal(p.h.state.busy,false,name);const status=p.status(),rows=p.rows(),picked=clone(p.h.state.picked);
    assert.doesNotMatch(status,/Reading the newest history|Review the restore again/,name);
    release();await work;assert.equal(p.status(),status,name);assert.equal(p.rows(),rows,name);assert.deepEqual(p.h.state.picked,picked,name);assert.equal(p.h.state.busy,false,name);
    assert.equal(p.h.restoreRefresh,null,name);assert.equal(p.f.writes().length,2,name);assert.equal(p.c.state.loadedRevision,5,name);
  }
});
test('busy, failed, unknown or unadopted restores never trigger the successful follow-up GET',async()=>{
  for(const mode of ['busy','failed','unknown','late-edit','adoption-error']){
    const p=mounted();await p.open();await p.review();const request=p.f.opts.request;
    if(mode==='busy')p.c.running=true;
    if(mode==='adoption-error')p.f.opts.draft.adopt=()=>{throw Error('editor unavailable');};
    p.f.opts.request=async(path,q)=>{if(mode==='failed'&&q?.action==='restore')throw Error('restore refused');const result=await request(path,q);
      if(q?.action==='restore'){if(mode==='unknown')throw Error('lost reply');if(mode==='late-edit'){p.f.change();p.dispatch('input',p.input);}}return result;};
    await p.h.commitRestore();assert.equal(p.reads.length,1,mode);assert.equal(p.c.state.loadedRevision,undefined,mode);assert.equal(p.c.historyAdoption,null,mode);assert.equal(p.h.state.busy,false,mode);
    assert.doesNotMatch(p.status(),/Restore completed|History refreshed/,mode);if(mode==='late-edit')assert.equal(p.f.current().recipe.controls.positive,'later local edit');
  }
});
