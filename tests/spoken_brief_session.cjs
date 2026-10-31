'use strict';
const assert = require('node:assert/strict');
const {ReviewSession, SourcePreviewSession} = require('../app/static/spoken-brief-session.js');
const digest = 'a'.repeat(64), other = 'b'.repeat(64), revision = 'c'.repeat(64);
function snapshot(key) {
  return {archive_sha256:digest, playback_sha256:revision, reports:[], reviews:[],
    archive:{chapters_sha256:digest, manifest_sha256:digest, master:{sha256:other,samples:48000},
      sample_rate:48000, segments:[], chapters:[], source:{name:key}},
    playback:{manifest_sha256:digest,master_sha256:other,sample:0,rate:1,loop:null}};
}
function harness() {
  const requests=[];
  const s=new ReviewSession((route,query,body)=>new Promise((resolve,reject)=>requests.push({route,query,body,resolve,reject})));
  return {s,requests};
}
async function opened(h,key='A') {const done=h.s.open(key); h.requests.at(-1).resolve(snapshot(key)); await done;}
async function run() {
  {
    const h=harness(); assert.equal(h.requests.length,0);
    const a=h.s.open('A'), b=h.s.open('B'); h.requests[1].resolve(snapshot('B')); await b;
    h.requests[0].resolve(snapshot('A')); assert.equal(await a,null); assert.equal(h.s.current.key,'B');
  }
  {
    const h=harness(); const a=h.s.open('A'),b=h.s.open('B'); h.requests[1].reject(Error('offline'));
    await assert.rejects(b); h.requests[0].resolve(snapshot('A')); await a; assert.equal(h.s.current,null);
  }
  {
    const h=harness(); await opened(h); const write=h.s.bookmark({sample:12,rate:1,loop:null});
    await assert.rejects(h.s.bookmark({sample:19,rate:1,loop:null}),/Inspect|progress/);
    assert.equal(h.requests.length,2); assert.equal(h.requests[1].body.expected_playback_sha256,revision);
    await opened(h,'B'); h.requests[1].resolve({playback:{...snapshot('A').playback,sample:12},playback_sha256:other});
    assert.equal((await write).current,false); assert.equal(h.s.current.key,'B'); assert.equal(h.s.current.snapshot.playback.sample,0);
  }
  {
    const h=harness(); await opened(h); const write=h.s.bookmark({sample:12,rate:1,loop:null});
    const oldRead=h.s.open('A'); h.requests[1].reject(Error('response lost')); await assert.rejects(write);
    h.requests[2].resolve(snapshot('A')); await oldRead;
    await assert.rejects(h.s.bookmark({sample:12,rate:1,loop:null}),/Inspect/);
    await opened(h); const retry=h.s.bookmark({sample:13,rate:1,loop:null});
    h.requests.at(-1).resolve({playback:{...snapshot('A').playback,sample:13},playback_sha256:other}); await retry;
    assert.equal(h.s.current.snapshot.playback_sha256,other);
  }
  {
    const h=harness(); await opened(h); const write=h.s.bookmark({sample:12,rate:1,loop:null});
    h.requests.at(-1).resolve({playback:{...snapshot('A').playback,master_sha256:digest,sample:12},playback_sha256:other});
    await assert.rejects(write,/identity|acknowledgement/); assert.equal(h.s.current.snapshot.playback.sample,0);
  }
  {
    const h=harness(); await opened(h); const a=h.s.report(digest), b=h.s.report(other);
    h.requests.at(-1).resolve({report_sha256:other,archive:{manifest_sha256:digest,master_sha256:other}}); await b;
    h.requests[1].resolve({report_sha256:digest,archive:{manifest_sha256:digest,master_sha256:other}}); assert.equal(await a,null); assert.equal(h.s.reportValue.report_sha256,other);
    const later=h.s.report(digest); await opened(h,'B'); h.requests[3].resolve({report_sha256:digest,archive:{manifest_sha256:digest,master_sha256:other}});
    assert.equal(await later,null); assert.equal(h.s.reportValue,null);
  }
  {
    const h=harness(); await opened(h); const body={target:'segment-0001',audio_sha256:digest,decision:'replace',
      findings:{pronunciation:'needs-work'},reviewer:'owner',reason:'first',report_sha256:null};
    const write=h.s.review(body); body.reason='new text while saving';
    assert.equal(h.requests.at(-1).body.reason,'first'); assert.equal(h.requests.at(-1).body.archive_sha256,digest);
    h.requests.at(-1).resolve({id:other,reused:false,generation_submitted:false}); const result=await write;
    assert.equal(result.current,true); assert.equal(body.reason,'new text while saving');
    assert.deepEqual(h.s.current.snapshot.reviews,[other]);
  }
  {
    const h=harness(); await opened(h); const a=h.s.savedReview(digest); await opened(h,'B');
    h.requests[1].resolve({review_sha256:digest,archive:{manifest_sha256:digest,master_sha256:other}}); assert.equal(await a,null);
  }
  {
    const requests = [], s = new SourcePreviewSession((route, query, body) => new Promise((resolve, reject) => requests.push({route,query,body,resolve,reject})));
    assert.equal(requests.length, 0);
    s.invalidate(); assert.equal(requests.length, 0);
    await assert.rejects(s.preview('.'), /Refresh/);
    const refresh = s.refresh(); requests.at(-1).resolve({enabled:true,source_root_id:digest}); await refresh;
    const value = {root_id:digest,manifest:{source:{sha256:other},segments:[{text:'Fictional'}],omissions:{}},batch_count:1,generation_submitted:false};
    const a = s.preview('A'), aRequest = requests.at(-1);
    s.invalidate(); // A -> B -> A still invalidates the first A.
    const b = s.preview('A'); requests.at(-1).resolve(value); assert.deepEqual(await b, value);
    aRequest.resolve(value); assert.equal(await a, null);
    const stale = s.preview('A'), staleRequest = requests.at(-1);
    s.invalidate(); staleRequest.reject(Error('Old refusal')); assert.equal(await stale, null);
    const oldRoot = s.preview('A'), oldRootRequest = requests.at(-1);
    const firstRoot = s.refresh(), firstRequest = requests.at(-1), secondRoot = s.refresh();
    requests.at(-1).resolve({enabled:true,source_root_id:other}); await secondRoot;
    firstRequest.resolve({enabled:true,source_root_id:digest}); assert.equal(await firstRoot, null);
    oldRootRequest.resolve(value); assert.equal(await oldRoot, null); assert.equal(s.root, other);
    const wrong = s.preview('A'); requests.at(-1).resolve(value); await assert.rejects(wrong, /identity/);
    const disabled = s.refresh(); requests.at(-1).resolve({enabled:false,source_root_id:null}); await disabled;
    await assert.rejects(s.preview('A'), /Refresh/);
    assert.ok(requests.every(r => r.body === undefined));
  }
  console.log('Spoken Brief archive and source-preview ownership scenarios passed');
}
run().catch(e=>{console.error(e); process.exitCode=1;});
