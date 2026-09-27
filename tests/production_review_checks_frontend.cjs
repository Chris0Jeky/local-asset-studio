// #1203: comparison candidates carry the same quick checks as Combine tiles. Execute the real Production renderer and
// handler: each candidate shows its route's checks and a count from owner answers; a press saves one answer through the
// ordinary guarded asset update and changes nothing about the study itself.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),requests=[],updates=[],messages=[];
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const assetState={workspace_id:'1'.repeat(32),assets:[
  {id:'asset-a',media_type:'image',preset_id:'anima-portrait',tags:['hero','check:style=yes','check:clean=no'],metadata_revision:2},
  {id:'asset-b',media_type:'image',preset_id:'anima-portrait',tags:[],metadata_revision:0}]};
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},assetState,
  catalog:{presets:[{id:'anima-portrait'}]},api:async()=>[],post:async(url,data)=>{requests.push({url,data});return {};},
  refreshAssets:async()=>{if(!assetState.assets.some(a=>a.id==='asset-c'))assetState.assets.push({id:'asset-c',media_type:'image',preset_id:'anima-portrait',tags:['late'],metadata_revision:0});return true;},mutateAssets:async payload=>{updates.push(JSON.parse(JSON.stringify(payload)));const a=assetState.assets.find(x=>x.id===payload.ids[0]);a.tags=payload.tags;a.metadata_revision++;return {status:'applied'};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/review-checks.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const stage=(label,asset)=>({label,operation:'generate',job:{id:'job-'+label,preset_id:'anima-portrait',status:'completed',outputs:[{asset_id:asset,media_type:'image',seed:42}]}});
const plan={id:'c'.repeat(32),name:'Lantern keeper',kind:'comparison',axis:'cfg',values:[3.5,5],budget:{reserved:2,allowance:4},created_at:1790000000,
  stages:[stage('A','asset-a'),stage('B','asset-b'),stage('C','asset-c')],state:{status:'awaiting_review',message:'Finished'}};
vm.runInContext(`productionPlans=${JSON.stringify([plan])};productionId=${JSON.stringify(plan.id)};renderProduction();`,context);
(async()=>{
  let html=$('#productionDetail').innerHTML;
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
  console.log('Comparison quick checks save one owner answer per press and count them per candidate.');
})().catch(error=>{console.error(error);process.exitCode=1;});
