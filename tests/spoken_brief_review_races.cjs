'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const {ReviewSession} = require('../app/static/spoken-brief-session.js');
const hash = 'a'.repeat(64), audioHash = 'b'.repeat(64), oldBookmark = 'c'.repeat(64), newBookmark = 'd'.repeat(64);
const reportA = 'e'.repeat(64), reportB = 'f'.repeat(64);
function snapshot(key='A') {
  const archive = {chapters_sha256:hash, manifest_sha256:hash, master:{sha256:audioHash, samples:48000}, sample_rate:48000,
    source:{name:key}, segments:[{id:'segment-0001', text:'First.', start_sample:0, end_sample:10000, audio_sha256:audioHash},
      {id:'segment-0002', text:'Second.', start_sample:12000, end_sample:48000, audio_sha256:audioHash}],
    chapters:[{title:'First', start_sample:0, end_sample:12000}, {title:'Second', start_sample:12000, end_sample:48000}]};
  return {archive_sha256:hash, playback_sha256:oldBookmark, archive,
    playback:{manifest_sha256:hash, master_sha256:audioHash, sample:0, rate:1, loop:null},
    reports:[reportA, reportB], reviews:[reportA, reportB], record_refusals:[], record_lists_truncated:false};
}
function acknowledgement(sample=12) {
  return {playback:{...snapshot().playback,sample}, playback_sha256:newBookmark};
}
function record(id=reportA) {
  return {report_sha256:id, review_sha256:id, archive:{manifest_sha256:hash,master_sha256:audioHash},
    targets:[{id:'segment-0001',transcript_status:'match'}], target:'segment-0001', decision:'keep', reviewer:'owner'};
}
function sessionHarness() {
  const requests=[];
  const session=new ReviewSession((route,query,body)=>new Promise((resolve,reject)=>requests.push({route,query,body,resolve,reject})));
  return {session,requests};
}
async function open(h,key='A') {
  const pending=h.session.open(key); h.requests.at(-1).resolve(snapshot(key)); await pending;
}
for (const readFirst of [true,false]) {
  test(`a same-archive inspection overlapping a successful save stays blocked (readFirst=${readFirst})`,async()=>{
    const h=sessionHarness(); await open(h);
    const save=h.session.bookmark({sample:12,rate:1,loop:null}), write=h.requests.at(-1);
    const inspect=h.session.open('A'), read=h.requests.at(-1);
    if (readFirst) { read.resolve(snapshot()); await inspect; write.resolve(acknowledgement()); await save; }
    else { write.resolve(acknowledgement()); await save; read.resolve(snapshot()); await inspect; }
    assert.equal(h.session.blocked(),true,'A pre-save snapshot must not be promoted into a current writable view');
    const count=h.requests.length;
    await assert.rejects(h.session.bookmark({sample:20,rate:1,loop:null}),/Inspect/);
    assert.equal(h.requests.length,count,'Do not send another mutation from the stale view');
    const refresh=h.session.open('A');
    h.requests.at(-1).resolve({...snapshot(),...acknowledgement()}); await refresh;
    assert.equal(h.session.blocked(),false,'A later explicit observation clears the barrier');
    const next=h.session.bookmark({sample:20,rate:1,loop:null});
    assert.equal(h.requests.at(-1).body.expected_playback_sha256,newBookmark);
    h.requests.at(-1).resolve(acknowledgement(20)); await next;
  });
}
test('successful off-screen saves do not block another archive or merge record IDs into it',async()=>{
  const h=sessionHarness(); await open(h);
  const save=h.session.review({target:'master'}), request=h.requests.at(-1);
  await open(h,'B'); request.resolve({id:newBookmark,reused:false}); await save;
  assert.equal(h.session.blocked(),false);
  assert.equal(h.session.current.snapshot.reviews.includes(newBookmark),false);
  await open(h,'A'); assert.equal(h.session.blocked(),false);
});

