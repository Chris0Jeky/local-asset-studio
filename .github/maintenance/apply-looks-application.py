from pathlib import Path
import subprocess
root=Path('.')
def blob(name): return subprocess.check_output(['git','hash-object',name],text=True).strip()
expected_before={'app/static/app.js':'d97d45d9351d9d85fcd40501428080b82b5328a0','app/static/looks.js':'7688910abe5e8f2595168231a8d2716f8bd6b0ae','app/static/studio-core.js':'bace135a41f5ce09d19c4b6ed47af1801658f0cf','tests/looks_frontend.cjs':'78758ab256a819c3a6da425b92d7bece0920cca5'}
for name,wanted in expected_before.items(): assert blob(name)==wanted,('base drift',name)
def replace(name,old,new):
 p=root/name;s=p.read_text();assert s.count(old)==1,(name,old[:80],s.count(old));p.write_text(s.replace(old,new))
replace('app/static/looks.js',"look.origin==='seed'?'shipped look':'your look'","look.origin==='seed'?(look.revision>0?'edited shipped look':'shipped look'):'your look'")
replace('app/static/looks.js','  return{SLOT,slotCount,recipeProblem,groups,optionLabel,prepareBlocker,saveBlocker,saveControls,summary,optionRows,optionsPayload,readyMessage};', '''  // Probe detached controls first: an unsupported select value becomes empty, and numeric
  // controls can reject a value. Never publish only the settings that happened to stick.
  function applyControls(controls,resolve){
    const writes=[],problems=[];
    for(const [key,value] of Object.entries(controls||{})){
      const input=resolve(key);
      if(!input){problems.push(key);continue;}
      const probe=input.cloneNode(true);probe.value=value;
      const same=probe.type==='number' ? probe.value!==''&&Number.isFinite(Number(value))&&Number(probe.value)===Number(value) : String(probe.value)===String(value);
      if(!same||!probe.checkValidity()){problems.push(key);continue;}
      writes.push([input,value]);
    }
    if(!problems.length)for(const [input,value] of writes)input.value=value;
    return problems;
  }
  let application=null;
  function normalizeApplication(value,presetId){
    if(!value||value.version!==1||value.preset_id!==presetId||!Array.isArray(value.controls)||!value.controls.length||value.controls.length>32||value.controls.some(k=>typeof k!=='string'||!/^[a-z][a-z0-9_]{0,63}$/.test(k)))return null;
    return {version:1,preset_id:presetId,controls:[...new Set(value.controls)]};
  }
  function clearApplication(){application=null;}
  function restoreApplication(value,presetId){
    application=value==null?null:normalizeApplication(value,presetId);
    if(value!=null&&!application)throw Error('Invalid saved Look application state.');
  }
  function applicationPayload(presetId){return application?.preset_id===presetId?{look_application:normalizeApplication(application,presetId)}:{};}
  function applicationBlocker(presetId){return application?.preset_id===presetId?'This Look could not be applied: '+application.controls.join(', ')+'. Recipe defaults are shown; no Look settings were applied. Reprepare with supported settings or reset the recipe without the look. Nothing was generated.':'';}
  return{SLOT,slotCount,recipeProblem,groups,optionLabel,prepareBlocker,saveBlocker,saveControls,summary,optionRows,optionsPayload,readyMessage,applyControls,normalizeApplication,clearApplication,restoreApplication,applicationPayload,applicationBlocker};''')
replace('app/static/looks.js',"+'<p id=\"lookStatus\" role=\"status\" aria-live=\"polite\"></p>';","+'<p id=\"lookStatus\" role=\"status\" aria-live=\"polite\"></p><button type=\"button\" id=\"lookReset\" hidden>Reset recipe without the look</button>';")
replace('app/static/looks.js','    renderLines();\n    const look=current()',"    renderLines();\n    q('#lookReset').hidden=!L.applicationBlocker(typeof selected!=='undefined'?selected?.id:null);q('#lookReset').disabled=busy;\n    const look=current()")
replace('app/static/looks.js',"    for(const [key,value] of Object.entries(result.controls)){const input=key==='positive'?q('#positive'):key==='negative'?q('#negative'):getControl(key);if(input)input.value=value;}","""    const problems=L.applyControls(result.controls,key=>key==='positive'?q('#positive'):key==='negative'?q('#negative'):getControl(key));
    if(problems.length){
      L.restoreApplication({version:1,preset_id:result.preset_id,controls:problems},result.preset_id);
      q('#positive').dispatchEvent(new Event('input',{bubbles:true}));updateReady();recipeChanged();
      const text=L.applicationBlocker(result.preset_id);message(text,true);status(text,true);return;
    }""")
