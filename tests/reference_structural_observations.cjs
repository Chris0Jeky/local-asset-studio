// Availability follows retained records; attachment writes remain destination-bound.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const read = name => fs.readFileSync(path.join(__dirname, '../app/static/', name), 'utf8');
const app = read('app.js');
const start = app.indexOf('function parentClaimed('), end = app.indexOf('function renderPresets(', start);
assert.ok(start >= 0 && end > start, 'load the real parent-claim owner');

function harness({emptySecond = false, min = 1} = {}) {
  const c = vm.createContext({});
  vm.runInContext([
    `let selected={reference_slots:[{role:'style'},{role:'style'}],reference_board:{min:${min}},last_reference:true};`,
    "let parentAssets=['source','other'],parentByInput={lastReference:'source'},uploaded=null,lastUploaded='source.png';",
    "const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{value:'',files:[],parentElement:null,addEventListener(){}});return nodes.get(id)};",
    "const notices=[],readiness=[],message=text=>notices.push(text),updateReady=()=>readiness.push(referencesReady()),esc=String;",
    "const StudioContinuation={sourceInput:()=> 'last_reference'};",
    "const requests=[],api=(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject})),post=(url,body)=>api(url,{body});",
    app.slice(start,end), read('reference-model.js'), read('references.js'),
    "resetReferenceSlots();Object.assign(referenceRecords[0],{file:'old.png',sha256:'old',parent_asset:'source',missing:false});",
    emptySecond ? "parentAssets=['source'];" : "Object.assign(referenceRecords[1],{file:'other.png',sha256:'other',parent_asset:'other',missing:false});",
    "this.restore=records=>restoreReferenceSlots(records);this.upload=i=>uploadRoleFile(i,{name:'new.png',size:10,type:'image/png'});this.copy=i=>attachReferenceAsset(i,'new-parent');",
    "this.edit=(kind,index)=>$('#referenceCards').onclick({target:{closest:selector=>selector==='[data-ref-'+kind+']'?{dataset:{['ref'+kind[0].toUpperCase()+kind.slice(1)]:String(index)}}:null}});",
    "this.reset=()=>resetReferenceSlots();this.requests=requests;this.notices=notices;this.readiness=readiness;",
    "this.state=()=>JSON.stringify({records:referenceRecords,pending:referencePending,ready:referencesReady(),parents:parentAssets,inputs:parentByInput,payload:attachedReferencePayload()});",
  ].join('\n'), c);
  return {...c,state:()=>JSON.parse(c.state())};
}
const status = (available = true, sha256 = 'old') => [
  {file:'old.png',sha256,available}, {file:'other.png',sha256:'other',available:true},
];
function retainedSource(h) {
  assert.deepEqual(h.state().inputs,{lastReference:'source'});
  assert.ok(h.state().parents.includes('source'));
  assert.ok(h.state().payload.every(r=>!('epoch' in r)&&!('check' in r)), 'no observation token in serialized records');
}

