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
// Wildcard disclosure: availability, focus handoff, Escape, toggle and recipe refresh (fake DOM with events and focus).
{
  class Node2 {
    constructor(doc,tag,id=''){this.doc=doc;this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.parentNode=null;this.hidden=false;this.open=false;this.dataset={};this.listeners={};this.textContent='';}
    append(...items){for(const item of items){if(item.parentNode)item.parentNode.children=item.parentNode.children.filter(c=>c!==item);item.parentNode=this;this.children.push(item);}}
    after(item){const parent=this.parentNode;if(item.parentNode)item.parentNode.children=item.parentNode.children.filter(c=>c!==item);item.parentNode=parent;parent.children.splice(parent.children.indexOf(this)+1,0,item);}
    contains(node){for(let n=node;n;n=n.parentNode)if(n===this)return true;return false;}
    querySelector(selector){const visit=n=>{for(const c of n.children){if(selector==='[data-wildcard]'&&c.dataset.wildcard!==undefined)return c;const f=visit(c);if(f)return f;}return null;};return visit(this);}
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    emit(type,event={}){for(const fn of this.listeners[type]||[])fn(event);}
    focus(){this.doc.activeElement=this;}
  }
  class Doc2 {
    constructor(){this.body=new Node2(this,'body');this.activeElement=null;this.listeners={};this.defaultView={};}
    createElement(tag){return new Node2(this,tag);}
    querySelector(selector){const id=selector.slice(1),visit=n=>{if(n.id===id)return n;for(const c of n.children){const f=visit(c);if(f)return f;}return null;};return visit(this.body);}
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    emit(type){for(const fn of this.listeners[type]||[])fn({});}
  }
  const doc=new Doc2(),label=new Node2(doc,'label','positiveWrap'),prompt=new Node2(doc,'textarea','positive'),host=new Node2(doc,'div','wildcardChips');
  const chip=new Node2(doc,'button');chip.dataset.wildcard='lighting';host.append(chip);label.append(prompt,host);doc.body.append(label);
  const details=Disclosure.mount(doc).wildcards;
  assert.equal(details.id,'promptWildcards');assert.equal(details.parentNode,doc.body,'the disclosure sits after the prompt label');
  assert.equal(details.children[1],host,'the existing chip host moves inside, not a copy');
  assert.equal(details.hidden,false,'available chips show the disclosure');assert.equal(details.open,false);
  const summary=details.children[0];
  details.open=true;let prevented=false;
  details.emit('keydown',{key:'Escape',preventDefault(){prevented=true;},stopPropagation(){}});
  assert.equal(details.open,false);assert.equal(prevented,true);assert.equal(doc.activeElement,summary,'Escape closes and returns focus to the summary');
  chip.focus();details.open=false;details.emit('toggle');
  assert.equal(doc.activeElement,summary,'closing with focus inside moves focus to the summary, not into hidden chips');
  details.open=true;doc.emit('studio:recipe');assert.equal(details.open,false,'a refresh closes the disclosure');assert.equal(details.hidden,false);
  chip.focus();delete chip.dataset.wildcard;
  doc.emit('studio:recipe');
  assert.equal(details.hidden,true,'a recipe without wildcards hides the disclosure');
  assert.equal(doc.activeElement,prompt,'focus inside a disappearing disclosure returns to the prompt');
  assert.equal(Disclosure.mount(doc).wildcards,details,'mounting again reuses the disclosure');
}
// observe() caches one observer per disclosure and watches text changes; sync/wrap guard missing nodes.
{
  const observed=[];class FakeObserver{constructor(fn){this.fn=fn;}observe(target,options){observed.push({target,options});}}
  const doc={defaultView:{MutationObserver:FakeObserver}},details={hidden:false},target={textContent:''};
  const first=Disclosure.observe(doc,details,target),second=Disclosure.observe(doc,details,target);
  assert.ok(first instanceof FakeObserver);assert.equal(second,first,'one observer per disclosure');
  assert.equal(observed.length,1);assert.deepEqual(observed[0].options,{childList:true,subtree:true,characterData:true});
  assert.equal(details.hidden,true,'observe syncs immediately');
  target.textContent='Now there is guidance';first.fn();assert.equal(details.hidden,false,'a mutation re-syncs visibility');
  assert.equal(Disclosure.observe({defaultView:{}},{hidden:false},target),null,'no MutationObserver means no observer, not a throw');
  assert.equal(Disclosure.sync(null,target),null);assert.equal(Disclosure.sync(details,null),null);
  assert.equal(Disclosure.wrap(new Document(),'missing','missingHelp','Summary'),null);
}
console.log('create progressive disclosure contracts passed');
