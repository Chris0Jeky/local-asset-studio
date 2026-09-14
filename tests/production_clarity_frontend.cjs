// Real Experiments rendering in Node's VM: planner cards, plan display names and
// the live comparison summary. No browser, no ComfyUI, no generation.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,hidden:false,required:false,open:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const safeUrl=url=>{try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[],createElement:()=>({style:{},classList:{toggle(){}},querySelectorAll:()=>[]})},
  esc,safeUrl,setInterval(){},showView(){},api:async()=>[],post:async()=>({})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const run=source=>vm.runInContext(source,context);

// 1 · A grid variant states its label once and never repeats its rationale.
const base={steps:20,cfg:4,width:768,height:1152,seed:7,positive:'a portrait'};
const variant={label:'steps=8 · cfg=3.0',controls:{...base,steps:8,cfg:3.0},
  rationale:'Turbo schedules are documented at eight steps with low guidance.',
  description:'steps=8 · cfg=3.0 · cfg=3.0, height=1152, seed=7, steps=8, width=768 — Turbo schedules are documented at eight steps with low guidance.',
  sources:['https://example.invalid/kb']};
run(`comparisonRecipe=${JSON.stringify({controls:base})};plannedVariants=[${JSON.stringify(variant)}];plannerAxes=[];renderPlanner();`);
// Accessible names are not visible text: strip them before counting what reads.
const visible=html=>html.replace(/aria-label="[^"]*"/g,'');
const card=visible($('#plannedVariants').innerHTML);
const occurrences=(text,needle)=>text.split(needle).length-1;
assert.equal(occurrences(card,'steps=8 · cfg=3.0'),1,'The axis label must appear exactly once per card');
assert.equal(occurrences(card,'Turbo schedules are documented'),1,'The rationale must appear exactly once per card');
assert.doesNotMatch(card,/height=1152/,'Unchanged recipe settings are noise, not a change');
assert.doesNotMatch(card,/width=768/);
assert.match(card,/source ↗/);

// 2 · A remix variant whose label names no setting still shows what it moves.
const remix={label:'Ink lines lead',controls:{...base,lora:1,lora2:0.6},rationale:'Ink lines leads at 1; the rest support at 0.6.',sources:[]};
run(`plannedVariants=[${JSON.stringify(remix)}];renderPlanner();`);
const remixCard=visible($('#plannedVariants').innerHTML);
assert.match(remixCard,/lora=1, lora2=0\.6/,'Changed LoRA weights are the only settings worth printing');
assert.equal(occurrences(remixCard,'Ink lines leads at 1'),1);

// 3 · Humanised display names: stored names keep their hashes, the list does not.
const at=Date.UTC(2026,8,14,10,0,0)/1000;
const planned={id:'b'.repeat(32),name:'Edit bridge 618d5e599670b2906aedf3fa2525aa696a8ae10a',kind:'comparison',axis:'steps',values:[8,20,30],
  created_at:at,recipe:{preset_id:'anima-portrait'},budget:{reserved:3,allowance:8},stages:[],
  state:{status:'planned',message:'Ready for explicit Start. No generation submitted.',artifacts:[]}};
const display=run(`planDisplayName(${JSON.stringify(planned)})`);
assert.doesNotMatch(display,/618d5e59/,'A content hash is not a name');
assert.match(display,/Edit bridge/);
assert.match(display,/steps = 8, 20, 30/);
assert.match(display,/2026/);
assert.equal(run(`planDisplayName(${JSON.stringify({name:'Rainy portrait · lighting study',kind:'comparison',axis:'variants',values:['a','b'],created_at:at})})`).includes('2 planned variants'),true);
assert.equal(run(`planDisplayName({name:'',kind:'native'})`),'Untitled plan');

// 4 · The list keeps the stored name available and the detail header humanises too.
run(`productionPlans=[${JSON.stringify(planned)}];productionId=${JSON.stringify(planned.id)};renderProduction();`);
const list=$('#productionList').innerHTML;
assert.match(list,/Edit bridge · steps = 8, 20, 30/);
assert.match(list,/title="Edit bridge 618d5e59/,'The stored name stays reachable, untouched');
assert.match($('#productionDetail').innerHTML,/Edit bridge · steps = 8, 20, 30/);
assert.match($('#productionDetail').innerHTML,/Start comparison/,'Start stays explicit');

// 5 · Empty state repeats the orientation and offers the planner.
run('productionPlans=[];productionId=null;renderProduction();');
assert.match($('#productionList').innerHTML,/Compare one change at a time/);
assert.match($('#productionList').innerHTML,/data-production-plan/);

// 6 · The live summary states the arithmetic and refuses a budget below the candidates.
$('#experimentRecipe').textContent='Anima portrait';$('#experimentAxis').value='steps';
$('#experimentValues').value='8, 20, 30';$('#experimentBudget').value='8';$('#estimateValue').textContent='4.0 min';
run('plannedVariants=null;renderPlannerSummary();');
assert.match($('#experimentSummary').textContent,/Compare steps = 8, 20, 30 on Anima portrait/);
assert.match($('#experimentSummary').textContent,/3 graph runs/);
assert.match($('#experimentSummary').textContent,/about 12 min/);
assert.match($('#experimentBudgetNote').textContent,/3 values × 1 seed = 3 runs; 8 reserved/);
$('#experimentBudget').value='2';run('renderPlannerSummary();');
assert.match($('#experimentBudgetNote').textContent,/at least 3/,'A budget below the candidate count is arithmetic, not an opinion');
$('#estimateValue').textContent='Calculating…';$('#experimentBudget').value='8';run('renderPlannerSummary();');
assert.match($('#experimentSummary').textContent,/timing still being measured/,'A pending estimate is not a missing one');
$('#estimateValue').textContent='Unavailable';run('renderPlannerSummary();');
assert.match($('#experimentSummary').textContent,/no measured time/);

// 7 · Create's estimate covers its whole batch; a comparison stage runs one output, so the share is divided out.
$('#estimateValue').textContent='42 s';run('renderPlannerSummary();');
assert.match($('#experimentSummary').textContent,/about 2 min at roughly 0\.7 min per run/,'Second-form estimates count too');
$('#estimateValue').textContent='20.0 min';$('#batch').value='4';run('renderPlannerSummary();');
assert.match($('#experimentSummary').textContent,/about 15 min at roughly 5\.0 min per run \(Create’s estimate for 4 outputs, shared out\)/);
$('#batch').value='';

// 8 · Plain digit runs are names, not hashes; a stated setting is matched whole, not as a prefix.
assert.match(run(`planDisplayName({name:'Portrait seed 12345678',kind:'native'})`),/12345678/,'A seed is not a content hash');
assert.equal(JSON.stringify(run(`variantChanges({label:'steps=10',controls:{steps:1,cfg:4}},{steps:20,cfg:4})`)),'["steps=1"]','steps=10 does not state steps=1');
assert.equal(JSON.stringify(run(`variantChanges({label:'steps=1 · cfg=3',controls:{steps:1,cfg:3}},{steps:20,cfg:4})`)),'[]');

console.log('Experiments planner cards state each fact once; plan names, empty state and comparison arithmetic read clearly.');
