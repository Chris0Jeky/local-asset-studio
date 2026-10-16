// #1203: comparison candidates carry the same quick checks as Combine tiles. Execute the real Production renderer and
// handler: each candidate shows its route's checks and a count from owner answers; a press saves one answer through the
// ordinary guarded asset update and changes nothing about the study itself.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),requests=[],updates=[],messages=[];
let mutateGate=null,mutateError=null;
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const assetState={workspace_id:'1'.repeat(32),assets:[
  {id:'asset-a',media_type:'image',preset_id:'anima-portrait',tags:['hero','check:style=yes','check:clean=no'],metadata_revision:2},
  {id:'asset-b',media_type:'image',preset_id:'anima-portrait',tags:[],metadata_revision:0}]};
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},assetState,
  catalog:{presets:[{id:'anima-portrait'}]},api:async()=>[],post:async(url,data)=>{requests.push({url,data});return {};},
  refreshAssets:async()=>{if(!assetState.assets.some(a=>a.id==='asset-c'))assetState.assets.push({id:'asset-c',media_type:'image',preset_id:'anima-portrait',tags:['late'],metadata_revision:0});return true;},mutateAssets:async payload=>{updates.push(JSON.parse(JSON.stringify(payload)));const a=assetState.assets.find(x=>x.id===payload.ids[0]);a.tags=payload.tags;a.metadata_revision++;if(mutateGate)await mutateGate;if(mutateError){const err=mutateError;mutateError=null;throw err;}return {status:'applied'};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/review-checks.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const stage=(label,asset)=>({label,operation:'generate',job:{id:'job-'+label,preset_id:'anima-portrait',status:'completed',outputs:[{asset_id:asset,media_type:'image',seed:42}]}});
const plan={id:'c'.repeat(32),name:'Lantern keeper',kind:'comparison',axis:'cfg',values:[3.5,5],budget:{reserved:2,allowance:4},created_at:1790000000,
  stages:[stage('A','asset-a'),stage('B','asset-b'),stage('C','asset-c')],state:{status:'awaiting_review',message:'Finished'}};
vm.runInContext(`productionPlans=${JSON.stringify([plan])};productionId=${JSON.stringify(plan.id)};renderProduction();`,context);
(async()=>{
  let html=$('#productionDetail').innerHTML;
  assert.deepEqual([...html.matchAll(/data-candidate-check="(\w+)" data-asset="asset-c"/g)].map(m=>m[1]),['style','anatomy','composition','clean'],'asset-c has its four chips on the first render, before any refresh');
  assert.match(html,/<p class="muted candidate-check-count">style 1\/1 · clean 0\/1<\/p>/,'candidate A counts its owner answers');
  assert.equal((html.match(/candidate-check-count/g)||[]).length,1,'candidate B has no answers, so no count');
  assert.deepEqual([...html.matchAll(/data-candidate-check="(\w+)" data-asset="asset-b"/g)].map(m=>m[1]),['style','anatomy','composition','clean']);
  assert.match(html,/class="review-check is-yes" data-candidate-check="style" data-asset="asset-a"/);
  assert.match(html,/data-candidate-review="selected" data-candidate-asset="asset-b">Keeper</,'Keeper stays beside the checks');
  const chip={dataset:{candidateCheck:'anatomy',asset:'asset-b'}},event={target:{closest:s=>s==='[data-candidate-check]'?chip:null}};
  await $('#productionDetail').onclick(event);
  assert.deepEqual(updates,[{ids:['asset-b'],action:'edit',tags:['check:anatomy=yes']}],'one guarded tags update per press, nothing else');
  assert.equal(requests.length,0,'the study itself is not written');
  assert.match($('#productionMessage').textContent,/Saved for this candidate: anatomy yes\. The comparison outcome is unchanged\./);
  html=$('#productionDetail').innerHTML;
  assert.match(html,/<p class="muted candidate-check-count">anatomy 1\/1<\/p>/,'the count updates after the save');
  // Codex on #1212: a candidate that finished after the last Workspace read still has chips; a press reads fresh tags first.
  assert.equal((html.match(/data-candidate-check="\w+" data-asset="asset-c"/g)||[]).length,4);
  await $('#productionDetail').onclick({target:{closest:s=>s==='[data-candidate-check]'?{dataset:{candidateCheck:'clean',asset:'asset-c'}}:null}});
  assert.deepEqual(updates[1],{ids:['asset-c'],action:'edit',tags:['late','check:clean=yes']},'the other tags read after the refresh survive');
  // #1211 M1: a second press while the first save is still in flight must not read or write.
  const pending=updates.length;let release;mutateGate=new Promise(resolve=>{release=resolve;});
  const again={dataset:{candidateCheck:'clean',asset:'asset-c'}};
  const detail=$('#productionDetail');
  const press=()=>detail.onclick({target:{closest:s=>s==='[data-candidate-check]'?again:null}});
  const first=press();const second=press();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(updates.length,pending+1,'exactly one update is recorded while the first save is pending');
  assert.equal($('#productionMessage').textContent,'Still saving the last answer. Press again in a moment. Nothing was changed.');
  release();mutateGate=null;await first;await second;
  await press();
  assert.equal(updates.length,pending+2,'a press after the first save settles records its own update');
  assert.match($('#productionMessage').textContent,/Saved for this candidate: clean /);
  mutateError=Error('save refused');const refused=updates.length;
  await press();
  assert.equal(updates.length,refused+1,'the refused save is the call that rejected');
  assert.equal($('#productionMessage').textContent,'save refused');
  await press();
  assert.equal(updates.length,refused+2,'a refused save releases the busy flag so a later press works');
  assert.match($('#productionMessage').textContent,/Saved for this candidate: clean /);
  // #1211: key 2 presses candidate B's anatomy chip. The $() stub has no querySelectorAll, so the event carries the candidate.
  const saved=updates.length;
  assetState.assets.find(a=>a.id==='asset-b').tags=[];
  const checks=['style','anatomy','composition','clean'].map(name=>({disabled:false,dataset:{candidateCheck:name,asset:'asset-b'},click(){return $('#productionDetail').onclick({target:{closest:s=>s==='[data-candidate-check]'?this:null}});}}));
  const candidate={querySelectorAll:s=>s==='[data-candidate-check]'?checks:[]};
  const key=target=>({key:'2',preventDefault(){this.defaultPrevented=true;},target});
  const listen=$('#productionDetail').onkeydown;
  // The save re-renders the detail: focus returns to the same chip so the next key still lands (#1386 Codex P2).
  let refocused=null;const rerendered=['style','anatomy'].map(name=>({dataset:{candidateCheck:name,asset:'asset-b'},focus(){refocused=name;}}));
  $('#productionDetail').querySelectorAll=s=>s==='[data-candidate-check]'?rerendered:[];
  if(typeof listen==='function')await listen(key({tagName:'BUTTON',closest:s=>s==='article.candidate'||s==='.candidate'?candidate:null}));
  assert.deepEqual(updates[saved],{ids:['asset-b'],action:'edit',tags:['check:anatomy=yes']},'key 2 on candidate B reaches the anatomy chip and saves the same guarded tags update as a click');
  assert.equal(updates.length,saved+1,'one key press saves one answer');
  assert.equal(refocused,'anatomy','focus returns to the re-rendered chip that was pressed');
  delete $('#productionDetail').querySelectorAll;
  // A refused save on the key path is shown like a click's, not dropped as an unhandled rejection.
  mutateError=Error('key save refused');$('#productionMessage').textContent='';
  if(typeof listen==='function')await listen(key({tagName:'BUTTON',closest:s=>s==='article.candidate'||s==='.candidate'?candidate:null}));
  assert.equal($('#productionMessage').textContent,'key save refused','a refused key save shows its error');
  const typed=updates.length;
  if(typeof listen==='function')await listen(key({tagName:'TEXTAREA',id:'productionNotes',closest:s=>s==='article.candidate'||s==='.candidate'?candidate:null}));
  assert.equal(updates.length,typed,'a key typed in a notes/input target does not save');
  // Blind comparison: the recipe and full-plan downloads carry the settings, so they stay hidden until Reveal.
  assetState.assets.find(a=>a.id==='asset-b').tags=[];
  const blindHtml=$('#productionDetail').innerHTML;
  assert.equal((blindHtml.match(/data-job-recipe=/g)||[]).length,0,'blind: no candidate recipe download is offered');
  assert.equal((blindHtml.match(/Recipe hidden while comparing blind/g)||[]).length,3,'blind: each candidate says why its recipe is hidden');
  assert.doesNotMatch(blindHtml,/plan\.json\?download/,'blind: the full plan download is hidden too');
  assert.match(blindHtml,/Full plan hidden while comparing blind/);
  // Muse B: a second Keeper press on one candidate while its save is in flight records no second update and no false failure.
  const beforeKeeper=updates.length;let releaseKeeper;mutateGate=new Promise(resolve=>{releaseKeeper=resolve;});
  const keeper={dataset:{candidateReview:'selected',candidateAsset:'asset-b'}};
  const pressKeeper=()=>$('#productionDetail').onclick({target:{closest:s=>s==='[data-candidate-review]'?keeper:null}});
  const keeperFirst=pressKeeper(),keeperSecond=pressKeeper();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(updates.length,beforeKeeper+1,'a second Keeper press while the first save is pending records no update');
  assert.equal($('#productionMessage').textContent,'Still saving the last mark for this candidate. Press again in a moment. Nothing was changed.');
  releaseKeeper();mutateGate=null;await keeperFirst;await keeperSecond;
  assert.match($('#productionMessage').textContent,/Marked as a keeper in your Workspace/,'the first save reports its own success');
  assert.doesNotMatch($('#productionMessage').textContent,/Still saving|Resolve the earlier library update/,'no failure is reported for the save that succeeded');
  await pressKeeper();
  assert.equal(updates.length,beforeKeeper+2,'a Keeper press after the save settles records its own update');
  assetState.assets.find(a=>a.id==='asset-b').tags=[];
  // Muse C: an overlapping plan action says so instead of doing nothing.
  const startButton={dataset:{projectAction:'start'},disabled:false};
  vm.runInContext('productionActionPending=true;',context);
  const sentBefore=requests.length;$('#productionMessage').textContent='';
  await $('#productionDetail').onclick({target:{closest:s=>s==='[data-project-action]'?startButton:null}});
  assert.equal($('#productionMessage').textContent,'Wait for the current action to finish. Nothing was sent.','an overlapping plan action is explained, not swallowed');
  assert.equal(requests.length,sentBefore,'the overlapping action sends nothing');
  assert.equal(startButton.disabled,false,'the overlapping action leaves the running button alone');
  vm.runInContext('productionActionPending=false;',context);
  // Muse D: a candidate video has an accessible name that matches its visible heading and never leaks the hidden settings.
  const videoPlan={...plan,id:'d'.repeat(32),stages:[1,2].map(n=>({label:n===1?'A':'B',operation:'generate',job:{id:'job-v'+n,preset_id:'anima-portrait',status:'completed',outputs:[{asset_id:'asset-v'+n,media_type:'video'}]}}))};
  vm.runInContext(`productionPlans=${JSON.stringify([videoPlan])};productionId=${JSON.stringify(videoPlan.id)};renderProduction();`,context);
  let videoHtml=$('#productionDetail').innerHTML;
  assert.match(videoHtml,/<video src="\/api\/assets\/asset-v1\/file" controls preload="metadata" aria-label="Candidate A"><\/video>/,'candidate video is named like its heading');
  assert.match(videoHtml,/<video src="\/api\/assets\/asset-v2\/file" controls preload="metadata" aria-label="Candidate B"><\/video>/);
  assert.doesNotMatch(videoHtml,/cfg 3\.5|cfg 5/,'blind: the video name does not reveal the varied setting');
  // Reveal restores the recipe and full-plan downloads.
  vm.runInContext('blindComparison=false;renderProduction();',context);
  videoHtml=$('#productionDetail').innerHTML;
  assert.equal((videoHtml.match(/data-job-recipe="job-v\d"/g)||[]).length,2,'revealed: each candidate recipe is offered again');
  assert.match(videoHtml,/plan\.json\?download/,'revealed: the full plan download is offered again');
  vm.runInContext('blindComparison=true;',context);
  console.log('Comparison quick checks save one owner answer per press and count them per candidate.');
})().catch(error=>{console.error(error);process.exitCode=1;});
