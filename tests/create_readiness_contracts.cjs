// Production readiness policy and inspection handler; only DOM/HTTP/time are controlled.
'use strict';
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const U=require('../app/static/studio-core.js');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
function fixture(){
  const elements=new Map(), requests=[], timers=new Map();let timerId=0;
  const element=id=>{if(!elements.has(id))elements.set(id,{value:'',files:[],textContent:'',innerHTML:'',disabled:false,hidden:false,classList:{toggle(){}},addEventListener(){},setAttribute(){}});return elements.get(id);};
  const c=vm.createContext({console,URL,Blob,AbortController,location:{hash:''},setInterval(){},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},
    document:{querySelector:element,querySelectorAll:()=>[],addEventListener(){}},
    fetch(url,options={}){if(!url.startsWith('/api/inspect/'))return new Promise(()=>{});let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});requests.push({url,options,resolve:data=>resolve({ok:true,json:async()=>data}),reject});return promise;}});
  vm.runInContext(source,c);const run=js=>vm.runInContext(js,c);run("selected={id:'A',name:'Recipe A'}");
  return{run,element,requests,timers};
}
const report=name=>({requirements:[{file:name+'.safetensors',present:true}],nodes:[{type:name+'Node'}],graph:{label:name}});
const text=s=>s.element('#dependencies').textContent+' '+s.element('#dependencies').innerHTML;
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log('PASS',name);}catch(e){failed++;console.error('FAIL',name,'\n'+e.stack);}}
(async()=>{
  await test('structured blocker actions use the same policy as legacy readiness',()=>{
    const cases=[{}, {online:false}, {online:null}, {schemaAvailable:false}, {workerAlive:false}, {referencesReady:false}, {missing:['file']}, {backend:'other'}, {switching:true}, {busy:true}, {preset:null}, {preset:{runtime_block:'manual runtime gate'}}];
    for(const item of cases){const input={preset:{id:'A'},online:true,schemaAvailable:true,...item};assert.equal(typeof U.readinessItems,'function');const items=U.readinessItems(input);assert.deepEqual(U.readiness(input),{ready:items.length===0,blockers:items.map(i=>i.message)});assert.ok(items.every(i=>/^[a-z-]+$/.test(i.code)));}
  });
  await test('actions offer navigation, never install/switch/generate dispatch',()=>{
    assert.equal(typeof U.readinessItems,'function');const items=U.readinessItems({preset:null,online:null,schemaAvailable:false,workerAlive:false,referencesReady:false,missing:['x'],switching:true,busy:true});
    const allow=new Set(['recipes','models','dependencies','references',null]);assert.ok(items.every(i=>allow.has(i.action??null)));assert.equal(items.find(i=>i.code==='busy').action,null);assert.equal(items.find(i=>i.code==='references').action,'references');
  });
  await test('starting inspection invalidates the previous count and graph immediately',async()=>{
    const s=fixture();s.element('#dependencyCount').textContent='1 / 1 present';s.element('#nodeList').innerHTML='old';s.element('#graphPreview').textContent='old';const p=s.run('inspectSelected()');
    assert.match(s.element('#dependencyCount').textContent,/Checking/);assert.equal(s.element('#nodeList').innerHTML,'');assert.equal(s.element('#graphPreview').textContent,'');s.requests[0].resolve(report('A'));await p;
  });
  for(const failure of [false,true])await test('A → B rejects old '+(failure?'failure':'success'),async()=>{
    const s=fixture();const a=s.run('inspectSelected()');s.run("selected={id:'B',name:'B'}");const b=s.run('inspectSelected()');s.requests[1].resolve(report('new-B'));await b;
    const before=text(s);failure?s.requests[0].reject(Error('old-A failed')):s.requests[0].resolve(report('old-A'));await a;assert.equal(text(s),before);
  });
  for(const failure of [false,true])await test('A → B → A rejects previous-session '+(failure?'failure':'success'),async()=>{
    const s=fixture();const a=s.run('inspectSelected()');s.run("selected={id:'B',name:'B'}");const b=s.run('inspectSelected()');s.run("selected={id:'A',name:'A again'}");const again=s.run('inspectSelected()');
    s.requests[2].resolve(report('current-A'));await again;s.requests[1].resolve(report('B'));await b;const before=text(s);failure?s.requests[0].reject(Error('old-A error')):s.requests[0].resolve(report('old-A'));await a;assert.equal(text(s),before);assert.equal(s.element('#graphPreview').textContent,JSON.stringify(report('current-A').graph,null,2));
  });
  await test('repeat check supersedes older check of the same recipe',async()=>{
    const s=fixture();const a=s.run('inspectSelected()'),b=s.run('inspectSelected()');s.requests[1].resolve(report('new'));await b;s.requests[0].resolve(report('old'));await a;assert.match(text(s),/new.safetensors/);assert.doesNotMatch(text(s),/old.safetensors/);
  });
  await test('superseded request receives an actual abort signal',async()=>{
    const s=fixture();const a=s.run('inspectSelected()');s.run("selected={id:'B'}");const b=s.run('inspectSelected()');assert.equal(s.requests[0].options.signal?.aborted,true);s.requests[0].resolve(report('old'));s.requests[1].resolve(report('B'));await Promise.all([a,b]);
  });
  await test('failure removes obsolete presence evidence and exposes explicit recheck',async()=>{
    const s=fixture();const a=s.run('inspectSelected()');s.requests[0].resolve(report('A'));await a;const b=s.run('inspectSelected()');s.requests[1].reject(Error('<script>offline</script>'));await b;
    assert.equal(s.element('#dependencyCount').textContent,'Unavailable');assert.match(s.element('#dependencies').innerHTML,/data-inspect-retry/);assert.doesNotMatch(s.element('#dependencies').innerHTML,/<script>/);assert.equal(s.element('#graphPreview').textContent,'');
  });
  await test('deadline releases panel even when transport ignores abort; no retry',async()=>{
    const s=fixture();const p=s.run('inspectSelected()');assert.ok(s.timers.size,'inspection has a finite deadline');[...s.timers.values()][0]();await p;
    assert.equal(s.element('#dependencyCount').textContent,'Unavailable');assert.match(text(s),/timed out/);assert.equal(s.requests[0].options.signal.aborted,true);assert.equal(s.requests.length,1);assert.equal(s.timers.size,0);s.requests[0].resolve(report('too late'));await Promise.resolve();assert.doesNotMatch(text(s),/too late/);
  });
  await test('unknown file presence is never counted as present',async()=>{
    const s=fixture();const p=s.run('inspectSelected()');s.requests[0].resolve({requirements:[{file:'yes',present:true},{file:'unknown',present:null}],nodes:[],graph:{}});await p;assert.equal(s.element('#dependencyCount').textContent,'1 / 2 present');assert.equal(s.timers.size,0);
  });
  console.log(`Create readiness contracts: ${passed} passed, ${failed} failed`);if(failed)process.exitCode=1;
})();
