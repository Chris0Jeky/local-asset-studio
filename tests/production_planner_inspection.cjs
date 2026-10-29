// Execute shipped planner handlers; only transport and DOM are deterministic fixtures.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const elements = new Map(), requests = [];
let mounted = null;
const $ = selector => {
  if(selector === '#plannerBlock') return mounted;
  if(!elements.has(selector)) elements.set(selector, {innerHTML:'', textContent:'', value:'', open:true,
    disabled:false, hidden:false, classList:{toggle(){}}, querySelectorAll:()=>[],
    before(element){mounted = element;}, showModal(){this.open = true;}, close(){this.open = false;this.onclose?.();}});
  return elements.get(selector);
};
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const ctx = vm.createContext({$, esc, safeUrl:()=> '#', setInterval(){}, showView(){}, api:async()=>[],
  document:{querySelector:$, querySelectorAll:()=>[], createElement:()=>({})},
  post:(url, body) => new Promise((resolve, reject) => requests.push({url, body, resolve, reject}))});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/production.js'), 'utf8'), ctx);
const run = script => vm.runInContext(script, ctx);
const saved = [{label:'Owner draft', controls:{seed:7}, rationale:'Retained', sources:[]}];
function setup(){
  $('#experimentDialog').open = true;
  $('#experimentAxis').value = 'seed'; $('#experimentValues').value = '7'; $('#experimentBudget').value = '9';
  run(`comparisonRecipe={preset_id:'fixture', controls:{seed:7}};plannedVariants=${JSON.stringify(saved)};plannerAxisIds=[];plannerBlock();`);
}
const inspect = {mode:'inspect', variants:[], axes_available:[], axes_withheld:[
  {id:'<img src=x>', control:'steps', code:'accelerator_schedule', accelerator_slots:['lora'], message:'<script>not executable</script>'}],
  notice:'Known roles, not installed-byte attestation.', generation_submitted:false, reservation_created:false};
