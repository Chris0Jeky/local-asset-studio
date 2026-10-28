'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../app/static/studio-workbench.js'),'utf8');
const definition=source.slice(source.indexOf('  const pictureStamp='),source.indexOf('  function renderUndo('));
const restore=source.slice(source.indexOf('  wordingBack.onclick='),source.indexOf('  wordingDismiss.onclick='));
const draft=source.slice(source.indexOf('  function snapshot(){'),source.indexOf('  // This remains the sole owner of Create mutation;'));
const clicks=source.slice(source.indexOf("  q('#createView').addEventListener('click'"),source.indexOf('  const originalLoadSetups='));
function fixture(){
  const elements=new Map();const q=id=>{if(!elements.has(id))elements.set(id,{value:id==='#batch'?'1':'',files:[],dispatchEvent(){},focus(){},addEventListener(type,fn){this[type]=fn;}});return elements.get(id);};
  const s={draftPrivacy:'regular',selected:{id:'old',name:'Old'},uploaded:'old.png',lastUploaded:null,parentAssets:['asset'],parentByInput:{reference:'asset'},referenceRecords:[],
    recipeTemplateHash:'a'.repeat(64),referencePending:0,wordingBack:{},pictureKept:null,wordingKept:null,q,wording:()=>({positive:'words',negative:''}),pickedFiles:()=>[],values:()=>({seed:s.seed,lora_name:q('lora_name').value,lora2_name:q('lora2_name').value}),seed:7,
    U:{normalizeDraft:value=>value},continuationPayload:()=>({}),tilePayload:()=>({}),parallaxPayload:()=>({}),attachedReferencePayload:()=>[],pendingInputs:new Set(),
    getControl:key=>q(key),updateReady(){},recipeChanged(){},syncReady(){},renderReferenceSlots(){},updateLoraHints(){s.hints++;s.hintedNames=[q('lora_name').value,q('lora2_name').value];},hints:0,saves:0,saveDraft(){s.saves++;s.savedDraft=s.draftSnapshot();},
    announce(text){s.notice=text;},renderUndo(){s.renders++;},renders:0,forgetWording(){s.pictureKept=null;},selectPreset(id){s.selected={id,name:'Old'};s.recipeTemplateHash=null;},Event:class{}};
  vm.createContext(s);vm.runInContext(draft+';this.draftSnapshot=snapshot;'+definition+';this.snapshot=pictureSnapshot;this.stamp=pictureStamp;'+restore+clicks,s);
  q('lora_name').value='first.safetensors';q('lora2_name').value='second.safetensors';
  const pic=s.snapshot();s.selected={id:'new',name:'New'};s.recipeTemplateHash=null;s.uploaded=null;q('lora_name').value=q('lora2_name').value='';pic.loaded=s.stamp();s.pictureKept=pic;return s;
}
let count=0;function test(name,run){run();count++;console.log('PASS '+name);}
test('an in-flight upload refuses restore without changing selection or consuming its offer',()=>{
  const s=fixture();s.referencePending=1;s.wordingBack.onclick();assert.equal(s.selected.id,'new');assert.ok(s.pictureKept);assert.equal(s.saves,0);assert.match(s.notice,/upload/i);
  s.referencePending=0;s.wordingBack.onclick();assert.equal(s.selected.id,'old');assert.equal(s.saves,1);
});
test('restore carries the exact template hash through the first save and refreshes LoRA hints',()=>{
  const s=fixture();s.wordingBack.onclick();assert.equal(s.selected.id,'old');assert.equal(s.recipeTemplateHash,'a'.repeat(64));assert.equal(s.savedDraft.templateHash,'a'.repeat(64));assert.equal(s.hints,1);assert.deepEqual(s.hintedNames,['first.safetensors','second.safetensors']);
});
test('click-only edits withdraw the picture offer even when batch is unchanged',()=>{
  for(const selector of ['#randomSeed','[data-variant]','[data-ref-clear]']){
    const s=fixture();s.q('#createView').click({target:{closest:selectors=>selectors.split(',').includes(selector)}});assert.equal(s.pictureKept,null,selector);assert.ok(s.renders);assert.equal(s.q('#batch').value,'1');
  }
  const s=fixture();s.q('#createView').click({target:{closest:()=>false}});assert.ok(s.pictureKept,'unrelated clicks keep the offer');
});
test('a later programmatic sampling change is not discarded by going back',()=>{
  const s=fixture();s.seed=99;s.wordingBack.onclick();assert.equal(s.selected.id,'new');assert.match(s.notice,/nothing was replaced/);
});
console.log(count+' picture way-back checks passed');