replace('app/static/looks.js',"  q('#lookTrash').onclick=", "  q('#lookReset').onclick=()=>{if(busy)return;selectPreset(selected.id);status('Recipe reset without the look. Review its defaults before generating.');};\n  q('#lookTrash').onclick=")
replace('app/static/studio-core.js','    const continuation=value.recipe.continuation;', '''    const look=value.recipe.look_application;
    if(look!=null&&(typeof StudioLooks==='undefined'||!StudioLooks.normalizeApplication(look,value.recipe.preset)))return null;
    const continuation=value.recipe.continuation;''')
replace('app/static/studio-core.js','controls,batch,...(continuation?', 'controls,batch,...(look?{look_application:StudioLooks.normalizeApplication(look,value.recipe.preset)}:{}),...(continuation?')
replace('app/static/app.js','  recipeTemplateHash=null;\n  selected=next;', "  recipeTemplateHash=null;\n  if(typeof StudioLooks!=='undefined')StudioLooks.clearApplication();\n  selected=next;")
replace('app/static/app.js','  selectPreset(s.preset);\n  if(s.continuation', "  if(s.look_application!=null&&(typeof StudioLooks==='undefined'||!StudioLooks.normalizeApplication(s.look_application,s.preset)))throw Error('Invalid saved Look application state.');\n  selectPreset(s.preset);\n  if(typeof StudioLooks!=='undefined')StudioLooks.restoreApplication(s.look_application,s.preset);\n  if(s.continuation")
replace('app/static/app.js','function continuationBlockerItems(){', "function continuationBlockerItems(){\n  const lookProblem=typeof StudioLooks!=='undefined'?StudioLooks.applicationBlocker(selected?.id):'';\n  if(lookProblem)return [{code:'look',message:lookProblem}];")
replace('app/static/app.js','function checkedSetupControls() {\n  const controls=values();', "function checkedSetupControls() {\n  const lookProblem=typeof StudioLooks!=='undefined'?StudioLooks.applicationBlocker(selected?.id):'';\n  if(lookProblem)throw Error('Setup not saved. '+lookProblem);\n  const controls=values();")
replace('app/static/studio-workbench.js','recipe:{preset:selected.id,...continuationPayload(),controls:values(),batch:', "recipe:{preset:selected.id,...continuationPayload(),...(typeof StudioLooks!=='undefined'?StudioLooks.applicationPayload(selected.id):{}),controls:values(),batch:")
p=root/'tests/looks_frontend.cjs';p.write_text(p.read_text()+r'''
// Execute the shipped application path with select-like readback semantics.
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../app/static/looks.js'),'utf8');
const applySource=source.slice(source.indexOf('  function apply(result){'),source.indexOf("  q('#lookSelect').addEventListener"));
function selectControl(options, initial){let value=initial;return {type:'select-one',get value(){return value;},set value(v){value=options.includes(String(v))?String(v):'';},cloneNode(){return selectControl(options,value);},checkValidity(){return true;}};}
function textControl(initial,type='text'){return {type,value:String(initial),cloneNode(){return textControl(this.value,type);},checkValidity(){return true;},dispatchEvent(){}};}
function applyFixture(controls){
  const inputs={'#positive':textControl('default words'),'#negative':textControl(''),'#batch':textControl(1),seed:textControl(13,'number'),sampler:selectControl(['euler'],'euler')};
  let status='',message='';const sandbox={L,looks:[],busy:false,composed:null,selected:{id:'demo',defaults:{positive:'default words'}},q:key=>inputs[key],getControl:key=>inputs[key],
    selectPreset(){L.clearApplication?.();inputs.seed.value='13';inputs.sampler.value='euler';},confirm:()=>true,
    status(text){status=text;},message(text){message=text;},updateLoraHints(){},updateReady(){},scheduleTimeEstimate(){},recipeChanged(){},Event:class{}};
  vm.runInNewContext(applySource+';apply(result)',{...sandbox,result:{preset_id:'demo',look:{id:'test',name:'Test'},controls}});
  return {inputs,status,message};
}
test('a stale select choice cannot become a prepared success or partially apply the other controls',()=>{
  const result=applyFixture({positive:'new words',seed:37,sampler:'removed'});
  assert.match(result.status,/could not be applied/);assert.doesNotMatch(result.status,/press Generate/);
  assert.equal(result.inputs.seed.value,'13');assert.equal(result.inputs.sampler.value,'euler');
  assert.match(L.applicationBlocker('demo'),/sampler/);
});
test('a missing control is reported and does not silently fall through to graph defaults',()=>{
  const result=applyFixture({positive:'new words',seed:37,fps:24});
  assert.match(result.status,/fps/);assert.match(L.applicationBlocker('demo'),/fps/);
});
test('a valid application is all-or-nothing and clears an earlier hold',()=>{
  const result=applyFixture({positive:'new words',seed:37,sampler:'euler'});
  assert.match(result.status,/Nothing was generated; press Generate/);assert.equal(result.inputs.seed.value,37);
  assert.equal(L.applicationBlocker('demo'),'');
});
test('an edited shipped seed is no longer presented as the original shipped look',()=>{
  assert.match(L.summary({...night,revision:2}),/edited shipped look/);
});
test('draft normalization preserves the hold and cannot silently drop malformed hold state',()=>{
  const U=require('../app/static/studio-core.js');global.StudioLooks=L;
  const hold={version:1,preset_id:'demo',controls:['sampler','sampler']};
  const draft={version:1,updatedAt:1,recipe:{preset:'demo',controls:{seed:13},look_application:hold}};
  try{
    const normalized=U.normalizeDraft(draft);assert.deepEqual(normalized.recipe.look_application,{version:1,preset_id:'demo',controls:['sampler']});
    L.clearApplication();L.restoreApplication(normalized.recipe.look_application,'demo');assert.match(L.applicationBlocker('demo'),/sampler/);
    for(const bad of [{...hold,version:2},{...hold,preset_id:'other'},{...hold,controls:[]},{...hold,controls:[{}]},{...hold,controls:['<script>']},false]){
      assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,look_application:bad}}),null);
    }
    assert.deepEqual(L.applicationPayload('other'),{});
  }finally{L.clearApplication();delete global.StudioLooks;}
  assert.equal(U.normalizeDraft(draft),null,'a host without Looks must refuse the held draft, not lose its state');
});
test('out-of-range and fractional numeric settings refuse the entire application',()=>{
  for(const invalid of [0,101,2.5]){
    const number=textControl(10,'number');number.cloneNode=()=>({...textControl(10,'number'),checkValidity(){return Number(this.value)>=1&&Number(this.value)<=100&&Number.isInteger(Number(this.value));}});
    const prompt=textControl('unchanged');const problems=L.applyControls({positive:'new',steps:invalid},key=>key==='steps'?number:prompt);
    assert.deepEqual(problems,['steps']);assert.equal(prompt.value,'unchanged');assert.equal(number.value,'10');
  }
});
console.log(count+' total Look checks passed');
''')
expected_after={'app/static/app.js':'12018d30d7df8457a6ae051e66d3fdf9dad7f989','app/static/looks.js':'05a205321e38164c87f62ff95ee91bc4ab5655c2','app/static/studio-core.js':'7c005187885ae082dfb8a4bcd5558ae009e607d2','app/static/studio-workbench.js':'2e47ddfda94b3ad6041e66bf15ff98ed909b314a','tests/looks_frontend.cjs':'1333f97a1f7c1cb246e5487e72490dc878259711','tests/looks_application_browser.py':'e6ac42d462d6bce260e23ee65d5abee7624c1fc6','.github/workflows/looks-application.yml':'9dfe4ecc3ac76c2af3f986ac4d9fd9b2bf4c6831'}
for name,wanted in expected_after.items(): assert blob(name)==wanted,('output drift',name,blob(name))
