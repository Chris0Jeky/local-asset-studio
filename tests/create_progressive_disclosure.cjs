'use strict';
const assert = require('node:assert/strict');
const Disclosure = require('../app/static/create-progressive-disclosure.js');

class Element {
  constructor(tag, id='') { this.tagName=tag.toUpperCase(); this.id=id; this.children=[]; this.parentNode=null; this.open=false; this.hidden=false; this.className=''; this.textContent=''; }
  append(...items) { for (const item of items) { if (item.parentNode) item.parentNode.children=item.parentNode.children.filter(child=>child!==item); item.parentNode=this; this.children.push(item); } }
  insertBefore(item, reference) { if (item.parentNode) item.parentNode.children=item.parentNode.children.filter(child=>child!==item); const index=this.children.indexOf(reference); assert.notEqual(index,-1); item.parentNode=this; this.children.splice(index,0,item); }
}
class Document {
  constructor() { this.body=new Element('body'); }
  createElement(tag) { return new Element(tag); }
  querySelector(selector) { const id=selector.startsWith('#')?selector.slice(1):''; const visit=node=>{ if (node.id===id) return node; for (const child of node.children) { const found=visit(child); if(found)return found; } return null; }; return visit(this.body); }
}

const document=new Document();
const recipeParent=new Element('section','recipeParent');
const recipeNotes=new Element('div','recipeNotes');
const referenceParent=new Element('section','roleReferences');
const referenceNote=new Element('p','referenceBoardNote');
recipeParent.append(recipeNotes); referenceParent.append(referenceNote); document.body.append(recipeParent,referenceParent);

let result=Disclosure.mount(document);
assert.equal(result.recipe.id,'recipeNotesHelp');
assert.equal(result.recipe.tagName,'DETAILS');
assert.equal(result.recipe.open,false);
assert.equal(result.recipe.hidden,true,'An empty recipe explanation must not leave an empty disclosure');
assert.equal(result.recipe.children[0].tagName,'SUMMARY');
assert.equal(result.recipe.children[0].textContent,'Recipe details, provenance and sources');
assert.equal(result.recipe.children[1],recipeNotes,'The existing recipeNotes owner must be preserved');
assert.equal(result.references.id,'referenceBoardHelp');
assert.equal(result.references.open,false);
assert.equal(result.references.hidden,true,'An empty reference explanation must not leave an empty disclosure');
assert.equal(result.references.children[0].textContent,'How are these references used?');
assert.equal(result.references.children[1],referenceNote,'The existing referenceBoardNote owner must be preserved');

recipeNotes.textContent='This recipe keeps the selected appearance stack.';
Disclosure.sync(result.recipe,recipeNotes);
assert.equal(result.recipe.hidden,false,'Authored recipe guidance must reveal its existing wrapper');
recipeNotes.textContent='   ';
Disclosure.sync(result.recipe,recipeNotes);
assert.equal(result.recipe.hidden,true,'Clearing recipe guidance must hide the wrapper again');
referenceNote.textContent='Picture 1 supplies the look.';
Disclosure.sync(result.references,referenceNote);
assert.equal(result.references.hidden,false,'Reference guidance must reveal its existing wrapper');

result=Disclosure.mount(document);
assert.equal(recipeParent.children.length,1,'Mounting twice must not create another wrapper');
assert.equal(referenceParent.children.length,1,'Mounting twice must not create another wrapper');
assert.equal(result.recipe,document.querySelector('#recipeNotesHelp'));
assert.equal(result.references,document.querySelector('#referenceBoardHelp'));
// Post-Prepare guidance is an existing renderer, not a second state owner.
const continuationParent=new Element('section','uxContinuation');
const guidance=new Element('div','uxContinuationGuidance');
guidance.textContent='Retained route explanation';
continuationParent.append(guidance);document.body.append(continuationParent);
result=Disclosure.mount(document);
assert.ok(result.continuation,'Existing continuation guidance needs an optional disclosure');
assert.equal(result.continuation.id,'continuationGuidanceHelp');
assert.equal(result.continuation.open,false);
assert.equal(result.continuation.hidden,false);
assert.equal(result.continuation.children[1],guidance);
result.continuation.open=true;
Disclosure.mount(document);
assert.equal(continuationParent.children.length,1);
assert.equal(result.continuation.open,true,'Idempotent mounting preserves an explicit reading choice');

// The shell can request the adapter before studio-workbench creates its context.
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const late=new Document(),callbacks=[];late.readyState='loading';
late.addEventListener=(type,fn,options)=>{assert.equal(type,'DOMContentLoaded');assert.equal(options.once,true);callbacks.push(fn);};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../app/static/create-progressive-disclosure.js'),'utf8'),{document:late});
assert.equal(callbacks.length,1,'Initial parser-time mount must retry once after the context is created');
const lateContext=new Element('section','uxContinuation'),lateGuidance=new Element('div','uxContinuationGuidance');
lateGuidance.textContent='Created by the following workbench script';lateContext.append(lateGuidance);late.body.append(lateContext);
callbacks[0]();
assert.equal(late.querySelector('#continuationGuidanceHelp').children[1],lateGuidance);
console.log('create progressive disclosure contracts passed');
