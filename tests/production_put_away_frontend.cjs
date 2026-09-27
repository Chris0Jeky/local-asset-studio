// #940: the owner can put a settled plan away from its detail view. Execute the real Production renderer and handler:
// only the put-away route is called, a running plan offers nothing, and the in-progress list hides a put-away plan.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),requests=[];
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},
  api:async()=>[],post:async(url,data)=>{requests.push({url,data});return {};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const base={id:'c'.repeat(32),name:'Old study',kind:'native',budget:{reserved:0,allowance:1},stages:[],created_at:Date.now()/1000-86400,state:{status:'failed',message:'Retained'}};
const render=value=>vm.runInContext(`productionPlans=${JSON.stringify(value)};productionId=${JSON.stringify(base.id)};renderProduction();`,context);
(async()=>{
  render([{...base,can_put_away:true,put_away:false}]);
  assert.match($('#productionDetail').innerHTML,/<button data-plan-put-away="true">Put away<\/button> <small>Takes it off your desk/);
  assert.equal(requests.length,0,'Rendering changes nothing');
  const button={dataset:{planPutAway:'true'},disabled:false},event={target:{closest:s=>s==='[data-plan-put-away]'?button:null}};
  await Promise.all([$('#productionDetail').onclick(event),$('#productionDetail').onclick(event)]);
  assert.deepEqual(JSON.parse(JSON.stringify(requests)),[{url:'/api/production/'+base.id+'/put-away',data:{put_away:true}}],'One request per press; nothing else');
  assert.equal(button.disabled,false);
  render([{...base,put_away:true,put_away_at:1790000000,can_bring_back:true,can_put_away:false}]);
  assert.match($('#productionDetail').innerHTML,/Put away [^<]+\. Its status, stages and files are unchanged/);
  assert.match($('#productionDetail').innerHTML,/<button data-plan-put-away="false">Bring back<\/button>/);
  assert.match($('#productionList').innerHTML,/No plans in progress or needing attention/,'The in-progress list hides a put-away plan');
  vm.runInContext(`planFilter={type:'all',status:'all'};renderProduction();`,context);
  assert.match($('#productionList').innerHTML,/failed · native export · put away/,'All statuses still lists it, tagged');
  render([{...base,state:{status:'running',message:'Busy'},can_put_away:false,put_away:false}]);
  assert.doesNotMatch($('#productionDetail').innerHTML,/data-plan-put-away/,'A running plan offers no put away');
  console.log('Plan put away changes only its marker, one request per press; nothing is started or stopped.');
})().catch(error=>{console.error(error);process.exitCode=1;});
