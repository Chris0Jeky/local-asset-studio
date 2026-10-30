/* Executes the shipped read-only setup history panel against a fake DOM and a fake GET-only API; no browser, no HTTP server. */
const test=require('node:test'),assert=require('node:assert/strict');
const H=require('../app/static/setup-history.js');
const WS='a'.repeat(32),ID='draft-one',HEAD=45,hex=(c,n=64)=>String(c).repeat(n).slice(0,n);
const sha=n=>(String(n).padStart(2,'0')+'ab').repeat(16);
class El{
  constructor(tag,doc){this.tag=tag;this.doc=doc;this.children=[];this.listeners={};this.dataset={};this.attrs={};this.hidden=false;this.disabled=false;this.checked=false;this.open=false;this.own='';}
  set textContent(v){this.own=String(v);this.children=[];}get textContent(){return this.own+this.children.map(c=>typeof c==='string'?c:c.textContent).join('');}
  set innerHTML(_){throw Error('innerHTML must never be used for history values');}
  set id(v){this._id=v;this.doc.ids.set(v,this);}get id(){return this._id;}
  append(...c){this.children.push(...c);}replaceChildren(...c){this.own='';this.children=c;}
  setAttribute(k,v){this.attrs[k]=v;}addEventListener(k,f){(this.listeners[k]??=[]).push(f);}
  fire(k){for(const f of this.listeners[k]||[])f({target:this});}
  click(){if(this.disabled)return;if(this.type==='checkbox')this.checked=!this.checked;this.fire(this.type==='checkbox'?'change':'click');}
  focus(){this.doc.activeElement=this;}
  all(){return this.children.flatMap(c=>typeof c==='string'?[]:[c,...c.all()]);}
  querySelectorAll(sel){assert.equal(sel,'[data-key]');return this.all().filter(n=>n.dataset.key!==undefined);}
}
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));};
function summary(r){return {revision:r,record_sha256:sha(r),draft_sha256:sha(Math.ceil(r/2)),graph_sha256:hex('c'),record_bytes:900+r,preset_id:r>30?'late-preset':'early-preset',backend_id:'primary',input_count:r>40?2:1};}
function server(options={}){
  const calls=[],head=options.head??HEAD;
  const reply=(v,status=200)=>({ok:status<400,status,text:async()=>JSON.stringify(v)});
  const base=()=>({workspace_id:WS,draft_id:ID,head_revision:head,head_record_sha256:sha(head),observation_only:true,dependencies_checked:false,generation_submitted:false,staging_performed:false});
  const side=text=>({sha256:hex('d'),bytes:text.length,preview:text,truncated:false,omitted_bytes:0,redacted:false});
  async function fetch(path,init={}){
    calls.push({path,init});const u=new URL(path,'http://127.0.0.1');const q=Object.fromEntries(u.searchParams);if(options.refuse?.(u,q))return reply({error:options.refuseText||'Refused for the test'},options.status||409);
    if(u.pathname.endsWith('/history')){const before=q.before_revision?+q.before_revision:head+1,limit=+q.limit,revisions=[];for(let r=before-1;r>=1&&revisions.length<limit;r--)revisions.push(summary(r));
      const last=revisions.at(-1)?.revision;return reply({format:'studio.setup-history-page/v2',...base(),limit,revisions,next_before_revision:last>1?last:null,...options.pageEdit});}
    if(u.pathname.endsWith('/compare')){const hostile='<img src=x onerror=alert(1)> & "quote" ‮';
      return reply({format:'studio.setup-history-compare/v2',...base(),left_revision:+q.left,right_revision:+q.right,left_record_sha256:sha(+q.left),right_record_sha256:sha(+q.right),sections:[
        {section:'wording',changed:true,left:side('old '+hostile),right:{...side('new '+hostile),truncated:true,omitted_bytes:77}},
        {section:'controls',changed:false,left:side('{"seed":"1"}'),right:side('{"seed":"1"}')},
        {section:'runtime',changed:true,left:{...side(''),preview:null,redacted:true},right:{...side(''),preview:null,redacted:true}},
        {section:'<b>odd</b>',changed:true,left:side('x'),right:side('y')}]});}
    throw Error('Unexpected request '+path);
  }
  return {fetch,calls};
}
function page(srv,state={workspace_id:WS,draft_id:ID,revision:HEAD}){
  const doc={ids:new Map(),activeElement:null,listeners:{},querySelector(s){return this.ids.get(s.slice(1))||null;},addEventListener(k,f){this.listeners[k]=f;},createElement(t){return new El(t,this);}};
  const panel=new El('section',doc);panel.id='sharedSetupPanel';
  const counts={adopt:0,capture:0,stamp:0,storage:0},frozen=JSON.stringify(state);
  const w={document:doc,AbortController,setTimeout,clearTimeout,fetch:srv.fetch,
    StudioSetupApply:{controller:{state}},
    StudioSetupDraft:{adopt(){counts.adopt++;},capture(){counts.capture++;return {};},stamp(){counts.stamp++;}},
    get localStorage(){counts.storage++;throw Error('history must not touch browser storage');},
    get sessionStorage(){counts.storage++;throw Error('history must not touch browser storage');}};
  H.mount(w);const details=doc.querySelector('#setupHistory');
  const $=id=>doc.querySelector('#'+id),rows=()=>$('setupHistoryList').children;
  const open=async()=>{details.open=true;details.fire('toggle');await settle();};
  return {w,doc,panel,details,counts,state,frozen:()=>JSON.stringify(state)===frozen,$,rows,open,status:()=>$('setupHistoryStatus').textContent,
    boxes:()=>details.all().filter(n=>n.type==='checkbox'),links:()=>details.all().filter(n=>n.tag==='a')};
}
test('opening lists the newest bounded page and follows the explicit continuation twice',async()=>{
  const srv=server(),p=page(srv);await p.open();
  assert.equal(srv.calls.length,1);assert.equal(srv.calls[0].path,'/api/workflow-studio/setup-drafts/'+ID+'/history?workspace_id='+WS+'&limit=20');
  assert.equal(p.rows().length,20);assert.match(p.rows()[0].textContent,/Revision 45 \(current head\)/);assert.match(p.rows()[19].textContent,/Revision 26/);
  assert.match(p.rows()[0].textContent,/Changed from revision 44: draft\./);assert.match(p.rows()[1].textContent,/No draft, preset, backend, graph or input-count difference from revision 43/);
  assert.match(p.rows()[4].textContent,/Changed from revision 40: draft, input files 1 to 2\./);assert.match(p.rows()[14].textContent,/Changed from revision 30: draft, preset early-preset to late-preset\./);
  assert.equal(p.$('setupHistoryOlder').hidden,false);assert.match(p.status(),/Showing 20 of 45 revisions, newest first/);
  p.$('setupHistoryOlder').click();await settle();
  assert.equal(srv.calls[1].path,'/api/workflow-studio/setup-drafts/'+ID+'/history?workspace_id='+WS+'&limit=20&before_revision=26&expected_head=45');
  assert.equal(p.rows().length,40);assert.match(p.rows()[19].textContent,/from revision 25 in this summary/,'the page boundary summary is recomputed once older rows load');
  p.$('setupHistoryOlder').click();await settle();assert.match(srv.calls[2].path,/before_revision=6&expected_head=45/);
  assert.equal(p.rows().length,45);assert.equal(p.$('setupHistoryOlder').hidden,true);assert.match(p.rows()[44].textContent,/First revision\./);
  assert.match(p.status(),/Loaded 5 older revisions; 45 of 45/);
});
test('two selected revisions show the typed comparison with literal escaped text and notes',async()=>{
  const srv=server(),p=page(srv);await p.open();
  assert.equal(p.$('setupHistoryCompare').disabled,true);
  p.boxes()[19].click();assert.equal(p.$("setupHistoryCompare").disabled,true);p.boxes()[0].focus();p.boxes()[0].click();
  assert.equal(p.$('setupHistoryCompare').disabled,false);assert.equal(p.boxes().filter(b=>b.disabled).length,18,'a third selection is refused natively');
  assert.equal(p.doc.activeElement.dataset.key,'pick-45','focus survives the list rebuild');
  p.$('setupHistoryCompare').click();await settle();
  assert.equal(srv.calls.at(-1).path,'/api/workflow-studio/setup-drafts/'+ID+'/compare?workspace_id='+WS+'&left=26&right=45&expected_head=45');
  const view=p.$('setupHistoryComparison'),text=view.textContent;
  assert.match(text,/Revision 26 compared with revision 45/);assert.ok(text.includes('old <img src=x onerror=alert(1)> & "quote" ‮'),'values are shown literally');
  assert.equal(view.all().some(n=>/^(img|b|script)$/.test(n.tag)),false,'no element is ever built from a value');
  assert.match(text,/Wording: changed/);assert.match(text,/Controls: unchanged/);assert.match(text,/Truncated: 77 bytes are not shown\./);
  assert.match(text,/Recorded runtime: changed/);assert.match(text,/Redacted: only the hash and byte length are shown\./);assert.ok(text.includes('<b>odd</b>: changed'));
  assert.doesNotMatch(text,/"seed"/,'unchanged sections show no preview');assert.match(p.status(),/3 of 4 sections differ/);
});
test('each revision offers the existing export route as a plain download link',async()=>{
  const srv=server(),p=page(srv);await p.open();const link=p.links()[0];
  assert.equal(link.href,'/api/workflow-studio/setup-drafts/'+ID+'/export?workspace_id='+WS+'&revision=45');assert.equal(link.attrs.download,'setup-revision-45-inspection.json');
  assert.match(link.textContent,/Download inspection export, revision 45/);assert.equal(srv.calls.length,1,'the link is never followed by the panel');
});
test('an API refusal is shown as text and keeps the list that was already read',async()=>{
  const srv=server({refuse:(u,q)=>!!q.before_revision,refuseText:'Reviewed setup head changed; explicitly restart history inspection'}),p=page(srv);await p.open();
  p.$('setupHistoryOlder').click();await settle();
  assert.match(p.status(),/History could not be read: Reviewed setup head changed; explicitly restart history inspection \(HTTP 409\)\. Nothing was changed\./);
  assert.equal(p.rows().length,20);assert.equal(p.$('setupHistoryOlder').hidden,false);
  const down=page(server({refuse:()=>true,refuseText:'Reviewed setup line not found',status:404}));await down.open();
  assert.match(down.status(),/Reviewed setup line not found \(HTTP 404\)/);assert.equal(down.rows().length,0);
});
test('reads never mutate: GET only, no body, no Create draft, storage or recovery state touched',async()=>{
  const srv=server(),p=page(srv);await p.open();p.$('setupHistoryOlder').click();await settle();p.boxes()[0].click();p.boxes()[1].click();p.$('setupHistoryCompare').click();await settle();p.$('setupHistoryRefresh').click();await settle();
  assert.ok(srv.calls.length>=4);for(const c of srv.calls){assert.equal(c.init.method,undefined);assert.equal(c.init.body,undefined);assert.ok(c.path.startsWith('/api/workflow-studio/setup-drafts/'+ID+'/')&&/\/(history|compare)\?/.test(c.path));}
  assert.deepEqual(p.counts,{adopt:0,capture:0,stamp:0,storage:0});assert.ok(p.frozen(),'the shared setup session state is unchanged');
});
test('without a saved shared revision nothing is requested',async()=>{
  const srv=server(),p=page(srv,{pending:null});await p.open();
  assert.equal(srv.calls.length,0);assert.match(p.status(),/No shared setup revision is saved in this session yet\. Nothing was requested\./);
});
test('malformed or foreign responses are refused instead of rendered',async()=>{
  for(const edit of [{workspace_id:'b'.repeat(32)},{observation_only:false},{generation_submitted:true},{revisions:[{...summary(44)}]},{next_before_revision:3},{format:'studio.setup-history-compare/v2'}]){
    const p=page(server({pageEdit:edit}));await p.open();assert.match(p.status(),/History could not be read/,JSON.stringify(edit));assert.equal(p.rows().length,0);
  }
});
test('a superseded response never overwrites a newer read',async()=>{
  const srv=server(),old=server({head:30});let release;const held=new Promise(r=>release=r);let n=0;
  const p=page({...srv,fetch:async(path,init)=>{if(++n===1){await held;return old.fetch(path,init);}return srv.fetch(path,init);}});
  p.details.open=true;p.details.fire('toggle');p.$('setupHistoryRefresh').click();await settle();release();await settle();
  assert.equal(p.rows().length,20);assert.match(p.status(),/of 45 revisions/);assert.match(p.rows()[0].textContent,/Revision 45/);
});
