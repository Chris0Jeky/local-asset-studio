'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup,collectionReceipt,memoryStorage}=require('./collection_editor_fixture.cjs');
const source=fs.readFileSync(path.join(__dirname,'../app/static/collection-editor.js'),'utf8');
const A='a'.repeat(32);
function page(storage=memoryStorage()){
  const s=setup({storage});
  s.run(`assetState.collections=[{id:'${A}',name:'Before',description:'Original',revision:1}];`);
  s.run(source);
  return {...s,open:(id=null)=>s.run(`openCollection(${JSON.stringify(id)})`),
    input:(id,text)=>{s.el(id).value=text;s.el(id).emit('input');},
    submit:()=>s.el('#collectionForm').onsubmit({preventDefault(){}}),
    restore:()=>s.el('#restoreCollectionDraft').onclick(),
    inspect:()=>s.el('#inspectCollectionCommand').onclick()};
}
const cases=[
  ['restored field key order does not make reverted values dirty',async()=>{
    const s=page();s.open(A);s.input('#collectionName','Local edit');
    const r=page(s.storage);r.open(A);r.restore();
    assert.deepEqual(Object.keys(r.run('collectionSession.baseline')),['description','name']);
    r.input('#collectionName','Before');
    assert.equal(r.run('collectionDirty()'),false);
    assert.equal(r.el('#saveCollection').disabled,true);
    assert.equal(r.run(`collectionSession.journal.get('${A}')`),null);
    await r.submit();assert.equal(r.writes.length,0);
  }],
  ['reloaded unchanged raw clicked fields normalize after exact status confirmation',async()=>{
    const s=page();s.open();s.input('#collectionName',' Clicked ');
    const waiting=s.submit(),payload=s.payload(0);
    s.writes[0].reject(Error('lost response'));await waiting;
    const r=page(s.storage);r.open();r.restore();
    assert.deepEqual(Object.keys(r.run('collectionSession.pending.clicked_values')),['description','name']);
    const inspecting=r.inspect();r.reads[0].resolve(collectionReceipt(payload,A));await inspecting;
    assert.equal(r.el('#collectionName').value,'Clicked');
    assert.equal(r.run('collectionSession.pending'),null);
    assert.equal(r.run('collectionSession.recovery'),null);
    assert.equal(r.run('collectionDirty()'),false);
    assert.equal(r.writes.length,0);
  }]
];
(async()=>{
  let failed=0;
  for(const [name,run] of cases){try{await run();console.log('PASS',name);}catch(e){failed++;console.error('FAIL',name,e.message);}}
  console.log(JSON.stringify({passed:cases.length-failed,failed}));if(failed)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
