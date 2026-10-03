'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../app/static/studio-workbench.js'),'utf8');
const definition=source.slice(source.indexOf('  const pictureStamp='),source.indexOf('  function renderUndo('));
const restore=source.slice(source.indexOf('  wordingBack.onclick='),source.indexOf('  wordingDismiss.onclick='));
const clicks=source.slice(source.indexOf("  q('#createView').addEventListener('click',e=>{if(e.target.closest('[data-variant]"),source.indexOf('  const originalLoadSetups='));
function fixture(){
  const elements=new Map();const q=id=>{if(!elements.has(id))elements.set(id,{value:id==='#batch'?'1':'',files:[],dispatchEvent(){},focus(){},addEventListener(type,fn){this[type]=fn;}});return elements.get(id);};
  const s={selected:{id:'old',name:'Old'},uploaded:'old.png',lastUploaded:null,parentAssets:['asset'],parentByInput:{reference:'asset'},referenceRecords:[],
    recipeTemplateHash:'a'.repeat(64),referencePending:0,wordingBack:{},pictureKept:null,wordingKept:null,q,wording:()=>({positive:'words',negative:''}),pickedFiles:()=>[],values:()=>({seed:s.seed}),seed:7,
    getControl:key=>q(key),updateReady(){},recipeChanged(){},syncReady(){},renderReferenceSlots(){},updateLoraHints(){s.hints++;},hints:0,saves:0,saveDraft(){s.saves++;s.savedHash=s.recipeTemplateHash;},
    announce(text){s.notice=text;},renderUndo(){s.renders++;},renders:0,forgetWording(){s.pictureKept=null;},selectPreset(id){s.selected={id,name:'Old'};s.recipeTemplateHash=null;},Event:class{}};
  vm.createContext(s);vm.runInContext(definition+';this.snapshot=pictureSnapshot;this.stamp=pictureStamp;'+restore+clicks,s);
  const pic=s.snapshot();s.selected={id:'new',name:'New'};s.recipeTemplateHash=null;s.uploaded=null;pic.loaded=s.stamp();s.pictureKept=pic;return s;
}
let count=0;function test(name,run){run();count++;console.log('PASS '+name);}
test('an in-flight upload refuses restore without changing selection or consuming its offer',()=>{
  const s=fixture();s.referencePending=1;s.wordingBack.onclick();assert.equal(s.selected.id,'new');assert.ok(s.pictureKept);assert.equal(s.saves,0);assert.match(s.notice,/upload/i);
});
test('restore carries the exact template hash through the first save and refreshes LoRA hints',()=>{
  const s=fixture();s.wordingBack.onclick();assert.equal(s.selected.id,'old');assert.equal(s.recipeTemplateHash,'a'.repeat(64));assert.equal(s.savedHash,'a'.repeat(64));assert.equal(s.hints,1);
});
test('click-only edits withdraw the picture offer even when batch is unchanged',()=>{
  const s=fixture();s.q('#createView').click({target:{closest:()=>true}});assert.equal(s.pictureKept,null);assert.ok(s.renders);
});
test('a later programmatic sampling change is not discarded by going back',()=>{
  const s=fixture();s.seed=99;s.wordingBack.onclick();assert.equal(s.selected.id,'new');assert.match(s.notice,/nothing was replaced/);
});
console.log(count+' picture way-back checks passed');
