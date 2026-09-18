// The actual Prompt Lab draft owner, not an independent fake state machine.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = new Map();
function node() { return {value:'',textContent:'',hidden:false,disabled:false,children:[],listeners:{},
  addEventListener(k,f){this.listeners[k]=f;},append(...x){this.children.push(...x);},replaceChildren(...x){this.children=x;},querySelectorAll(){return [];}}; }
const element = id => {if(!elements.has(id))elements.set(id,node());return elements.get(id);};
const context = vm.createContext({document:{getElementById:element,createElement:node},
  fetch:async()=>({ok:true,json:async()=>({profiles:[]})})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/prompt-lab.js'),'utf8'),context);
const bridge = context.StudioPromptDraft;
assert.ok(bridge,'Prompt Lab must expose its guarded current-draft adapter');
element('brief').value='My original brief';
const snapshot=bridge.capture();
assert.equal(snapshot.intent.brief,'My original brief');
const preview = ticket => ({format:'studio.reference-transfer-preview/v1',base_intent:ticket.intent,
  intent:{...JSON.parse(ticket.json),brief:'Reviewed interpretation'},generation_submitted:false,inference_submitted:false,execution_authorized:false});
let candidate=preview(snapshot);
element('brief').value='A newer manual change';
assert.throws(()=>bridge.apply(snapshot,candidate),/changed/i,'Even an input not yet reported by an event is newer work');
assert.equal(element('brief').value,'A newer manual change');
const fresh=bridge.capture();
candidate=preview(fresh); candidate.base_intent={...fresh.intent,brief:'Another client'};
assert.throws(()=>bridge.apply(fresh,candidate),/match/i,'A reply for another base cannot apply');
assert.equal(element('brief').value,'A newer manual change');
candidate=preview(fresh); const receipt=bridge.apply(fresh,candidate);
assert.equal(element('brief').value,'Reviewed interpretation');
assert.throws(()=>bridge.apply(fresh,candidate),/changed/i,'Applying twice must not repeat the old write');
bridge.undo(receipt);
assert.equal(element('brief').value,'A newer manual change','Undo preserves the exact earlier user draft');
const again=bridge.capture(); const later=bridge.apply(again,preview(again));
element('style').value='My later style edit';
assert.throws(()=>bridge.undo(later),/changed/i,'Undo cannot overwrite a subsequent manual edit');
assert.equal(element('style').value,'My later style edit');
const now=bridge.capture();const forged=preview(now);forged.generation_submitted=true;
assert.throws(()=>bridge.apply(now,forged),/preview/i);
assert.equal(element('style').value,'My later style edit');
const commaBase=bridge.capture(); const commaPreview=preview(commaBase);
commaPreview.intent.tags=['ink, bold']; commaPreview.intent.avoid=['text, logos'];
bridge.apply(commaBase,commaPreview);
assert.equal(JSON.stringify(bridge.capture().intent.tags),JSON.stringify(['ink, bold']),'Displaying a selected tag must not split its original value');
assert.equal(JSON.stringify(bridge.capture().intent.avoid),JSON.stringify(['text, logos']));
console.log('Reference review draft guards passed');
