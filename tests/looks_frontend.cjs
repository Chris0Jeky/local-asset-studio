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
console.log(count+' checks. Look contracts passed');
