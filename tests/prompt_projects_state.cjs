const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const elements=new Map();
class Element{constructor(tag='div'){Object.assign(this,{tag,value:'',children:[],listeners:{},dataset:{},hidden:false,disabled:false});}addEventListener(k,f){this.listeners[k]=f;}append(...c){this.children.push(...c);}replaceChildren(...c){this.children=c;}setAttribute(k,v){this[k]=v;}querySelectorAll(){return [];} }
const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const events={};const context=vm.createContext({document:{getElementById:el,createElement:t=>new Element(t),createTextNode:t=>new Element(),addEventListener:(k,f)=>events[k]=f,dispatchEvent:e=>events[e.type]?.()},
 window:{addEventListener(){}},CustomEvent:class{constructor(type){this.type=type;}},URL:{revokeObjectURL(){}},
 fetch:async()=>({ok:true,json:async()=>({profiles:[]})})});
for(const name of ['prompt-lab.js','reference-review.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8'),context);
const owner=context.StudioPromptDraft,review=context.StudioReferenceReview;
assert.equal(typeof owner.openSaved,'function','Existing draft owner must own saved-brief replacement');
assert.equal(typeof review.capture,'function','Existing review owner must expose its current context');
assert.equal(typeof review.restore,'function','Existing review owner must own restoring saved selections');
// Registry is deliberately explicit in this controlled fixture.
vm.runInContext("registry=[{id:'sdxl-prose-v1',tasks:['image'],max_refs:0,min_refs:0}];",context);
el('profile').value='sdxl-prose-v1';el('brief').value='Current unsaved';
const snapshot=owner.capture(),doc={format:'studio.prompt-document/v1',name:'Saved',profile_id:'sdxl-prose-v1',intent:{...snapshot.intent,brief:'Saved words'},reference_context:null};
el('brief').value='Newer typing';assert.throws(()=>owner.openSaved(snapshot,doc),/changed/i);assert.equal(el('brief').value,'Newer typing');
const fresh=owner.capture();assert.throws(()=>owner.openSaved(fresh,{...doc,profile_id:'removed-profile'}),/profile/i);assert.equal(el('brief').value,'Newer typing');
owner.openSaved(fresh,doc);assert.equal(el('brief').value,'Saved words');assert.throws(()=>owner.openSaved(fresh,doc),/changed/i);
const before=review.capture();review.restore(null);assert.equal(review.capture().context,null);assert.notEqual(before.version,review.capture().version);assert.equal(el('rr-review').hidden,true);
assert.equal(el('rr-preview').disabled,true);assert.equal(el('rr-undo').disabled,true);
console.log('Saved brief owner guards passed');
