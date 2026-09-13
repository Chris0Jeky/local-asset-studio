'use strict';
const assert = require('node:assert/strict'), {test} = require('node:test'), {createHash, webcrypto} = require('node:crypto');
const C = require('../app/static/workflow-saved-run-core.js');
const hash = x => createHash('sha256').update(x).digest('hex');
function packetFixture(id = 'prep-first', doc = 'document-a') {
  const request = {request_id: id, document_id: doc, expected_revision: 1, preset_id: 'example'};
  const controls_json = '{"seed":9223372036854775807}';
  const ticket_json = '{"format":"studio.run-ticket/v1","request_id":"ticket-a","recipe":{"preset_id":"example","batch_count":1,"controls":'+controls_json+'},"pins":{"backend_id":"primary","graph_sha256":"'+ 'b'.repeat(64)+'"}}';
  const s = {request_id: id, document_id: doc, revision: 1, preset_id: 'example', job_id: 'job-a', document_sha256: 'a'.repeat(64), ticket_sha256: hash(ticket_json)};
  const record_json = JSON.stringify({format: 'studio.document-run/v1', request, report: {ticket_sha256: s.ticket_sha256, document_sha256: s.document_sha256, job_id: s.job_id, recipe: {preset_id:'example', controls: {seed: 'SEED'}}, ticket: {request_id: 'ticket-a'}}}).replace('"SEED"', '9223372036854775807');
  s.record_sha256 = hash(record_json);
  return {source: s, head_revision: 1, source_is_current: true, ticket_json, record_json, controls_json, backend_id: 'primary', prepared_graph_sha256: 'b'.repeat(64), dispatch_attempted: false};
}
class Storage {
  constructor() {this.data = new Map(); this.fail = false;}
  get length() {return this.data.size;}
  key(i) {return [...this.data.keys()][i] || null;}
  getItem(k) {return this.data.get(k) ?? null;}
  setItem(k,v) {if(this.fail)throw Error('storage refused');this.data.set(k,v);}
  removeItem(k) {if(this.fail)throw Error('storage refused');this.data.delete(k);}
}
if (process.env.WORKFLOW_FIXTURE_ONLY !== '1') {
  test('exact review retains large seeds despite parsed-number rounding', async()=>{
    const p=packetFixture(), result=await C.review(p,'prep-first',webcrypto);
    assert.equal(result.ticket_json,p.ticket_json);assert.match(result.controls_json,/9223372036854775807/);
    assert.notEqual(hash(JSON.stringify(JSON.parse(p.ticket_json))),p.source.ticket_sha256);
  });
  test('tampered text, source and head are rejected', async()=>{
    for(const change of [p=>p.ticket_json+=' ',p=>p.record_json+=' ',p=>p.source.document_id='other',p=>p.head_revision=0,p=>p.source_is_current=false,p=>p.controls_json='{}']) {
      const p=packetFixture();change(p);await assert.rejects(()=>C.review(p,'prep-first',webcrypto));
    }
    await assert.rejects(()=>C.review(packetFixture(),'other',webcrypto));
  });
  test('per-request preparation notes survive another tab and a new journal',()=>{
    const s=new Storage(),a=new C.Journal(s),b=new C.Journal(s);
    const value={request_id:'a',document_id:'doc',expected_revision:1,preset_id:'p'};
    a.retain(value);b.retain({...value,request_id:'b'});assert.equal(new C.Journal(s).list().length,2);
    assert.throws(()=>a.retain({...value,preset_id:'other'}));a.complete(value);assert.equal(b.list()[0].request_id,'b');
  });
  test('retention failures and corruption preserve existing evidence',()=>{
    const s=new Storage(),j=new C.Journal(s),v={request_id:'a',document_id:'doc',expected_revision:1,preset_id:'p'};
    s.fail=true;assert.throws(()=>j.retain(v));assert.equal(s.length,0);s.fail=false;j.retain(v);
    s.data.set(C.PREFIX+'a','broken');assert.throws(()=>j.list());assert.equal(s.getItem(C.PREFIX+'a'),'broken');
  });
  test('bounded notes and strict revisions refuse new entries without pruning',()=>{
    const s=new Storage(),j=new C.Journal(s),v={request_id:'a',document_id:'doc',expected_revision:1,preset_id:'p'};
    for(let i=0;i<32;i++)j.retain({...v,request_id:'r'+i});assert.throws(()=>j.retain(v));assert.equal(j.list().length,32);
    for(const r of [true,0,1025,1.5])assert.throws(()=>C.request({...v,expected_revision:r}));
    for(const id of ['..','__proto__','a/b'])assert.throws(()=>C.identifier(id));
  });
  test('last reference is metadata only and never an execution signal',()=>{
    const s=new Storage(),j=new C.Journal(s),p=packetFixture();j.remember(p.source);
    assert.deepEqual(new C.Journal(s).previous(),p.source);assert.equal(s.getItem(C.LAST).includes('ticket_json'),false);
  });
}
module.exports={packetFixture,Storage};
