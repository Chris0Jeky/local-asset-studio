'use strict';
const assert=require('node:assert/strict'),{test}=require('node:test'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
const workbench=fs.readFileSync(path.join(__dirname,'../app/static/studio-workbench.js'),'utf8');
function section(source,start,end){const a=source.indexOf(start),b=source.indexOf(end,a+start.length);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
function page(){
  const nodes=new Map(),writes=[],messages=[],pending=[],state={scope:'regular',privacy:'regular',revision:0};
  const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',files:[],textContent:'',innerHTML:'',classList:{toggle(){}},addEventListener(){},setAttribute(){},focus(){}});return nodes.get(id);};
  const context={console,URL,Blob,AbortController,location:{hash:''},setInterval(){},setTimeout(){},clearTimeout(){},
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener(){}},
    StudioPrivacy:{capture:()=>({...state}),creation:()=>state.privacy,scope:()=>state.scope,allows:job=>state.scope==='all'||(job.privacy||'regular')===state.scope,submitted(){}},
    fetch:(url,options={})=>{if(options.method!=='POST')return new Promise(()=>{});const next=deferred();writes.push({url,options});pending.push(next);return next.promise;}};
  context.window=context;vm.createContext(context);vm.runInContext(app,context);
  context.messages=messages;
  vm.runInContext("selected={id:'fixture',reference:true,last_reference:true};continuationBlockers=()=>[];updateReady=()=>{};message=(...args)=>messages.push(args);refresh=async()=>{};attachedReferencePayload=()=>[]",context);
  const file=name=>({name,type:'image/png',size:32});
  node('#reference').files=[file('first.png')];node('#lastReference').files=[file('last.png')];node('#batch').value='1';
  const reply=(index,data,ok=true)=>pending[index].resolve({ok,status:ok?200:400,json:async()=>data});
  return {context,node,writes,messages,state,reply,pending,run:js=>vm.runInContext(js,context),turn:()=>new Promise(resolve=>setImmediate(resolve))};
}
test('privacy switch during first upload never stages a newly selected private second file in regular storage',async()=>{
  const h=page(),send=h.node('#generate').onclick();assert.equal(h.writes.length,1);
  Object.assign(h.state,{privacy:'private',scope:'private',revision:1});
  h.node('#lastReference').files=[{name:'private-canary.png',type:'image/png',size:32}];
  h.reply(0,{file:'first-staged.png'});await h.turn();
  // Release a buggy second request so this regression never leaves a pending test.
  if(h.writes.length>1)h.reply(1,{file:'wrong-scope.png'});
  await send;
  assert.equal(h.writes.length,1,'the new File must not be uploaded through the old regular owner');
  assert.equal(h.run('uploaded'),null);assert.equal(h.run('lastUploaded'),null);
});
test('a delayed private upload refusal cannot replace the Regular editor message',async()=>{
  const h=page();Object.assign(h.state,{privacy:'private',scope:'private',revision:1});
  const send=h.node('#generate').onclick();Object.assign(h.state,{privacy:'regular',scope:'regular',revision:2});
  h.reply(0,{error:'private source canary'},false);await send;
  assert.doesNotMatch(JSON.stringify(h.messages),/private source canary/);
});
test('an unchanged owner uploads both captured files and submits one frozen creation',async()=>{
  const h=page(),first=h.node('#reference').files[0],last=h.node('#lastReference').files[0];
  const send=h.node('#generate').onclick();h.reply(0,{file:'first-staged.png'});await h.turn();
  assert.equal(h.writes[0].options.body,first);assert.equal(h.writes[1].options.body,last);
  h.reply(1,{file:'last-staged.png'});await h.turn();
  assert.equal(h.writes.length,3);assert.equal(h.writes[2].url,'/api/jobs');
  const body=JSON.parse(h.writes[2].options.body);assert.equal(body.controls.reference,'first-staged.png');assert.equal(body.controls.last_reference,'last-staged.png');
  h.reply(2,{id:'queued-fixture',message:'Queued'});await send;
  assert.equal(h.run("startedJobIds.has('queued-fixture')"),true);
});
test('a job admitted before a scope switch keeps its acknowledgment without publishing private text',async()=>{
  const h=page();Object.assign(h.state,{privacy:'private',scope:'private',revision:1});
  h.node('#reference').files=[];h.node('#lastReference').files=[];
  const send=h.node('#generate').onclick();await h.turn();assert.equal(h.writes[0].url,'/api/jobs');
  Object.assign(h.state,{privacy:'regular',scope:'regular',revision:2});
  h.reply(0,{id:'private-queued',privacy:'private',message:'private response canary'});await send;
  assert.equal(h.run("startedJobIds.has('private-queued')"),true);
  assert.doesNotMatch(JSON.stringify(h.messages),/private response canary/);
});
function attachmentPage(kind){
  const nodes=new Map(),response=deferred(),button={dataset:{uxPull:'private-asset'},disabled:false};
  const q=id=>{if(!nodes.has(id))nodes.set(id,{value:'recipe',textContent:'',disabled:false});return nodes.get(id);};
  const context={q,AbortSignal,selectionEpoch:1,handoffEpoch:1,sourcePickerEpoch:1,handoffId:'private-asset',sourceContext:{sha256:'sha'},
    handoffBusy:false,pickerBusy:false,handoffBusyOwner:null,pickerBusyOwner:null,handoffBaseline:'same',workbenchStamp:()=> 'same',destinationDetails(){},syncReady(){},
    handoff:{open:true},picker:{open:true},api:()=>response.promise,post:()=>response.promise,
    selected:{reference:true},continuationState:null,attachStamp:()=> 'same',privacyOptions:()=>({})};
  context.window=context;vm.createContext(context);
  const start=kind==='handoff'?"  q('#uxPrepareHandoff').onclick=async()=>{":"  q('#uxSourceAssets').onclick=async e=>{";
  const end=kind==='handoff'?"\n  handoff.addEventListener('close'":"\n  picker.addEventListener('cancel'";
  vm.runInContext(section(workbench,start,end),context);
  const call=()=>kind==='handoff'?q('#uxPrepareHandoff').onclick():q('#uxSourceAssets').onclick({target:{closest:()=>button}});
  return {context,q,response,call};
}
for(const kind of ['handoff','picker'])test(`a stale private ${kind} refusal cannot publish into or release a newer regular attachment`,async()=>{
  const h=attachmentPage(kind),request=h.call();
  h.context.selectionEpoch++;h.context.handoffEpoch++;h.context.sourcePickerEpoch++;
  h.context.handoffBusy=h.context.pickerBusy=true;
  h.context.handoffBusyOwner={};h.context.pickerBusyOwner={};
  const target=kind==='handoff'?'#uxHandoffStatus':'#uxPickerStatus';h.q(target).textContent='Regular attachment';
  h.response.reject(Error('Private attachment error canary'));await request;
  assert.equal(h.q(target).textContent,'Regular attachment');
  assert.equal(h.context[kind==='handoff'?'handoffBusy':'pickerBusy'],true,'newer request keeps its busy owner');
});

// Exercise the production sibling handlers and the real reference attachment owner.
// A view-only switch keeps the same draft/slot objects, so selection and slot guards
// alone cannot stand in for the captured privacy revision.
function siblingAttachmentPage(kind){
  const nodes=new Map(),response=deferred(),messages=[],writes=[],effects=[];
  const privacy={scope:'private',privacy:'private',revision:1};
  const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',disabled:false,hidden:false,attributes:{},replaceChildren(){this.textContent='';},setAttribute(name,value){this.attributes[name]=value;}});return nodes.get(id);};
  const item={asset:{id:'private-second',sha256:'second-sha',title:'Private second picture'}};
  const button={dataset:{uxSecondSlot:'1'},disabled:false};
  const context={q:node,$:node,selectionEpoch:1,referenceEpoch:1,referencePending:0,
    continuationState:{source_asset_id:'private-source',source_sha256:'source-sha',reference_file:'old.png'},
    continuationSource:{positive:'private original'},selected:{id:'fixture',reference_slots:[{},{}],continuation_capability:{}},
    secondPicture:item,secondPanel:{hidden:false,attributes:{},contains:()=>false,querySelectorAll:()=>[button],setAttribute(name,value){this.attributes[name]=value;}},
    pickerBusy:false,handoffBusy:false,pickerBusyOwner:null,submitting:false,restoring:false,draftDirty:false,
    sourceReadError:'',varyUnapplied:null,pendingInputs:new Set(['reference']),view:'create',document:{activeElement:{},addEventListener:(name,callback)=>{if(name==='studio:privacy-change')context.privacyChange=callback;}},
    sourceSeq:0,sourcePickerEpoch:0,handoffEpoch:0,pickerLoading:false,handoffBusyOwner:null,picker:{open:false},handoff:{open:false},
    homeEpoch:0,homeData:null,homeSignature:'',tileRead:0,parallaxRead:0,jobInspector:{open:false,replaceChildren(){}},
    referenceRecords:[{file:'first.png'},{file:'old-second.png'}],referenceAttachments:new WeakMap(),referenceChecks:new WeakMap(),referenceUploading:new Set(),uploaded:null,
    StudioPrivacy:{capture:()=>({...privacy}),creation:()=>privacy.privacy},privacyOptions:captured=>({headers:{'X-Studio-Privacy':captured.scope,'X-Studio-Creation-Privacy':captured.privacy}}),
    StudioContinuation:{sourceInput:()=> 'reference',sourceLabel:()=> 'Source',normalize:value=>value,guidance:()=>[]},
    post:(url,body,options)=>{writes.push({url,body,options});return response.promise;},
    confirm:()=>true,workbenchStamp:()=> 'same',syncReady(){},updateReady(){},renderReferenceSlots(){},forgetDrawnGuide(){},focusReadinessTarget(){},
    announce:(...args)=>messages.push(args),saveDraft:()=>effects.push('save'),syncCreate:()=>effects.push('sync'),
    attachContinuationSource:()=>effects.push('attach'),replaceParentAsset:()=>effects.push('parent'),selectPreset:()=>effects.push('reset'),
    dismissSecondPicture:()=>{context.secondPicture=null;effects.push('dismiss');},secondName:value=>value.asset.title,
  };
  context.window=context;vm.createContext(context);
  const references=fs.readFileSync(path.join(__dirname,'../app/static/references.js'),'utf8');
  vm.runInContext(section(references,'function beginReferenceAttachment(index){','// The readiness model'),context);
  vm.runInContext(section(workbench,'  async function pullIntoSlot(index,id',"  q('#uxSourceAssets').onclick=async e=>{"),context);
  vm.runInContext(section(workbench,"  document.addEventListener('studio:privacy-change',event=>{",'  showView(location.hash);initializeDrafts();'),context);
  if(kind==='reattach')vm.runInContext(section(workbench,'  async function reattachSource(){','  // One slot, two pictures:'),context);
  if(kind==='replace')vm.runInContext(section(workbench,"  q('#uxSecondReplace').onclick=async()=>{",'  // The existing slot attachment owner'),context);
  if(kind==='slot')vm.runInContext(section(workbench,"  q('#uxSecondSlots').onclick=async e=>{",'  // A modal handoff'),context);
  const call=()=>kind==='reattach'?context.reattachSource():kind==='replace'?node('#uxSecondReplace').onclick():kind==='slot'?node('#uxSecondSlots').onclick({target:{closest:()=>button}}):context.pullIntoSlot(1,item.asset.id);
  const stale=()=>{privacy.scope='regular';privacy.revision++;context.privacyChange({detail:{scope:'regular',previousScope:'private',creation:'private',previousCreation:'private'}});context.pickerBusy=true;context.pickerBusyOwner={newer:true};};
  const reply=()=>{const source=kind==='reattach'?'private-source':'private-second',sha=kind==='reattach'?'source-sha':'second-sha';response.resolve({file:'private-copy.png',parent_asset:source,sha256:sha,context:{asset_id:source,sha256:sha,positive:'private response canary'}});};
  return {context,privacy,messages,writes,effects,response,call,stale,reply,button};
}
for(const kind of ['reattach','replace','slot','pull']){
  test(`a stale private ${kind} refusal cannot expose text or release a newer attachment`,async()=>{
    const h=siblingAttachmentPage(kind),request=h.call();assert.equal(h.writes.length,1);
    h.stale();h.response.reject(Error('Private sibling error canary'));await request;
    assert.deepEqual(h.messages,[]);assert.equal(h.context.pickerBusy,true);assert.deepEqual(h.effects,[]);
  });
  test(`a ${kind} acknowledgment after a privacy-view change cannot apply to the current draft`,async()=>{
    const h=siblingAttachmentPage(kind),claim=JSON.stringify(h.context.continuationState),slots=JSON.stringify(h.context.referenceRecords),request=h.call();
    h.stale();h.reply();await request;
    assert.equal(h.writes.length,1,'the admitted copy is never retried');
    assert.equal(JSON.stringify(h.context.continuationState),claim);assert.equal(JSON.stringify(h.context.referenceRecords),slots);
    assert.deepEqual(h.effects,[]);assert.deepEqual(h.messages,[]);assert.equal(h.context.pickerBusy,true);
  });
  test(`an unchanged ${kind} owner applies its single acknowledged copy`,async()=>{
    const h=siblingAttachmentPage(kind),request=h.call();h.reply();await request;
    assert.equal(h.writes.length,1);assert.ok(h.effects.includes('save'));assert.equal(h.context.pickerBusy,false);
    assert.ok(h.messages.length||kind==='pull');
  });
}
test('privacy retirement clears the extra-slot affordance before its old response settles',async()=>{
  const h=siblingAttachmentPage('slot'),request=h.call();
  assert.equal(h.button.disabled,true);assert.equal(h.context.secondPanel.attributes['aria-busy'],'true');
  h.stale();assert.equal(h.button.disabled,false);assert.equal(h.context.secondPanel.attributes['aria-busy'],'false');
  h.reply();await request;assert.equal(h.context.pickerBusy,true,'the old response cannot release a new owner');
});
test('native continuation media explicitly admits either source classification only for private creation',()=>{
  const h=siblingAttachmentPage('pull');
  Object.assign(h.context,{contextPanel:{},selected:{continuation_capability:{prompt_role:'none'}}});
  vm.runInContext(section(workbench,'  function syncContinuation(){','  async function readSource('),h.context);
  h.context.syncContinuation();assert.equal(h.context.q('#uxContinuationImage').src,'/api/assets/private-source/file?privacy=all');
  h.privacy.privacy='regular';h.context.syncContinuation();assert.equal(h.context.q('#uxContinuationImage').src,'/api/assets/private-source/file');
});
