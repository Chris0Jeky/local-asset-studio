'use strict';
// #1221: looks in Create. Pure policy: which looks are offered, when Prepare and Save say why they are off, what a saved
// look records, and what the page says after preparing. The server composes the wording (tests/test_looks.py).
const assert=require('node:assert/strict');
const L=require('../app/static/looks.js');
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const night={id:'look-night',name:'Night Shift (retro anime)',usable:true,trashed_at:null,revision:0,origin:'seed',preset_name:'Z-Image Turbo fast',anchor_asset_id:'asset-9',
  body:{preset_id:'zimage-fast',template:'Background of {scene}.',scene_example:'a corridor'},lineage:[{role:'anchor',key:'retro-anime-master-z2',sha256:'c'.repeat(64)}]};
const away={...night,id:'look-away',name:'Old look',trashed_at:5,usable:false,unusable_reason:'This look is put away. Restore it to use it.'};
const broken={...night,id:'look-broken',name:'Broken',usable:false,unusable_reason:'Its recipe (gone) is not in the recipe library.',body:{...night.body,preset_id:'gone'},preset_name:null};
test('put-away looks are grouped apart; a look on another recipe says which recipe it uses',()=>{
  const g=L.groups([night,away,broken]);
  assert.deepEqual(g.active.map(l=>l.id),['look-night','look-broken']);assert.deepEqual(g.away.map(l=>l.id),['look-away']);
  assert.equal(L.optionLabel(night,'zimage-fast'),'Night Shift (retro anime)');
  assert.equal(L.optionLabel(night,'anima-portrait'),'Night Shift (retro anime) · on Z-Image Turbo fast');
  assert.equal(L.optionLabel(broken,'zimage-fast'),'Broken · unavailable');
  assert.deepEqual(L.groups(undefined),{active:[],away:[]});
});
test('Prepare is off with a reason until a usable look and a scene are there',()=>{
  assert.equal(L.prepareBlocker({look:null,scene:'x'}),'Choose a look.');
  assert.equal(L.prepareBlocker({look:night,scene:'  '}),'Type the scene in a few words.');
  assert.equal(L.prepareBlocker({look:away,scene:'a hall'}),'This look is put away. Restore it to use it.');
  assert.match(L.prepareBlocker({look:broken,scene:'a hall'}),/not in the recipe library/);
  assert.match(L.prepareBlocker({look:night,scene:'a hall',busy:true}),/Wait/);
  assert.equal(L.prepareBlocker({look:night,scene:'a hall'}),'');
});
test('Save needs a text-to-image recipe, one {scene} slot and a name',()=>{
  const text={id:'zimage-fast',positive:['4','text']};
  assert.match(L.saveBlocker({preset:null,positive:'',name:'x'}),/Choose a recipe/);
  assert.match(L.saveBlocker({preset:{...text,reference:['1','image']},positive:'{scene}',name:'x'}),/takes a picture/);
  assert.match(L.saveBlocker({preset:{...text,reference_slots:[{role:'style'}]},positive:'{scene}',name:'x'}),/takes a picture/);
  assert.match(L.saveBlocker({preset:{...text,modality:'video'},positive:'{scene}',name:'x'}),/image recipe/);
  assert.match(L.saveBlocker({preset:{id:'x'},positive:'{scene}',name:'x'}),/no wording/);
  assert.match(L.saveBlocker({preset:text,positive:'a room',name:'x'}),/Write \{scene\} in the wording/);
  assert.match(L.saveBlocker({preset:text,positive:'{scene} {scene}',name:'x'}),/only once/);
  assert.equal(L.saveBlocker({preset:text,positive:'of {scene}.',name:' '}),'Name the look.');
  assert.equal(L.saveBlocker({preset:text,positive:'of {scene}.',name:'Dusk'}),'');
  assert.equal(L.slotCount('a {scene} b'),1);assert.equal(L.slotCount(undefined),0);
});
test('a saved look keeps the recipe settings, never the wording or a picture',()=>{
  assert.deepEqual(L.saveControls({positive:'p',negative:'n',reference:'r.png',last_reference:'l.png',mode:'m',seed:'2026092752',width:'1344',cfg:'1.5',sampler:'euler',lora_name:'a.safetensors',steps:''}),
    {seed:2026092752,width:1344,cfg:1.5,sampler:'euler',lora_name:'a.safetensors'});
});
test('the summary names the recipe, the anchor and whether the anchor is in this Workspace',()=>{
  assert.equal(L.summary(night),'Z-Image Turbo fast · anchor retro-anime-master-z2 (in your Workspace) · shipped look');
  assert.equal(L.summary({...night,anchor_asset_id:null,origin:'owner'}),'Z-Image Turbo fast · anchor retro-anime-master-z2 (not in this Workspace) · your look');
  assert.equal(L.summary({...night,lineage:[]}),'Z-Image Turbo fast · no anchor picture · shipped look');
  assert.equal(L.summary(null),'');
});
test('after preparing, the page says what was set and that nothing was generated',()=>{
  const text=L.readyMessage({look:{name:'Night Shift (retro anime)'},preset_id:'zimage-fast',preset_name:'Z-Image Turbo fast',controls:{positive:'x',seed:2026092752,width:1344,height:768}},true);
  assert.equal(text,'Night Shift (retro anime) prepared on Z-Image Turbo fast (recipe switched), seed 2026092752, 1344x768. Your scene is in the wording. Nothing was generated; press Generate when it reads right.');
});
test('a look with optional lines offers one checkbox per line, set to its default, and sends every choice',()=>{
  const wall={id:'quiet_wall',label:'Keep the quiet wall for UI backgrounds',text:'The left half is a plain wall.',default:false};
  const withWall={...night,body:{...night.body,template:'Background of {scene}. {quiet_wall}',options:[wall,{...wall,id:'rain',label:'Heavy rain',default:true}]}};
  assert.deepEqual(L.optionRows(withWall),[{id:'quiet_wall',label:'Keep the quiet wall for UI backgrounds',checked:false},{id:'rain',label:'Heavy rain',checked:true}]);
  assert.deepEqual(L.optionRows(night),[]);assert.deepEqual(L.optionRows(null),[]);
  assert.deepEqual(L.optionsPayload(withWall,{quiet_wall:true}),{quiet_wall:true,rain:true},'an unticked-by-the-page line keeps its default');
  assert.deepEqual(L.optionsPayload(withWall,{quiet_wall:true,rain:false,stray:true}),{quiet_wall:true,rain:false},'only the look\'s own lines are sent');
  assert.equal(L.optionsPayload(night,{quiet_wall:true}),null,'a look without lines sends none');
  const text=L.readyMessage({look:{name:'Night Shift (retro anime)',options:{quiet_wall:true,rain:false}},preset_id:'zimage-fast',preset_name:'Z-Image Turbo fast',controls:{seed:1,width:1344,height:768}},false,withWall);
  assert.equal(text,'Night Shift (retro anime) prepared on Z-Image Turbo fast, seed 1, 1344x768, with: Keep the quiet wall for UI backgrounds. Your scene is in the wording. Nothing was generated; press Generate when it reads right.');
});
console.log(count+' checks. Look contracts passed');

