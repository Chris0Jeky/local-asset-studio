'use strict';
const assert = require('node:assert/strict');
const Disclosure = require('../app/static/create-progressive-disclosure.js');

class Element {
  constructor(tag, id='') { this.tagName=tag.toUpperCase(); this.id=id; this.children=[]; this.parentNode=null; this.open=false; this.className=''; this.textContent=''; }
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
assert.equal(result.recipe.children[0].tagName,'SUMMARY');
assert.equal(result.recipe.children[0].textContent,'Why this recipe?');
assert.equal(result.recipe.children[1],recipeNotes,'The existing recipeNotes owner must be preserved');
assert.equal(result.references.id,'referenceBoardHelp');
assert.equal(result.references.open,false);
assert.equal(result.references.children[0].textContent,'How are these references used?');
assert.equal(result.references.children[1],referenceNote,'The existing referenceBoardNote owner must be preserved');

result=Disclosure.mount(document);
assert.equal(recipeParent.children.length,1,'Mounting twice must not create another wrapper');
assert.equal(referenceParent.children.length,1,'Mounting twice must not create another wrapper');
assert.equal(result.recipe,document.querySelector('#recipeNotesHelp'));
assert.equal(result.references,document.querySelector('#referenceBoardHelp'));
console.log('create progressive disclosure contracts passed');
