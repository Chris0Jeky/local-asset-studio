// Typed input and one-shot requests on Create, the gallery and the Asset library survive polls and double clicks.
// Real app.js/workspace.js in a vm; HTTP is recorded and inert. Browser evidence is separate.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const StudioContinuation=require('../app/static/continuation-core.js');
const StudioAssetRecovery=require('../app/static/asset-recovery.js');
const elements=new Map(),requests=[],clicks=[];
const element=s=>{if(!elements.has(s))elements.set(s,{value:'',textContent:'',innerHTML:'',className:'',hidden:false,disabled:false,files:[],dataset:{},
  classList:{toggle(){},add(){},remove(){}},querySelectorAll(){return[];},addEventListener(){},setAttribute(){},focus(){},scrollIntoView(){}});return elements.get(s);};
const REASONS='[data-stop-tracking-reason],[data-abandon-reason],[data-abandon-ack]';
let reasonFields=()=>[],hold=null;
const context=vm.createContext({StudioContinuation,StudioAssetRecovery,URL,Blob,
  document:{querySelector:element,querySelectorAll:s=>s===REASONS?reasonFields():[],addEventListener(name,handler){if(name==='click')clicks.push(handler);}},
  window:{confirm:()=>true},location:{hash:''},setInterval(){},sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}},
  crypto:{randomUUID:()=>'request-id'},
  fetch:async(url,options={})=>{if(url==='/api/catalog')return new Promise(()=>{});
    if(options.method==='POST'){requests.push({url,data:JSON.parse(options.body)});if(hold)await hold;}
    return {ok:true,json:async()=>({message:'ok',setups:[]}),blob:async()=>new Blob(['x'])};}});
for(const name of ['app.js','reference-model.js','references.js','workspace.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
const run=s=>vm.runInContext(s,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
let finished=false;process.on('exit',()=>{if(!finished&&!process.exitCode){console.error('Contract run did not finish: a request was left pending');process.exitCode=1;}});
const gate=()=>{let open;hold=new Promise(resolve=>open=resolve);return()=>{hold=null;open();};};
// A form field inside a Problems card, keyed the way renderJobs keys focus (owner job + tag + class + data attributes).
const field=(tagName,className,dataset,job,type='text')=>({tagName,className,dataset,type,value:'',checked:false,closest:s=>s==='[data-output],[data-problem]'?{dataset:{problem:job}}:null});
const problemFields=()=>[field('INPUT','stopTrackingReason',{stopTrackingReason:'job-1'},'job-1'),field('INPUT','',{abandonReason:''},'job-1'),field('INPUT','',{abandonAck:''},'job-1','checkbox')];

(async()=>{
  run('refresh=async()=>{};loadSetups=async()=>{};refreshLibrary=async()=>{};');
  // 1. A jobs poll rebuilds the Problems markup; typed reasons and the acknowledgement come back.
  const job={id:'job-1',status:'uncertain',preset_name:'Demo',message:'Unknown outcome',outputs:[],prompt_ids:['p1'],can_stop_tracking:true,can_abandon:true,abandon_requires_acknowledgement:true};
  const before=problemFields(),after=problemFields();let call=0;
  before[0].value='ComfyUI was restarted';before[1].value='Not needed any more';before[2].checked=true;
  reasonFields=()=>call++===0?before:after;
  run(`jobs=[${JSON.stringify(job)}];renderJobs();`);
  assert.match(element('#gallery').innerHTML+element('#jobProblems').innerHTML,/Stop tracking|Abandon/,'fixture renders the reason controls');
  assert.equal(after[0].value,'ComfyUI was restarted','stop-tracking reason survives a re-render');
  assert.equal(after[1].value,'Not needed any more','abandon reason survives a re-render');
  assert.equal(after[2].checked,true,'abandon acknowledgement survives a re-render');
  reasonFields=()=>[];

  // 2. 'Recipe defaults' restores the authored settings outside a continuation and keeps the operator's wording.
  const preset={id:'demo',name:'Demo',positive:['1','text'],seed:['1','seed'],steps:['1','steps'],defaults:{positive:'authored words',seed:7,steps:20}};
  run(`catalog=${JSON.stringify({presets:[preset]})};selected=catalog.presets[0];continuationState=null;`);
  element('[data-key="seed"]').value='99';element('[data-key="steps"]').value='44';element('#positive').value='my own words';
  element('#recipeSelect').onchange({target:{value:''}});
  assert.equal(String(element('[data-key="seed"]').value),'7');assert.equal(String(element('[data-key="steps"]').value),'20');
  assert.equal(element('#positive').value,'my own words','Recipe defaults resets settings, not the wording');

  // 3. A double click on Save stores one setup.
  element('#saveName').value='Night market';requests.length=0;let release=gate();
  const first=element('#save').onclick(),second=element('#save').onclick();await tick();
  assert.equal(requests.filter(r=>r.url==='/api/setups').length,1,'second click while saving sends nothing');
  assert.equal(element('#save').disabled,true);release();await Promise.all([first,second]);assert.equal(element('#save').disabled,false);

  // 4. Resume observation and Stop tracking send one request per job while one is in flight.
  const click=(selector,target)=>element('#gallery').onclick({target:{closest:s=>s===selector?target:null}});
  requests.length=0;release=gate();
  const resume={dataset:{job:'job-1'}},resumes=[click('.resume',resume),click('.resume',resume)];await tick();
  assert.equal(requests.filter(r=>r.url.endsWith('/resume')).length,1);release();await Promise.all(resumes);
  requests.length=0;release=gate();
  const stop={dataset:{job:'job-1'},parentElement:{querySelector:()=>({value:'Restarted'})}},stops=[click('.stopTracking',stop),click('.stopTracking',stop)];await tick();
  assert.equal(requests.filter(r=>r.url.endsWith('/stop-tracking')).length,1);release();await Promise.all(stops);

  // 5. A double click on Install sends one install request.
  requests.length=0;release=gate();
  const installs=[run("install('model-a')"),run("install('model-a')")];await tick();
  assert.equal(requests.filter(r=>r.url==='/api/models/install').length,1);release();await Promise.all(installs);

  // 6. Starring a card whose asset left the library explains itself instead of surfacing a TypeError.
  run('assetState.assets=[]');requests.length=0;
  const star={dataset:{assetFavorite:'gone'}};
  for(const handler of clicks)await handler({target:{closest:s=>s==='[data-asset-favorite]'?star:null,dataset:{}}});
  assert.match(element('#assetMessage').textContent,/no longer in the loaded library/);assert.equal(requests.length,0);

  // 7. A reason chip pressed while a detail save is pending says so instead of vanishing.
  element('#assetTags').value='face';run("assetDetailBusy=true;toggleAssetReason('hands')");
  assert.equal(element('#assetTags').value,'face');assert.match(element('#assetDetailStatus').textContent,/still pending/);
  finished=true;console.log('Create input drafts and one-shot requests survive polls and double clicks.');
})().catch(error=>{console.error(error);process.exitCode=1;});
