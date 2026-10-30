// Owner-click prepare/start contracts for production.js; transport is held until explicitly resolved.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{execFileSync}=require('node:child_process');
const read=file=>process.env.PRODUCTION_TEST_BASE_REF?execFileSync('git',['show',process.env.PRODUCTION_TEST_BASE_REF+':'+file],{cwd:path.join(__dirname,'..'),encoding:'utf8'}):fs.readFileSync(path.join(__dirname,'..',file),'utf8');
const source=read('app/static/production.js'),index=read('app/static/index.html');
function harness(){
  const elements=new Map(),requests=[],calls=[];let mounted=null;
  const $=selector=>{if(selector==='#plannerBlock')return mounted;if(!elements.has(selector))elements.set(selector,{innerHTML:'',textContent:'',value:'',open:false,disabled:false,hidden:false,classList:{toggle(){}},querySelectorAll:()=>[],setCustomValidity(message){this.validationMessage=message;},before(el){mounted=el;},showModal(){this.open=true;},close(){this.open=false;this.onclose?.();}});return elements.get(selector);};
  const ctx=vm.createContext({$,esc:String,safeUrl:()=> '#',setInterval(){},showView(){},api:async()=>[],document:{querySelector:$,querySelectorAll:()=>[],createElement:()=>({})},
    post:(url,body)=>{calls.push({url,body});return new Promise((resolve,reject)=>requests.push({url,body,resolve,reject}));},
    selected:{id:'fixture',name:'Fixture',seed:true,steps:true,defaults:{seed:7,steps:20}},uploadInput:async()=>null,uploaded:null,lastUploaded:null,continuationPayload:()=>({}),values:()=>({seed:7,steps:20}),attachedReferencePayload:()=>[],parentAssets:[],recipeTemplateHash:'hash'});
  vm.runInContext(source,ctx);const run=code=>vm.runInContext(code,ctx);
  async function open(kind){if(kind==='comparison'){$('#experimentMinutes').value='30';await run('openComparison()');}else{run('nativeAssets=[{id:"asset",media_type:"image",duration:100,layerName:"Frame"}]');$('#nativeDialog').showModal();$('#nativeKind').value='atlas';}}
  const submit=(kind,start)=>$(kind==='comparison'?'#experimentForm':'#nativeForm').onsubmit({preventDefault(){},submitter:{id:kind==='comparison'?(start?'prepareExperiment':'prepareExperimentOnly'):(start?'prepareNative':'prepareNativeOnly')}});
  return {$,requests,calls,run,open,submit};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('limits are folded; inputs and safety rules stay inside Change',()=>{
  const dialog=index.match(/<dialog id="experimentDialog"[\s\S]*?<\/dialog>/)[0],details=dialog.match(/<details id="experimentLimits"[^>]*>([\s\S]*?)<\/details>/);
  assert.ok(details,'Limits need a native disclosure');assert.doesNotMatch(details[0].split('>')[0],/\bopen\b/);
  assert.match(details[1],/<summary>[\s\S]*Limits:[\s\S]*Change/);
  for(const id of ['experimentBudget','experimentMinutes','experimentBudgetNote'])assert.match(details[1],new RegExp('id="'+id+'"'));
  for(const rule of ['Existing work finishes first','between stages','accepted generation may continue','Branches share this budget'])assert.ok(details[1].includes(rule),rule);
  assert.match(dialog,/id="prepareExperiment"[^>]*>Prepare and start<\/button>/);assert.match(dialog,/id="prepareExperimentOnly"[^>]*>Prepare only<\/button>/);
  assert.match(index,/id="prepareNative"[^>]*>Prepare and start<\/button>/);assert.match(index,/id="prepareNativeOnly"[^>]*>Prepare only<\/button>/);
});
test('default runs equal chosen values times the single seed; manual limits and validity survive',async()=>{
  const h=harness();assert.equal(h.calls.length,0,'Page load sends nothing');await h.open('comparison');
  const count=h.$('#experimentValues').value.split(',').filter(v=>v.trim()).length;
  assert.equal(Number(h.$('#experimentBudget').value),count);assert.equal(count,3);
  assert.equal(h.$('#experimentLimitsSummary').textContent,'Limits: 3 runs · 30 min');
  h.$('#experimentBudget').value='2';h.$('#experimentBudget').oninput();assert.match(h.$('#experimentBudget').validationMessage,/at least 3/);
  h.$('#experimentBudget').oninvalid();assert.equal(h.$('#experimentLimits').open,true,'Invalid folded inputs can receive focus');
  h.$('#experimentBudget').value='9';h.$('#experimentBudget').oninput();h.$('#experimentMinutes').value='12';h.$('#experimentMinutes').oninput();
  assert.equal(h.$('#experimentLimitsSummary').textContent,'Limits: 9 runs · 12 min');assert.equal(h.$('#experimentBudget').validationMessage,'');assert.equal(h.calls.length,0);
});
for(const kind of ['comparison','native']){
  const endpoint=kind==='comparison'?'/api/production':'/api/production-export',dialog=kind==='comparison'?'#experimentDialog':'#nativeDialog',status=kind==='comparison'?'#experimentStatus':'#nativeStatus';
  test(kind+': Prepare only saves without starting',async()=>{const h=harness();await h.open(kind);const wait=h.submit(kind,false);assert.equal(h.requests[0].url,endpoint);h.requests.shift().resolve({id:'prepared'});await wait;assert.equal(h.calls.length,1);});
  test(kind+': explicit prepare/start awaits preparation and starts exactly once',async()=>{const h=harness();await h.open(kind);const wait=h.submit(kind,true);assert.equal(h.calls.length,1);const duplicate=h.submit(kind,true);assert.equal(h.calls.length,1,'Double click does not duplicate preparation');await duplicate;h.requests.shift().resolve({id:'prepared'});await tick();assert.equal(h.requests.length,1);assert.equal(h.requests[0].url,'/api/production/prepared/start');h.requests.shift().resolve({});await wait;assert.equal(h.calls.length,2);});
  test(kind+': failed prepare never starts',async()=>{const h=harness();await h.open(kind);const wait=h.submit(kind,true);h.requests.shift().reject(Error('Prepare refused'));await wait;assert.equal(h.calls.length,1);assert.match(h.$(status).textContent,/Prepare refused/);assert.equal(h.$(dialog).open,true);});
  test(kind+': uncertain start is visible and never retried',async()=>{const h=harness();await h.open(kind);const wait=h.submit(kind,true);h.requests.shift().resolve({id:'prepared'});await tick();assert.equal(h.requests[0]?.url,'/api/production/prepared/start');h.requests.shift().reject(Error('Start outcome uncertain'));await wait;await h.run('refreshProduction(true)');assert.equal(h.calls.length,2);assert.match(h.$('#productionMessage').textContent,/Start outcome uncertain/);});
  for(const change of ['edit','close'])test(kind+': '+change+' during prepare prevents a stale start',async()=>{const h=harness();await h.open(kind);const wait=h.submit(kind,true);if(change==='close')h.$(dialog).close();else h.$(kind==='comparison'?'#experimentForm':'#nativeForm').oninput();h.requests.shift().resolve({id:'late'});await wait;assert.equal(h.calls.length,1);});
}
