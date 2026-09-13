// Real Production controls in Node's VM; no browser or model inference claim.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),requests=[];
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},
  api:async()=>[],post:async(url,data)=>{requests.push({url,data});return {};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const project={id:'a'.repeat(32),name:'Resumable comparison',kind:'comparison',budget:{reserved:2,allowance:2},stages:[],
  state:{status:'stopped',message:'Time allowance exhausted',time_budget:{revision:7,measured_seconds:10,unmeasured_seconds:50,remaining_seconds:0,limit_seconds:60,amendments:[]}}};
const render=value=>vm.runInContext(`productionPlans=[${JSON.stringify(value)}];productionId=${JSON.stringify(project.id)};renderProduction();`,context);
(async()=>{
  render(project);assert.equal(requests.length,0);
  assert.match($('#productionDetail').innerHTML,/conservatively charged/);assert.match($('#productionDetail').innerHTML,/Extend time only/);
  assert.match($('#productionDetail').innerHTML,/Resume separately/);
  const button={dataset:{projectAction:'extend-time'},disabled:false},event={target:{closest:selector=>selector==='[data-project-action]'?button:null}};
  $('#extendTimeMinutes').value='15';$('#extendTimeReason').value='';
  await $('#productionDetail').onclick(event);assert.equal(requests.length,0,'A reason is mandatory');
  $('#extendTimeReason').value='Complete the remaining reserved candidate';
  const first=$('#productionDetail').onclick(event),duplicate=$('#productionDetail').onclick(event);await Promise.all([first,duplicate]);
  assert.deepEqual(JSON.parse(JSON.stringify(requests)),[{url:'/api/production/'+project.id+'/extend-time',data:{seconds:900,reason:'Complete the remaining reserved candidate',expected_revision:7}}]);
  assert.equal(button.disabled,false);assert.equal(requests.some(r=>r.url.endsWith('/resume')),false,'Extension never implies resume');
  render({...project,state:{...project.state,status:'running'}});assert.doesNotMatch($('#productionDetail').innerHTML,/Extend time only/);
  render({...project,state:{...project.state,time_budget:{...project.state.time_budget,limit_seconds:14400}}});assert.doesNotMatch($('#productionDetail').innerHTML,/Extend time only/);
  console.log('Production time extension controls preserve explicit consent, revisions and duplicate-action protection.');
})().catch(error=>{console.error(error);process.exitCode=1;});
