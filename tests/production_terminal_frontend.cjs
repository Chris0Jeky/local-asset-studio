// Execute the actual Production renderer/actions without claiming browser coverage.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),requests=[];
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},
  api:async()=>[],post:async(url,data)=>{requests.push({url,data});return {};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const project={id:'b'.repeat(32),name:'Retained observation',kind:'comparison',budget:{reserved:2,allowance:2},
  stages:[{label:'A',operation:'generate',attempt:{},job:{id:'retained-job',status:'failed',outputs:[],prompt_ids:['known'],tracking_disposition:{status:'resumed',history:[{status:'stopped'}]}}}],
  state:{status:'uncertain',message:'Inspection required'},can_reconcile_tracking:true};
const render=value=>vm.runInContext(`productionPlans=[${JSON.stringify(value)}];productionId=${JSON.stringify(project.id)};renderProduction();`,context);
(async()=>{
  for(const status of ['failed','partial']){
    render({...project,stages:[{...project.stages[0],job:{...project.stages[0].job,status}}]});
    assert.match($('#productionDetail').innerHTML,/<button data-project-action="resume" >Reconcile outcome only<\/button>/);
    assert.match($('#productionDetail').innerHTML,/No retry or later stage/);
    assert.equal(requests.length,0,'Rendering never reconciles or generates');
  }
  const button={dataset:{projectAction:'resume'},disabled:false},event={target:{closest:s=>s==='[data-project-action]'?button:null}};
  await Promise.all([$('#productionDetail').onclick(event),$('#productionDetail').onclick(event)]);
  assert.deepEqual(JSON.parse(JSON.stringify(requests)),[{url:'/api/production/'+project.id+'/resume',data:{}}]);
  render({...project,can_reconcile_tracking:false});assert.match($('#productionDetail').innerHTML,/<button data-project-action="resume" disabled>/,'Unknown or mixed receipt cannot use a status label to enable reconciliation');
  render({...project,can_reconcile_tracking:false,state:{status:'failed',message:'Create an explicit repair branch'}});
  assert.doesNotMatch($('#productionDetail').innerHTML,/data-project-action="resume"/);assert.match($('#productionDetail').innerHTML,/data-project-action="branch"/);
  console.log('Terminal outcome controls require authoritative eligibility and explicit action; no new generation request.');
})().catch(error=>{console.error(error);process.exitCode=1;});