// Execute the shipped application path with select-like readback semantics.
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../app/static/looks.js'),'utf8');
const applySource=source.slice(source.indexOf('  function apply(result){'),source.indexOf("  q('#lookSelect').addEventListener"));
function selectControl(options, initial){let value=initial;return {type:'select-one',get value(){return value;},set value(v){value=options.includes(String(v))?String(v):'';},cloneNode(){return selectControl(options,value);},checkValidity(){return true;}};}
function textControl(initial,type='text'){return {type,value:String(initial),cloneNode(){return textControl(this.value,type);},checkValidity(){return true;},dispatchEvent(){}};}
function applyFixture(controls){
  const inputs={'#positive':textControl('my words'),'#negative':textControl('my avoid'),'#batch':textControl(3),seed:textControl(99,'number'),sampler:selectControl(['euler'],'euler'),scheduler:selectControl(['normal'],'normal'),lora_name:selectControl(['installed.safetensors'],'installed.safetensors')};
  let status='',message='';const sandbox={recipeTemplateHash:null,L,looks:[],busy:false,composed:null,selected:{id:'demo',defaults:{positive:'default words'}},q:key=>inputs[key],getControl:key=>inputs[key],
    StudioSetupDraft:{capture:()=>({recipe:Object.fromEntries(Object.entries(inputs).map(([key,input])=>[key,input.value]))})},
    applySaved(recipe){for(const [key,value] of Object.entries(recipe))inputs[key].value=value;},preparationStamp:()=>'',preparationEpoch:0,
    selectPreset(){L.clearApplication?.();inputs.seed.value='13';inputs.sampler.value='euler';inputs['#positive'].value='default words';},confirm:()=>true,
    status(text){status=text;},message(text){message=text;},updateLoraHints(){},updateReady(){},scheduleTimeEstimate(){},recipeChanged(){},Event:class{}};
  vm.runInNewContext('let preparedShortcut;'+applySource+';apply(result)',{...sandbox,result:{preset_id:'demo',look:{id:'test',name:'Test',revision:0},controls}});
  return {inputs,status,message};
}
test('a stale select choice cannot become a prepared success or partially apply the other controls',()=>{
  const result=applyFixture({positive:'new words',seed:37,sampler:'removed'});
  assert.match(result.status,/could not be applied/);assert.doesNotMatch(result.status,/press Generate/);
  assert.equal(result.inputs.seed.value,'99');assert.equal(result.inputs.sampler.value,'euler');
  assert.equal(result.inputs['#positive'].value,'my words');assert.equal(result.inputs['#negative'].value,'my avoid');assert.equal(result.inputs['#batch'].value,'3');
  assert.equal(L.applicationBlocker('demo'),'');
});