for (const outcome of ['available','missing','hash mismatch','transport failure']) {
  test(`clearing another slot retains a pending ${outcome} observation`,async()=>{
    const h=harness(),checking=h.restore();
    assert.equal(h.state().pending,1);h.edit('clear',1);
    assert.equal(h.state().pending,1,'retained bytes still await their check');
    assert.equal(h.state().ready,false,'clear must not turn unchecked saved bytes into ready sources');
    assert.equal(h.readiness.at(-1),false,'the live readiness consumer sees the same pending state');
    assert.equal(h.requests.length,1,'structural edit does not launch another request');
    if(outcome==='transport failure')h.requests[0].reject(Error('offline'));
    else h.requests[0].resolve(status(outcome!=='missing',outcome==='hash mismatch'?'changed':'old'));
    await checking;
    assert.equal(h.state().records[0].missing,outcome!=='available');
    assert.equal(h.state().ready,outcome==='available');assert.equal(h.state().pending,0);
    assert.equal(h.state().records[1].file,null);assert.equal(h.state().records[1].missing,false);
    assert.equal(h.notices.length,outcome==='available'?0:1);retainedSource(h);
  });
}
for (const kind of ['down','up']) test(`${kind} reorder applies availability to the record, not the previous index`,async()=>{
  const h=harness(),checking=h.restore();h.edit(kind,kind==='down'?0:1);
  assert.equal(h.state().pending,1);assert.equal(h.state().ready,false);
  h.requests[0].resolve(status(false));await checking;
  assert.deepEqual(h.state().records.map(r=>[r.file,r.missing]),[['other.png',false],['old.png',true]]);
  assert.equal(h.state().pending,0);assert.equal(h.state().ready,false);retainedSource(h);
});
test('repeated reorders carry a check once and issue no replacement reads',async()=>{
  const h=harness(),checking=h.restore();h.edit('down',0);h.edit('up',1);h.edit('down',0);
  assert.equal(h.state().pending,1);assert.equal(h.requests.length,1);
  h.requests[0].resolve(status());await checking;assert.equal(h.state().pending,0);assert.equal(h.state().ready,true);
});
test('clearing all observed bytes drops pending authority without inventing a missing empty slot',async()=>{
  const h=harness({emptySecond:true,min:0}),checking=h.restore();h.edit('clear',0);
  assert.equal(h.state().pending,0);assert.equal(h.state().ready,true);
  h.requests[0].reject(Error('discarded check'));await checking;
  assert.equal(h.state().pending,0);assert.equal(h.notices.length,0);retainedSource(h);
});
test('a reset after reordering prevents late results from mutating a replacement recipe',async()=>{
  const h=harness(),checking=h.restore();h.edit('down',0);h.reset();const before=h.state();
  h.requests[0].reject(Error('obsolete recipe'));await checking;
  assert.deepEqual(h.state(),before);assert.equal(h.notices.length,0);
});
test('a structural edit still cancels old destination-bound uploads while retaining reads',async()=>{
  const h=harness(),checking=h.restore(),uploading=h.upload(0);assert.equal(h.state().pending,2);
  h.edit('down',0);assert.equal(h.state().pending,1);
  h.requests[1].resolve({file:'unwanted.png',sha256:'unwanted'});assert.equal(await uploading,false);
  assert.equal(h.state().pending,1);assert.equal(h.state().records[1].file,'old.png');
  h.requests[0].resolve(status(false));await checking;assert.equal(h.state().records[1].missing,true);assert.equal(h.state().pending,0);
});
for (const replace of ['upload','copy']) test(`a committed ${replace} supersedes a carried check even for identical bytes`,async()=>{
  const h=harness(),checking=h.restore();h.edit('down',0);const writing=h[replace](1);
  h.requests[1].resolve({file:'old.png',sha256:'old',...(replace==='copy'?{parent_asset:'new-parent'}:{})});await writing;
  h.requests[0].resolve(status(false));await checking;
  assert.equal(h.state().records[1].missing,false);assert.equal(h.state().ready,true);assert.equal(h.state().pending,0);retainedSource(h);
});
test('a failed replacement does not invalidate a carried observation of unchanged bytes',async()=>{
  const h=harness(),checking=h.restore();h.edit('down',0);const uploading=h.upload(1);
  h.requests[1].reject(Error('upload refused'));await uploading;h.requests[0].resolve(status(false));await checking;
  assert.equal(h.state().records[1].missing,true);assert.equal(h.state().pending,0);assert.equal(h.state().ready,false);
});
test('only the newest overlapping check is counted after reordering',async()=>{
  const h=harness(),older=h.restore(),newer=h.restore();assert.equal(h.state().pending,2);h.edit('down',0);
  assert.equal(h.state().pending,1);h.requests[1].resolve(status());await newer;
  assert.equal(h.state().pending,0);h.requests[0].reject(Error('old check'));await older;
  assert.equal(h.state().pending,0);assert.equal(h.state().ready,true);assert.equal(h.notices.length,0);
});
test('a retired check cannot decrement a new upload after its last observed file is cleared',async()=>{
  const h=harness({emptySecond:true}),checking=h.restore();h.edit('clear',0);const uploading=h.upload(0);
  h.requests[0].reject(Error('discarded check'));await checking;assert.equal(h.state().pending,1);
  h.requests[1].resolve({file:'new.png',sha256:'new'});await uploading;assert.equal(h.state().pending,0);assert.equal(h.state().ready,true);
});