// Minimal DOM/event fixture executes both shipped scripts. It does not claim native media decoding.
function pageHarness() {
  const elements=new Map(), requests=[];
  class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.value=''; this.checked=false; this.disabled=false;
      this.hidden=false; this.textContent=''; this.dataset={}; this.listeners={}; this.src=''; this.currentSrc='';
      this.readyState=0; this.currentTime=0; this.playbackRate=1; this.paused=true; this.error=null; this.seeking=false; }
    set id(value) { this._id=value; elements.set(value,this); }
    get id() { return this._id; }
    append(...children) { this.children.push(...children); if(this.tagName==='select' && !this.value) this.value=children[0]?.value||''; }
    replaceChildren(...children) { this.children=[]; this.value=''; this.append(...children); }
    set selectedIndex(value) { this.value=this.children[value]?.value||''; }
    setAttribute(key,value) { this[key]=value; }
    removeAttribute(key) { this[key]=''; }
    querySelector() { if(!this.tbody) this.tbody=new Element('tbody'); return this.tbody; }
    cloneNode() { const e=new Element(this.tagName); e.value=this.value; e.textContent=this.textContent; return e; }
    addEventListener(event,listener) { (this.listeners[event] ||= []).push(listener); }
    emit(event) { for(const listener of this.listeners[event]||[]) listener({target:this}); }
    pause() { this.paused=true; }
    load() { this.currentSrc=''; this.readyState=0; this.currentTime=0; this.emit('emptied'); }
    reset() { /* tests set form values explicitly; no simulated persistence or network */ }
  }
  const root=path.join(__dirname,'../app/static');
  for(const [,tag,id] of fs.readFileSync(path.join(root,'spoken-briefs.html'),'utf8').matchAll(/<(\w+)[^>]*\bid="([^"]+)"/g)) {
    const element=new Element(tag); element.id=id;
  }
  const context=vm.createContext({console,URL,URLSearchParams,TextDecoder,Uint8Array,
    document:{baseURI:'http://127.0.0.1:8191/spoken-briefs.html',getElementById:id=>elements.get(id),createElement:tag=>new Element(tag)},
    fetch:(target,options)=>new Promise((resolve,reject)=>{
      const u=new URL(target,'http://127.0.0.1:8191');
      requests.push({route:u.pathname.replace('/api/spoken-briefs',''),query:Object.fromEntries(u.searchParams),
        body:options.body&&JSON.parse(options.body),resolve:value=>resolve(new Response(JSON.stringify(value))),reject});
    })});
  vm.runInContext(fs.readFileSync(path.join(root,'spoken-brief-session.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(root,'spoken-briefs.js'),'utf8'),context);
  const el=id=>elements.get(id);
  async function inspected(key='A') {
    el('archiveList').value=key;
    const pending=el('inspect').onclick(); requests.at(-1).resolve(snapshot(key)); await pending;
  }
  function loaded() { const p=el('player'); p.currentSrc=p.src; p.readyState=1; p.emit('loadedmetadata'); }
  return {el,requests,inspected,loaded};
}
async function page() {
  const h=pageHarness(); h.requests[0].resolve({enabled:true});
  await new Promise(resolve=>setImmediate(resolve)); await h.inspected(); return h;
}
test('bookmark refuses unsettled audio without sending a mutation',async()=>{
  const h=await page(), before=h.requests.length;
  const attempt=h.el('savePosition').onclick();
  if(h.requests.length > before) h.requests.at(-1).resolve(acknowledgement(0));
  await attempt;
  assert.equal(h.requests.length,before,'No bookmark until media metadata/seek belongs to the selected audio');
  assert.equal(h.el('savePosition').disabled,true);
});
test('bookmark refuses a pending chapter seek and saves the settled position only',async()=>{
  const h=await page(); h.loaded();
  h.el('player').readyState=0; h.el('chapters').children[1].children[0].onclick();
  const before=h.requests.length, attempt=h.el('savePosition').onclick();
  if(h.requests.length > before) h.requests.at(-1).resolve(acknowledgement(0));
  await attempt;
  assert.equal(h.requests.length,before,'A pending seek must not save zero as the chapter position');
  h.loaded(); h.el('player').emit('seeked');
  const saved=h.el('savePosition').onclick(), req=h.requests.at(-1);
  assert.equal(req.route,'/bookmark'); assert.equal(req.body.sample,12000);
  req.resolve(acknowledgement(12000)); await saved;
});
test('media errors block bookmarks but do not prevent a separate listening review',async()=>{
  const h=await page(); h.loaded(); h.el('player').error={code:3}; h.el('player').emit('error');
  assert.equal(h.el('savePosition').disabled,true);
  assert.equal(h.el('saveReview').disabled,false);
  const before=h.requests.length; await h.el('savePosition').onclick(); assert.equal(h.requests.length,before);
});
test('changing the report choice clears loaded evidence without requesting or linking another report',async()=>{
  const h=await page(); h.el('reportList').value=reportA;
  const load=h.el('loadReport').onclick(); h.requests.at(-1).resolve(record()); await load;
  h.el('linkReport').checked=true; const before=h.requests.length;
  h.el('reportList').value=reportB; h.el('reportList').onchange();
  assert.equal(h.requests.length,before);
  assert.equal(h.el('linkReport').checked,false); assert.equal(h.el('linkReport').disabled,true);
  assert.equal(h.el('reportDetail').textContent,'No report selected.');
  assert.match(h.el('segments').querySelector('tbody').children[0].children[2].textContent,/Not loaded/);
});
test('changing the report choice invalidates an older in-flight report response',async()=>{
  const h=await page(); h.el('reportList').value=reportA;
  const load=h.el('loadReport').onclick(), req=h.requests.at(-1);
  h.el('reportList').value=reportB; h.el('reportList').onchange(); req.resolve(record()); await load;
  assert.equal(h.el('linkReport').disabled,true);
  assert.equal(h.el('reportDetail').textContent,'No report selected.');
});
test('changing the owner-record choice clears the old judgement and invalidates pending replies',async()=>{
  const h=await page(); h.el('reviewList').value=reportA;
  const first=h.el('loadReview').onclick(); h.requests.at(-1).resolve(record()); await first;
  h.el('reviewList').value=reportB; h.el('reviewList').onchange();
  assert.equal(h.el('reviewDetail').textContent,'No record selected.');
  assert.match(h.el('humanSummary').textContent,/Unreviewed/);
  const second=h.el('loadReview').onclick(), req=h.requests.at(-1);
  h.el('reviewList').value=''; h.el('reviewList').onchange(); req.resolve(record(reportB)); await second;
  assert.equal(h.el('reviewDetail').textContent,'No record selected.');
});
test('saving a separate review preserves the identity of the currently inspected owner record',async()=>{
  const h=await page(); h.el('reviewList').value=reportA;
  const load=h.el('loadReview').onclick(); h.requests.at(-1).resolve(record()); await load;
  h.el('reviewTarget').value='master'; h.el('decision').value='replace'; h.el('reviewer').value='owner'; h.el('reason').value='Separate judgement';
  const saved=h.el('reviewForm').onsubmit({preventDefault(){}});
  h.requests.at(-1).resolve({id:newBookmark,reused:false}); await saved;
  assert.equal(h.el('reviewList').value,reportA,'Displayed owner evidence must keep its selected identity');
  assert.match(h.el('reviewDetail').textContent,new RegExp(reportA));
});
