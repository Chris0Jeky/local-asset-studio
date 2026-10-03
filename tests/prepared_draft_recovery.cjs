'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const U=require('../app/static/studio-core.js');
let count=0;const test=(name,fn)=>{fn();count++;console.log('PASS '+name);};
const tile={version:1,preset_id:'tile-demo',source_asset_id:'source',source_sha256:'a'.repeat(64),rolled_file:'b'.repeat(32)+'_seam.png',rolled_sha256:'c'.repeat(64),size:512,band_px:112,feather_px:12,flatten_sigma_px:48};
const parallax={version:1,preset_id:'parallax-demo',source_asset_id:'source',source_sha256:'a'.repeat(64),source_file:'b'.repeat(32)+'_room.png',plan_id:'c'.repeat(64),stage:'plate',width:512,height:512,objects:'the desk',view_polygons:[[[0,0],[128,0],[128,128]]]};
const recipe=(kind,claim)=>({preset:claim.preset_id,[kind]:claim,controls:{positive:'reviewed words',reference:claim.rolled_file||claim.source_file,width:512,height:512},parent_assets:['source'],batch:1});
const draft=recipe=>({version:1,updatedAt:123,recipe});
test('browser drafts preserve both prepared routes and deep-copy polygon state',()=>{
  for(const [kind,claim] of [['tile',tile],['parallax',parallax]]){
    const normalized=U.normalizeDraft(draft(recipe(kind,claim)));assert.deepEqual(normalized.recipe[kind],claim);
    assert.notEqual(normalized.recipe[kind],claim);
    if(kind==='parallax'){normalized.recipe[kind].view_polygons[0][0][0]=99;assert.equal(claim.view_polygons[0][0][0],0);}
  }
});
test('malformed, mixed and cross-recipe claims cannot silently turn into plain drafts',()=>{
  for(const claim of [{...tile,version:2},{...tile,size:257},{...tile,rolled_file:'../bad.png'},{...tile,extra:true},{...tile,band_px:15}])assert.equal(U.normalizeDraft(draft(recipe('tile',claim))),null);
  for(const claim of [{...parallax,stage:'invented'},{...parallax,width:511},{...parallax,view_polygons:[[[1,2]]]},{...parallax,plan_id:'bad'}])assert.equal(U.normalizeDraft(draft(recipe('parallax',claim))),null);
  assert.equal(U.normalizeDraft(draft({...recipe('tile',tile),preset:'other'})),null);
  assert.equal(U.normalizeDraft(draft({...recipe('tile',tile),parallax})),null);
  assert.equal(U.normalizeDraft(draft({...recipe('tile',tile),continuation:{}})),null);
});
test('stale input, lineage, dimensions and batching produce explicit read-only blockers',()=>{
  const base=recipe('tile',tile);assert.equal(U.preparedBlocker(base),'');
  for(const changed of [{...base,controls:{...base.controls,reference:'other.png'}},{...base,parent_assets:[]},{...base,batch:2}])assert.ok(U.preparedBlocker(changed));
  const next=recipe('parallax',parallax);assert.equal(U.preparedBlocker(next),'');
  assert.match(U.preparedBlocker({...next,controls:{...next.controls,width:768}}),/512/);
  const missing={...base,controls:{positive:'reviewed words'}};assert.ok(U.normalizeDraft(draft(missing)),'keep the held envelope so reattachment stays explicit');assert.match(U.preparedBlocker(missing),/prepared/);
});
const app=fs.readFileSync(require.resolve('../app/static/app.js'),'utf8');
const apply=app.slice(app.indexOf('function applySaved('),app.indexOf('function continuationPayload('));
function applyFixture(saved){
  const inputs={'#reference':{value:'',files:[]},'#lastReference':{value:'',files:[]},'#positive':{value:''},'#negative':{value:''},'#batch':{value:1}};
  const sandbox={catalog:{presets:[{id:'tile-demo',reference:['1','image'],tile_route:true},{id:'parallax-demo',reference:['1','image'],parallax_route:true},{id:'plain'}]},StudioUX:U,
    tileState:null,parallaxState:null,continuationState:null,continuationSource:null,parentAssets:[],parentByInput:{},referenceRecords:[],uploaded:null,lastUploaded:null,
    $:key=>inputs[key],getControl:key=>inputs[key]||(inputs[key]={value:''}),updateReady(){},message(){},recipeChanged(){}};
  sandbox.selectPreset=id=>{sandbox.selected=sandbox.catalog.presets.find(p=>p.id===id);sandbox.tileState=null;sandbox.parallaxState=null;sandbox.uploaded=null;sandbox.lastUploaded=null;};
  sandbox.selectPreset('plain');vm.createContext(sandbox);vm.runInContext(apply,sandbox);sandbox.applySaved(saved);return sandbox;
}
test('shipped saved-setup application restores the claim, source and lineage',()=>{
  for(const [kind,claim] of [['tile',tile],['parallax',parallax]]){
    const state=applyFixture(recipe(kind,claim));assert.deepEqual(JSON.parse(JSON.stringify(state[kind+'State'])),claim);assert.equal(state.uploaded,claim.rolled_file||claim.source_file);assert.deepEqual(Array.from(state.parentAssets),['source']);
  }
  assert.throws(()=>applyFixture({...recipe('tile',tile),preset:'plain'}),/prepared|plan/i);
});
test('save, snapshot and checked recipe import carry both envelopes',()=>{
  const workbench=fs.readFileSync(require.resolve('../app/static/studio-workbench.js'),'utf8');
  const save=app.slice(app.indexOf("$('#save').onclick="),app.indexOf("$('#savedList').onclick="));
  const importing=app.slice(app.indexOf("$('#importRecipe').onchange="),app.indexOf("$('#refreshModels').onclick="));
  const snapshot=workbench.slice(workbench.indexOf('  function snapshot()'),workbench.indexOf('\n',workbench.indexOf('  function snapshot()')));
  for(const text of [save,snapshot]){assert.ok(text.includes('...tilePayload()'));assert.ok(text.includes('...parallaxPayload()'));}
  assert.ok(importing.includes('tile:recipe.tile'));assert.ok(importing.includes('parallax:recipe.parallax'));
});
console.log(count+' prepared-draft checks passed');
