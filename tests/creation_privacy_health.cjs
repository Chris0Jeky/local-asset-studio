const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
const start=source.indexOf('async function refreshHealth() {'),end=source.indexOf('\nfunction health()',start);
assert(start>=0&&end>start,'Use the shipped health renderer');
const failure={hidden:true,title:'',textContent:''};
let health={online:true,worker_alive:true,schema_available:true,worker_failure:{private:true,action:'private-work',durable:false,
  message:'A private work failure could not be saved. Open Private history to inspect it before restarting the Studio.',
  id:'PRIVATE-ID-CANARY',recording_error:'PRIVATE-ERROR-CANARY'}};
const context=vm.createContext({api:async()=>health,$:selector=>selector==='#workerFailure'?failure:null,
  selected:null,catalog:null,updateReady(){},message(){}});
vm.runInContext(source.slice(start,end),context);
(async()=>{
  await context.refreshHealth();assert.equal(failure.hidden,false);assert.equal(failure.title,'');
  assert.match(failure.textContent,/private/i);assert.doesNotMatch(JSON.stringify(failure),/PRIVATE-(ID|ERROR)-CANARY|undefined/);
  health={...health,worker_failure:{id:'regular-job-id',action:'generate',durable:false,recording_error:'disk full'}};
  await context.refreshHealth();assert.equal(failure.title,'regular-job-id');assert.match(failure.textContent,/regular-/);
  health={...health,worker_failure:null};await context.refreshHealth();assert.equal(failure.hidden,true);assert.equal(failure.textContent,'');
  console.log('Private and regular health alerts preserve visibility without private diagnostic content');
})().catch(error=>{console.error(error);process.exitCode=1;});
