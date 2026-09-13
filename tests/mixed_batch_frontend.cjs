// Real Gallery renderer/handlers; HTTP is inert. Browser evidence is separate.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const elements=new Map(),requests=[];
const element=s=>{if(!elements.has(s))elements.set(s,{value:'',textContent:'',innerHTML:'',className:'',hidden:false,disabled:false,classList:{toggle(){}},addEventListener(){}});return elements.get(s);};
let reply=async()=>({ok:true,json:async()=>({})}),serial=0;
const context=vm.createContext({document:{querySelector:element,querySelectorAll:()=>[],addEventListener(){}},
  window:{},location:{hash:''},URL,Blob,setInterval(){},sessionStorage:{getItem(){return null;}},
  crypto:{randomUUID:()=>`request-${++serial}`},
  fetch:async(url,options={})=>{if(url==='/api/catalog')return new Promise(()=>{});if(options.method==='POST')requests.push({url,data:JSON.parse(options.body)});return reply(url,options);}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8'),context);
const run=s=>vm.runInContext(s,context);
const summary={revision:'a'.repeat(64),known:[{index:0,prompt_id:'retained',status:'completed'}],unknown_index:1,never_submitted_count:1,
  can_observe:true,can_dispose:true,message:'Unknown tail remains'};
const job={id:'mixed-job',status:'uncertain',preset_name:'Synthetic mixed batch',message:'Needs reconciliation',outputs:[],prompt_ids:['retained'],has_pending_submission:true,mixed_batch:summary};
const render=value=>run(`jobs=[${JSON.stringify(value)}];renderJobs();`);
const reason={value:''},ack={checked:false},box={dataset:{job:job.id,revision:summary.revision},querySelector:s=>s==='[data-mixed-reason]'?reason:s==='[data-mixed-ack]'?ack:null};
const button=action=>({dataset:{mixedAction:action,job:job.id},disabled:false,closest:s=>s==='.mixedBatchControls'?box:null});
const event=b=>({target:{closest:s=>s==='[data-mixed-action]'?b:null}});
(async()=>{
  render(job);
  assert.match(element('#gallery').innerHTML,/Check known batch receipts/);
  assert.match(element('#gallery').innerHTML,/Abandon remaining batch locally/);
  assert.match(element('#gallery').innerHTML,/not cancel/);
  assert.equal(requests.length,0,'Rendering cannot issue commands');
  run('refresh=async()=>{}');
  const dispose=button('dispose');await element('#gallery').onclick(event(dispose));assert.equal(requests.length,0);
  reason.value='Keep this receipt';await element('#gallery').onclick(event(dispose));assert.equal(requests.length,0);
  ack.checked=true;
  let release;reply=()=>new Promise(resolve=>release=()=>resolve({ok:true,json:async()=>({})}));
  const first=element('#gallery').onclick(event(dispose));await Promise.resolve();
  await element('#gallery').onclick(event(dispose));assert.equal(requests.length,1,'Double click cannot duplicate a command');
  release();await first;
  assert.equal(requests[0].url,'/api/jobs/mixed-job/dispose-mixed');assert.equal(requests[0].data.acknowledge_unknown,true);
  assert.equal(requests[0].data.expected_revision,summary.revision);assert.equal(dispose.disabled,false);
  const observe=button('observe');reply=async()=>{throw Error('Response lost');};
  await element('#gallery').onclick(event(observe));const lost=requests.at(-1);
  reply=async()=>({ok:true,json:async()=>({})});await element('#gallery').onclick(event(observe));
  assert.deepEqual(requests.at(-1),lost,'Manual retry after response loss must retain exact request identity');
  assert.equal(requests.some(r=>r.url==='/api/jobs'),false,'Recovery never generates');
  render({...job,mixed_batch:{...summary,can_observe:false,can_dispose:false}});
  assert.match(element('#gallery').innerHTML,/data-mixed-action="observe"[^>]*disabled/);
  assert.match(element('#gallery').innerHTML,/data-mixed-action="dispose"[^>]*disabled/);
  render({...job,mixed_batch:{can_observe:false,can_dispose:false,message:'Malformed retained receipt'}});
  assert.doesNotMatch(element('#gallery').innerHTML,/data-mixed-action=/);
  console.log('Mixed Gallery recovery requires explicit consent, current evidence, and exact command identity.');
})().catch(error=>{console.error(error);process.exitCode=1;});
