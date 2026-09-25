// The real reference owner, with only transport and DOM replaced. No timers or GPU.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const references = fs.readFileSync(path.join(__dirname, '../app/static/references.js'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const lineage = app.slice(app.indexOf('function parentClaimed('), app.indexOf('function renderPresets('));

function harness() {
  const context = vm.createContext({});
  vm.runInContext([
    "const selected={id:'board',reference_slots:[{},{}],continuation_capability:{}};",
    "let uploaded='source.png',parentAssets=['source','old'],parentByInput={lastReference:'source'};",
    "const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',files:[],addEventListener(){}});return nodes.get(id)};",
    "const notices=[];const message=text=>notices.push(text);const updateReady=()=>{};const esc=String;",
    "const StudioContinuation={sourceInput:()=> 'last_reference'};",
    "const requests=[];const api=(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));",
    "const post=(url,data)=>api(url,{body:data});",
    lineage,
    references,
    "let renders=0;renderReferenceSlots=()=>{renders++};resetReferenceSlots();",
    "Object.assign(referenceRecords[0],{file:'old.png',parent_asset:'old',missing:false});",
    "this.run=code=>eval(code);this.requests=requests;this.notices=notices;",
    "this.upload=(index,name)=>uploadRoleFile(index,{name,type:'image/png',size:10});",
    "this.copy=(index=0,id='style')=>attachReferenceAsset(index,id);",
    "this.state=()=>JSON.stringify({references:referenceRecords,parents:parentAssets,inputs:parentByInput,uploaded,pending:referencePending,renders});",
  ].join('\n'), context);
  return {run: context.run, requests: context.requests, notices: context.notices,
    upload: context.upload, copy: context.copy, state: () => JSON.parse(context.state())};
}
const result = (file, parent) => ({file,sha256:'a'.repeat(64),width:10,height:10,...(parent ? {parent_asset:parent} : {})});

for (const action of ['upload','copy']) test(`replacing a drawn guide by ${action} drops its editable sidecar`, async () => {
  const h = harness(), filename = 'b'.repeat(32) + '_drawn-pose.png';
  h.run(`Object.assign(referenceRecords[0],{file:${JSON.stringify(filename)},artifact_id:'c'.repeat(64),renderer:'studio.coco18-lines/v1'})`);
  const pending = action === 'upload' ? h.upload(0,'drawn-pose.png') : h.copy();
  h.requests[0].resolve(result('d'.repeat(32) + '_drawn-pose.png',action === 'copy' ? 'style' : undefined));
  await pending;
  const slot = h.state().references[0];
  assert.equal(slot.file, 'd'.repeat(32) + '_drawn-pose.png');
  assert.equal('artifact_id' in slot, false);
  assert.equal('renderer' in slot, false);
});

test('clearing a drawn guide drops its editable sidecar before the slot is reused', () => {
  const h = harness();
  h.run("Object.assign(referenceRecords[0],{file:'b'.repeat(32)+'_drawn-pose.png',artifact_id:'c'.repeat(64),renderer:'studio.coco18-lines/v1'});");
  h.run("$('#referenceCards').onclick({target:{closest:selector=>selector==='[data-ref-clear]'?{dataset:{refClear:'0'}}:null}})");
  const slot = h.state().references[0];
  assert.equal(slot.file, null);
  assert.equal('artifact_id' in slot, false);
  assert.equal('renderer' in slot, false);
});

test('the last-started upload wins even when the older upload finishes last', async () => {
  const h = harness(), older = h.upload(0,'older.png'), newer = h.upload(0,'newer.png');
  h.requests[1].resolve(result('newer.png')); await newer;
  h.requests[0].resolve(result('older.png')); await older;
  assert.equal(h.state().references[0].file, 'newer.png');
  assert.equal(h.state().pending, 0);
  assert.deepEqual(h.state().parents, ['source']);
});

test('a library copy commits after unrelated wording changes and preserves the named source', async () => {
  const h = harness(), pending = h.copy();
  h.run("$('#positive').value='newer wording';referenceRecords[1].contribution='keep my edit'");
  h.requests[0].resolve(result('style.png','style')); await pending;
  assert.equal(h.state().references[0].file, 'style.png');
  assert.equal(h.state().references[1].contribution, 'keep my edit');
  assert.deepEqual(h.state().parents, ['source','style']);
  assert.deepEqual(h.state().inputs, {lastReference:'source'});
  assert.equal(h.state().uploaded, 'source.png');
  assert.equal(h.state().pending, 0);
});

for (const latest of ['upload','copy']) test(`a newer ${latest} invalidates the older competing attachment`, async () => {
  const h = harness(), older = latest === 'upload' ? h.copy() : h.upload(0,'older.png');
  const refused = latest === 'upload' ? assert.rejects(older, /slot changed/) : older;
  const newer = latest === 'upload' ? h.upload(0,'newer.png') : h.copy(0,'new-parent');
  h.requests[1].resolve(result('newer.png',latest === 'copy' ? 'new-parent' : undefined)); await newer;
  h.requests[0].resolve(result('older.png',latest === 'upload' ? 'style' : undefined)); await refused;
  assert.equal(h.state().references[0].file, 'newer.png');
  assert.equal(h.state().pending, 0);
});

for (const mutation of [
  "resetReferenceSlots()", // same recipe, new editor epoch
  "referenceRecords[0]={...referenceRecords[0],file:null,parent_asset:null}",
  "referenceEpoch++;[referenceRecords[0],referenceRecords[1]]=[referenceRecords[1],referenceRecords[0]];referencePending=0",
]) test(`a changed destination refuses delayed library bytes: ${mutation}`, async () => {
  const h = harness(), pending = h.copy();
  const refused = assert.rejects(pending, /slot changed/);
  h.run(mutation); const before = h.state();
  h.requests[0].resolve(result('style.png','style')); await refused;
  assert.deepEqual(h.state().references, before.references);
  assert.deepEqual(h.state().parents, before.parents);
  assert.equal(h.state().pending, 0);
});

for (const index of [-1,2,NaN,0.5]) test(`invalid destination ${index} is refused before staging`, async () => {
  const h = harness();
  await assert.rejects(h.copy(index), /destination slot/);
  assert.equal(h.requests.length, 0);
  assert.equal(h.state().pending, 0);
});

test('a failed library request releases pending state without changing attachments', async () => {
  const h = harness(), before = h.state(), pending = h.copy();
  const refused = assert.rejects(pending, /offline/);
  h.requests[0].reject(new Error('offline')); await refused;
  assert.deepEqual(h.state().references, before.references);
  assert.deepEqual(h.state().parents, before.parents);
  assert.equal(h.state().pending, 0);
});

test('two different slots can complete independently', async () => {
  const h = harness(), first = h.copy(0,'first'), second = h.copy(1,'second');
  h.requests[1].resolve(result('second.png','second')); await second;
  h.requests[0].resolve(result('first.png','first')); await first;
  assert.deepEqual(h.state().references.map(r=>r.file), ['first.png','second.png']);
  assert.equal(h.state().pending, 0);
});
