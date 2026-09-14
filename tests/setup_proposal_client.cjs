const {test}=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const C=require('../app/static/setup-proposal.js');
const hashText=async text=>crypto.createHash('sha256').update(text).digest('hex');
const q={goal:'reference-image',preset_id:'roles',expected_template_sha256:'b'.repeat(64),sources:[{asset_id:'a',sha256:'c'.repeat(64),role:'identity'}],draft:{version:1,updatedAt:0,templateHash:null,pendingInputs:[],recipe:{preset:'old',controls:{positive:'my brief',seed:'9223372036854775807'},batch:1,references:[],parent_assets:[],parent_by_input:{}}},positive:'my brief',negative:'',guidance:[{contribution:'face',avoid:'costume'}]};
async function report(query=q){const body={format:'studio.setup-proposal/v1',request:structuredClone(query),before:structuredClone(query.draft),intent:{preset_id:query.preset_id,template_sha256:query.expected_template_sha256,controls:{positive:query.positive,seed:'9223372036854775807'},batch:1,sources:query.sources.map((s,i)=>({...s,...query.guidance[i],slot:i+1,staged:false,transform:{policy:'native'},binding:['1','image']})),lineage:{parents:['a'],by_input:{reference:'a'},source_slots:[]}},precondition:{draft_sha256:'f'.repeat(64),scope:'caller-declared browser draft; not a server revision'},diff:[],observation:{candidate:{checks:[]}},side_effects:[],limits:[],can_apply:false,generation_submitted:false,execution_authorized:false};body.diff=diff(query.draft,body.intent);const exact=JSON.stringify(body);return {...body,proposal_json:exact,proposal_sha256:await hashText(exact)};}
function diff(before,intent){const r=before.recipe;return [
 ['Recipe',{preset:r.preset,template:before.templateHash},{preset:intent.preset_id,template:intent.template_sha256}],
 ['Settings and wording',r.controls,intent.controls],['Batch',r.batch,intent.batch],['References',r.references,intent.sources],
 ['Lineage',{parents:r.parent_assets,by_input:r.parent_by_input},intent.lineage],
 ['Continuation context',r.continuation??null,null],['Pending local inputs',before.pendingInputs,[]]
 ].map(([section,before,proposed])=>({section,before,proposed,changed:!C.same(before,proposed)}));}
async function reseal(r){const {proposal_sha256,proposal_json,...body}=r,exact=JSON.stringify(body);return {...body,proposal_json:exact,proposal_sha256:await hashText(exact)};}
test('self-consistent envelopes cannot rewrite negative wording, contributions or the review diff',async()=>{
 for(const mutate of [r=>r.intent.controls.negative='unrequested text',r=>r.intent.controls.reference='hidden.png',r=>r.intent.sources[0].contribution='different face',r=>r.intent.sources[0].avoid='different costume',r=>r.diff[1].changed=!r.diff[1].changed,r=>r.diff[1].proposed={positive:'invented'}]){
  const r=await report();mutate(r);const resealResult=await reseal(r);await assert.rejects(()=>C.validate(resealResult,q,hashText));
 }
});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
test('exact review bytes and request context both match',async()=>{const r=await report();assert.equal(await C.validate(r,q,hashText),r)});
test('changed exact bytes, request, source slots and authority refuse',async()=>{
 for(const mutate of [r=>r.proposal_json+=' ',r=>r.before.recipe.controls.positive='other',r=>r.can_apply=true,r=>r.intent.sources[0].slot=2,r=>r.request.sources[0].role='style']){
  const r=await report();mutate(r);await assert.rejects(()=>C.validate(r,q,hashText));
 }
});
test('request snapshot cannot be changed by caller while in flight',async()=>{
 const gate=deferred(),events=[],query=structuredClone(q);let captured;
 const s=new C.Session((v)=>{captured=v;return gate.promise},()=>true,e=>events.push(e),{hashText});
 const pending=s.load(query);query.sources[0].role='style';query.draft.recipe.controls.positive='modified';
 gate.resolve(await report(captured));await pending;
 assert.equal(events.at(-1).report.request.sources[0].role,'identity');assert.equal(events.at(-1).report.before.recipe.controls.positive,'my brief');
});
test('changed draft or A to B to A does not revive a late report',async()=>{
 const gate=deferred(),events=[];let matches=true,signal;
 const s=new C.Session((_,sg)=>{signal=sg;return gate.promise},()=>matches,e=>events.push(e),{hashText});
 const pending=s.load(q);s.invalidate('draft changed');s.invalidate('draft restored');gate.resolve(await report());await pending;
 assert.equal(signal.aborted,true);assert.equal(events.filter(e=>e.report).length,0);
 const s2=new C.Session(async()=>{matches=false;return report()},()=>matches,e=>events.push(e),{hashText});
 await s2.load(q);assert.equal(events.filter(e=>e.report).length,0);
});
test('deadline releases even when transport ignores abort, without a retry',async()=>{
 let fire,calls=0;const gate=deferred(),events=[];
 const s=new C.Session(()=>{calls++;return gate.promise},()=>true,e=>events.push(e),{hashText,set:fn=>{fire=fn;return 1},clear:()=>{}});
 const pending=s.load(q);await s.load(q);fire();assert.equal(s.busy,false);gate.resolve(await report());await pending;
 assert.equal(calls,1);assert.equal(events.filter(e=>e.report).length,0);assert.match(events.at(-1).message,/timed out/);
});
test('state change during asynchronous hash verification also refuses',async()=>{
 const gate=deferred(),events=[];let matches=true;
 const r=await report(),s=new C.Session(async()=>r,()=>matches,e=>events.push(e),{hashText:()=>gate.promise});
 const pending=s.load(q);await new Promise(resolve=>setImmediate(resolve));matches=false;gate.resolve(r.proposal_sha256);await pending;
 assert.equal(events.filter(e=>e.report).length,0);
});
test('plain JSON comparison preserves keys and wide integer strings',()=>{
 assert(C.same({b:1,a:'9223372036854775807'},{a:'9223372036854775807',b:1}));
 assert(!C.same({a:'9223372036854775807'},{a:'9223372036854775806'}));
 assert(!C.same({a:null},{}));
});