test('every unavailable select is named in plain words and Create retains its previous values',()=>{
  const result=applyFixture({positive:'new words',seed:37,lora_name:'gone.safetensors',sampler:'retired',scheduler:'retired'});
  assert.match(result.status,/LoRA 'gone.safetensors' is not installed/);assert.match(result.status,/sampler 'retired'/);assert.match(result.status,/schedule 'retired'/);
  assert.match(result.status,/Models & setup/);assert.match(result.status,/Prepare stopped/);
  assert.equal(result.inputs.seed.value,'99');assert.equal(result.inputs.lora_name.value,'installed.safetensors');
});
test('a missing control is reported and does not silently fall through to graph defaults',()=>{
  const result=applyFixture({positive:'new words',seed:37,fps:24});
  assert.match(result.status,/fps/);assert.equal(L.applicationBlocker('demo'),'');
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
test('actual controls are read back too and every write is restored when a live control rejects it',()=>{
  const prompt=textControl('old'),sampler=selectControl(['euler'],'euler');
  sampler.cloneNode=()=>textControl('euler');
  assert.deepEqual(L.applyControls({positive:'new',sampler:'gone'},key=>key==='positive'?prompt:sampler),['sampler']);
  assert.equal(prompt.value,'old');assert.equal(sampler.value,'euler');
});
test('prepared provenance survives drafts, resets and edits without changing the recorded options',()=>{
  const U=require('../app/static/studio-core.js');global.StudioLooks=L;
  const look={id:'look-a',name:'Night Shift',revision:2,options:{quiet_wall:true}};
  try{
    L.restoreApplication(null,'demo',look);look.options.quiet_wall=false;
    assert.equal(L.applicationPayload('demo').look.options.quiet_wall,true);
    const draft=U.normalizeDraft({version:1,updatedAt:1,recipe:{preset:'demo',controls:{positive:'edited scene'},...L.applicationPayload('demo')}});
    L.clearApplication();assert.deepEqual(L.applicationPayload('demo'),{});
    L.restoreApplication(draft.recipe.look_application,'demo',draft.recipe.look);
    assert.equal(L.applicationPayload('demo').look.revision,2);
    assert.deepEqual(L.applicationPayload('other'),{});
    assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,look:{...look,revision:true}}}),null);
  }finally{L.clearApplication();delete global.StudioLooks;}
});
test('gallery shows numeric diagnostics and unavailable state without claiming acceptance',()=>{
  const app=fs.readFileSync(require.resolve('../app/static/app.js'),'utf8');
  const note=vm.runInNewContext(app.slice(app.indexOf('function lookNote('),app.indexOf('var expandedPrompts='))+';lookNote',{esc:v=>String(v).replaceAll('<','&lt;')});
  const job={look:{name:'<Night Shift>',revision:2,options:{quiet_wall:true}}};
  const html=note(job,{text_safe:{left_edge_density:0.02,right_edge_density:0.1,comparison:'left quieter'}});
  assert.match(html,/&lt;Night Shift>/);assert.match(html,/left 2.0%, right 10.0%/);assert.match(html,/Detail proxy only/);
  assert.match(note(job,{text_safe:{error:'bad image'}}),/check unavailable: bad image/);
  assert.equal(note({},{}),'');
  // #1704: an empty still is said so with or without a Look, and an ordinary one adds nothing.
  assert.match(note({},{empty_picture:'uniform'}),/One flat colour: most likely a failed run, not a result/);
  assert.match(note(job,{empty_picture:'transparent',text_safe:{error:'x'}}),/^<p class="make-warn"><small>Fully transparent[^]*Night Shift/);
  assert.equal(note({},{empty_picture:''}),'');
});
console.log(count+' total Look checks passed');
