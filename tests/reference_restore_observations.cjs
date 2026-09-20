// Late availability responses must describe the observed attachment, never its replacement.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const read = file => fs.readFileSync(path.join(__dirname, '../app/static/', file), 'utf8');
const app = read('app.js');
const lineage = app.slice(app.indexOf('function parentClaimed('), app.indexOf('function renderPresets('));
function harness() {
  const c = vm.createContext({});
  vm.runInContext([
    "const selected={reference_slots:[{},{}],reference_board:{min:1},last_reference:true,continuation_capability:{}};",
    "let parentAssets=['source'],parentByInput={lastReference:'source'},uploaded=null,lastUploaded='source.png';",
    "const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{value:'',files:[],addEventListener(){}});return nodes.get(id)};",
    "const notices=[],message=text=>notices.push(text),updateReady=()=>{},esc=String;",
    "const StudioContinuation={sourceInput:()=> 'last_reference'};",
    "const requests=[],api=(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject})),post=(url,body)=>api(url,{body});",
    lineage, read('reference-model.js'), read('references.js'),
    "renderReferenceSlots=()=>{};resetReferenceSlots();Object.assign(referenceRecords[0],{file:'old.png',sha256:'old',missing:false});",
    "this.restore=records=>restoreReferenceSlots(records);this.upload=()=>uploadRoleFile(0,{name:'new.png',size:10,type:'image/png'});",
    "this.run=code=>eval(code);this.requests=requests;this.notices=notices;",
    "this.state=()=>JSON.stringify({records:referenceRecords,pending:referencePending,ready:referencesReady(),parents:parentAssets,inputs:parentByInput});",
  ].join('\n'), c);
  return {restore:c.restore,upload:c.upload,run:c.run,requests:c.requests,notices:c.notices,state:()=>JSON.parse(c.state())};
}
const oldStatus = available => [{file:'old.png',sha256:'old',available}];
for (const outcome of ['success','failure']) test(`late restore ${outcome} cannot invalidate a newly uploaded picture`, async () => {
  const h=harness(), checking=h.restore(), uploading=h.upload();
  h.requests[1].resolve({file:'new.png',sha256:'new'});await uploading;
  assert.equal(h.state().pending,1);
  if(outcome==='success')h.requests[0].resolve(oldStatus(true));else h.requests[0].reject(Error('old check failed'));
  await checking;
  assert.equal(h.state().records[0].missing,false);
  assert.equal(h.state().ready,true);
  assert.equal(h.state().pending,0);
  assert.deepEqual(h.state().inputs,{lastReference:'source'});
  assert.deepEqual(h.state().parents,['source']);
  assert.equal(h.notices.length,0);
});
for (const outcome of ['success','failure']) test(`an older ${outcome} cannot overwrite a later check of the same record`, async () => {
  const h=harness(),older=h.restore(),newer=h.restore();
  h.requests[1].resolve(oldStatus(true));await newer;
  if(outcome==='success')h.requests[0].resolve(oldStatus(false));else h.requests[0].reject(Error('older failed'));
  await older;assert.equal(h.state().ready,true);assert.equal(h.notices.length,0);
});
test('an old record cannot affect a separately restored setup in the same epoch',async()=>{
  const h=harness(),older=h.restore();
  const newer=h.restore([{file:'new.png',sha256:'new'}, {file:null}]);
  h.requests[1].resolve([{file:'new.png',sha256:'new',available:true}]);await newer;
  h.requests[0].resolve(oldStatus(false));await older;
  assert.equal(h.state().ready,true);assert.equal(h.notices.length,0);
});
test('matching filename and hash do not rescue an observation superseded by a new upload',async()=>{
  const h=harness(),older=h.restore(),upload=h.upload();
  h.requests[1].resolve({file:'old.png',sha256:'old'});await upload;
  h.requests[0].resolve(oldStatus(false));await older;assert.equal(h.state().ready,true);
});
for(const state of ['unavailable','different hash','transport failure'])test(`a current ${state} still blocks readiness`,async()=>{
  const h=harness(),pending=h.restore();
  if(state==='transport failure')h.requests[0].reject(Error('offline'));
  else h.requests[0].resolve([{file:'old.png',sha256:state==='different hash'?'changed':'old',available:state!=='unavailable'}]);
  await pending;assert.equal(h.state().ready,false);assert.equal(h.state().records[0].missing,true);
  assert.equal(!!h.state().records[1].missing,false,'empty optional position is not a missing file');
  assert.equal(h.state().pending,0);assert.equal(h.notices.length,1);
});
test('epoch reset owns the old pending count',async()=>{
  const h=harness(),pending=h.restore();h.run('resetReferenceSlots()');
  h.requests[0].reject(Error('old failure'));await pending;
  assert.equal(h.state().pending,0);assert.equal(h.notices.length,0);
});