(async()=>{
  assert.equal(requests.length, 0, 'Loading the module must not inspect or plan');
  setup();
  assert.match(mounted.innerHTML, /id="inspectSettings"/, 'Inspection must be reachable without a failed plan');
  $('#experimentBudget').value = '0'; // A read must not repair the owner's invalid draft.
  const pending = $('#inspectSettings').onclick();
  assert.equal(requests.length, 1); assert.equal(requests[0].url, '/api/experiments/plan');
  assert.equal(requests[0].body.mode, 'inspect'); assert.equal(requests[0].body.axes, undefined);
  requests.shift().resolve(inspect); await pending;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved), 'Inspection preserves the proposed variants');
  assert.equal($('#experimentBudget').value, '0', 'Inspection cannot resize an existing budget');
  assert.match($('#plannerLimits').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch($('#plannerLimits').innerHTML, /<script>|<img /, 'Imported labels and reasons are text');
  assert.match($('#experimentStatus').textContent, /Existing variants are unchanged/);
  // The latest explicit action wins even when older requests resolve last.
  const old = run('requestPlan("grid")');
  const newest = run('requestPlan("inspect")');
  const first = requests.shift(), second = requests.shift();
  second.resolve(inspect); await newest;
  first.resolve({...inspect, mode:'grid', variants:[{label:'Late old plan', controls:{seed:99}}]}); await old;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  // Closing or replacing a dialog context refuses stale success and failure alike.
  let wait = run('requestPlan("inspect")'); const closed = requests.shift();
  $('#cancelExperiment').onclick(); const status = $('#experimentStatus').textContent;
  closed.resolve({...inspect, notice:'late closed'}); await wait;
  assert.equal($('#experimentStatus').textContent, status);
  setup(); wait = run('requestPlan("grid")'); const replaced = requests.shift();
  run('comparisonRecipe={preset_id:"fixture",controls:{seed:7}}');
  replaced.reject(new Error('old context failure')); await wait;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  // Dropping a variant is also a newer local choice than an outstanding plan.
  wait = run('requestPlan("grid")'); const dropped = requests.shift();
  $('#plannedVariants').onclick({target:{closest:()=>({dataset:{dropVariant:'0'}})}});
  dropped.resolve({...inspect, mode:'grid', variants:saved}); await wait;
  assert.equal(run('plannedVariants'), null, 'A removed candidate must not reappear from an old plan');
  setup();
  // An unavailable inspection leaves the local plan intact, not silently cleared.
  wait = run('requestPlan("inspect")'); requests.shift().reject(new Error('Inspection unavailable')); await wait;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  assert.equal($('#experimentStatus').textContent, 'Inspection unavailable');
  assert.doesNotMatch($('#plannerLimits').innerHTML, /&lt;script&gt;/, 'Stale reasons must not survive a failed read');
  // Two wordings use the same captured recipe and only override positive text.
  ctx.selected={id:'fixture',name:'Lantern recipe',positive:true,seed:true,defaults:{seed:7}};
  ctx.uploadInput=async()=>null;ctx.uploaded=null;ctx.lastUploaded=null;
  ctx.continuationPayload=()=>({});ctx.attachedReferencePayload=()=>[{reference_id:'pose',file:'retained.png'}];
  ctx.parentAssets=['source-asset'];ctx.recipeTemplateHash='a'.repeat(64);
  const captured={positive:'A lantern in rain',negative:'text, watermark',seed:'9223372036854775807',width:'512',steps:'8'};
  ctx.values=()=>({...captured});
  await run('openComparison()');
  assert.equal(typeof $('#experimentMode').onchange,'function','The existing dialog must offer a working Two wordings mode');
  $('#experimentMode').value='wordings';$('#experimentMode').onchange();
  assert.equal($('#experimentWordingA').value,captured.positive);
  $('#experimentWordingB').value='Rain glows around a lantern';$('#experimentWordingB').oninput();
  assert.match($('#experimentSummary').textContent,/9223372036854775807/,'Shared seed digits remain exact');
  assert.match($('#experimentBudgetNote').textContent,/2 wordings.*1 seed.*2 runs/);
  assert.equal(requests.length,0,'Opening, switching and editing never prepares or generates');
  wait=$('#experimentForm').onsubmit({preventDefault(){}});
  const prepared=requests.shift();assert.equal(prepared.url,'/api/production');
  assert.deepEqual(JSON.parse(JSON.stringify(prepared.body.recipe.controls)),captured);
  assert.deepEqual(JSON.parse(JSON.stringify(prepared.body.variants)),[
    {label:'Wording A',controls:{positive:'A lantern in rain'}},
    {label:'Wording B',controls:{positive:'Rain glows around a lantern'}}]);
  assert.deepEqual(JSON.parse(JSON.stringify(prepared.body.recipe.references)),[{reference_id:'pose',file:'retained.png'}]);
  assert.deepEqual(JSON.parse(JSON.stringify(prepared.body.recipe.parent_assets)),['source-asset']);
  prepared.resolve({id:'prepared-wordings'});await wait;
  assert.equal(requests.length,0,'Preparing leaves Start comparison as a separate explicit action');

  await run('openComparison()');
  $('#experimentAxis').value='seed';$('#experimentValues').value='7, 8';
  wait=run('requestPlan("grid")');const oldNumeric=requests.shift();
  $('#experimentMode').value='wordings';$('#experimentMode').onchange();
  $('#experimentWordingA').value='Edited A';$('#experimentWordingB').value='Edited B';$('#experimentWordingB').oninput();
  oldNumeric.resolve({mode:'grid',variants:[{label:'Late numeric',controls:{seed:99}}],axes_available:[]});await wait;
  assert.equal(run('plannedVariants'),null,'A superseded numeric offer cannot enter a wording draft');
  assert.equal($('#experimentWordingA').value,'Edited A');assert.equal($('#experimentWordingB').value,'Edited B');
  await run('requestPlan("grid")');assert.equal(requests.length,0,'Hidden numeric actions cannot send a wording draft to the settings planner');
  $('#experimentMode').value='setting';$('#experimentMode').onchange();
  assert.equal($('#experimentValues').value,'7, 8','Switching preserves the numeric draft');
  $('#experimentMode').value='wordings';$('#experimentMode').onchange();
  assert.equal($('#experimentWordingA').value,'Edited A');assert.equal($('#experimentWordingB').value,'Edited B');

  for(const invalid of ['', '   ', ' Edited A ', 'x'.repeat(8001)]){
    $('#experimentWordingB').value=invalid;$('#experimentWordingB').oninput();
    await $('#experimentForm').onsubmit({preventDefault(){}});
    assert.equal(requests.length,0,'Blank, duplicate and oversized wordings cannot prepare');
    assert.equal($('#experimentWordingB').value,invalid,'Refusal retains the draft');
    assert.equal($('#prepareExperiment').disabled,true);
  }
  $('#experimentWordingB').value='Edited B';$('#experimentWordingB').oninput();
  run('comparisonParent={id:"parent",budget:{allowance:4,reserved:3}}');$('#experimentBudget').disabled=true;
  $('#experimentMode').onchange();await $('#experimentForm').onsubmit({preventDefault(){}});
  assert.equal(requests.length,0);assert.match($('#experimentStatus').textContent,/only 1 remain/,'Shared reservations reduce the available budget');
  run('comparisonParent=null');$('#experimentBudget').disabled=false;
  run('comparisonPositive=false');$('#experimentMode').onchange();
  await $('#experimentForm').onsubmit({preventDefault(){}});assert.equal(requests.length,0);
  assert.match($('#experimentStatus').textContent,/no editable positive wording/);
  run('comparisonPositive=true;comparisonSeed="-1"');$('#experimentMode').onchange();
  await $('#experimentForm').onsubmit({preventDefault(){}});assert.equal(requests.length,0);
  assert.match($('#experimentStatus').textContent,/fixed whole-number seed/);
  run('comparisonSeed="7"');$('#experimentMode').onchange();
  wait=$('#experimentForm').onsubmit({preventDefault(){}});const refused=requests.shift();
  refused.reject(new Error('Resolve prompt wildcards before planning'));await wait;
  assert.equal($('#experimentWordingA').value,'Edited A');assert.equal($('#experimentWordingB').value,'Edited B');
  assert.match($('#experimentStatus').textContent,/Resolve prompt wildcards/,'Server validation remains visible without losing either wording');

  wait=$('#experimentForm').onsubmit({preventDefault(){}});const cancelledPreparation=requests.shift();
  $('#cancelExperiment').onclick();await run('openComparison()');
  $('#experimentMode').value='wordings';$('#experimentMode').onchange();
  $('#experimentWordingB').value='New dialog draft';$('#experimentWordingB').oninput();
  const currentPlan=run('productionId');
  cancelledPreparation.resolve({id:'late-prepared-plan'});await wait;
  assert.equal($('#experimentDialog').open,true,'Late preparation cannot close a replacement dialog');
  assert.equal($('#experimentWordingB').value,'New dialog draft');assert.equal(run('productionId'),currentPlan);
  assert.equal(requests.length,0,'Cancelling or replacing the draft never submits a generation');
  console.log('Planner inspection: explicit read, retained variants, escaped reasons, latest-action/context/close guards passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
