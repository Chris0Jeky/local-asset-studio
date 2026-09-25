// Real Workflow Studio editor in Node's VM (#772): a background re-render must not replace text the user is
// typing, and a number box and its slider must agree while either moves. No browser, no ComfyUI, no queue.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const document={activeElement:null,listeners:{}};
class Element{
  constructor(tag){this.tagName=String(tag).toUpperCase();this.children=[];this.attributes={};this.style={};this.dataset={};this.parent=null;this._value='';this.textContent='';
    this.selectionStart=0;this.selectionEnd=0;this.selectionDirection='none';this.classList={add(){},remove(){},toggle(){}};}
  get value(){return this._value;}
  set value(v){this._value=String(v);this.selectionStart=this.selectionEnd=this._value.length;}
  get valueAsNumber(){return this._value===''?NaN:Number(this._value);}
  get isConnected(){let node=this;while(node.parent)node=node.parent;return node.root===true;}
  append(...nodes){for(const n of nodes){if(n&&typeof n==='object'){n.parent=this;this.children.push(n);}}}
  // Removing the focused element hands focus back to the page, as a browser does.
  replaceChildren(...nodes){for(const c of this.children)c.parent=null;this.children=[];if(document.activeElement&&!document.activeElement.isConnected)document.activeElement=null;this.append(...nodes);}
  setAttribute(k,v){this.attributes[k]=String(v);if(k==='type')this.type=String(v);if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v);}
  getAttribute(k){return this.attributes[k]??null;}
  get descendants(){return this.children.flatMap(c=>[c,...c.descendants]);}
  matches(selector){const m=/^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(selector);if(m)return m[2]===undefined?m[1] in this.attributes:this.getAttribute(m[1])===m[2];return this.tagName===selector.toUpperCase();}
  querySelector(selector){return this.descendants.find(n=>n.matches(selector))||null;}
  querySelectorAll(selector){return this.descendants.filter(n=>n.matches(selector));}
  contains(node){return node===this||this.descendants.includes(node);}
  focus(){document.activeElement=this;}
  setSelectionRange(start,end,direction='none'){if(this.type==='number'||this.type==='range')throw Error('InvalidStateError');this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}
  checkValidity(){return true;}
  addEventListener(){}setPointerCapture(){}scrollIntoView(){}showModal(){}close(){}
  getBoundingClientRect(){return {width:900,height:560,left:0,top:0};}
}
const body=new Element('body');body.root=true;
const ids=new Map();
const $=selector=>{if(!selector.startsWith('#'))return null;if(!ids.has(selector)){const node=new Element(selector==='#workflowCanvas'?'svg':'div');node.id=selector.slice(1);body.append(node);ids.set(selector,node);}return ids.get(selector);};
Object.assign(document,{body,querySelector:$,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),createTextNode:text=>{const n=new Element('#text');n.textContent=text;return n;},
  dispatchEvent(){},addEventListener(){}});
$('#workflowName').type='text';$('#workflowName').value='Untitled workflow';$('#nodeSearch').value='';
const schema={backend_id:'primary',schema_sha256:'a'.repeat(64),nodes:{Sampler:{class_type:'Sampler',name:'Sampler',category:'sampling',description:'',outputs:[],output_node:true,inputs:[
  {name:'steps',type:'INT',widget:'number',required:true,hidden:false,options:{min:1,max:100,default:20}},
  {name:'cfg',type:'FLOAT',widget:'number',required:true,hidden:false,options:{min:0,max:30,step:0.5,default:7}},
  {name:'text',type:'STRING',widget:'text',required:true,hidden:false,options:{}}]}}};
let schemaReads=0;
const fetch=async url=>{const reply=value=>({ok:true,json:async()=>JSON.parse(JSON.stringify(value))});
  if(url.endsWith('/nodes')||url.endsWith('/nodes/refresh')){schemaReads++;return reply(schema);}
  if(url.endsWith('/guides'))return reply({guides:[]});if(url==='/api/catalog')return reply({presets:[]});throw Error('Unexpected fetch '+url);};
const context=vm.createContext({document,fetch,localStorage:{getItem:()=>null,setItem(){}},confirm:()=>true,matchMedia:()=>({matches:false}),requestAnimationFrame(){},
  innerHeight:900,URL,Blob:class{},Event:class{constructor(type){this.type=type;}},setTimeout,console});
context.window=context;
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/workflow-studio.js'),'utf8'),context);
const W=context.WorkflowStudio,inspector=$('#nodeInspector'),name=$('#workflowName');
const field=label=>inspector.querySelector('[aria-label="'+label+'"]');
const draft=(title,steps=20)=>({format:'studio.workflow/v1',name:title,revision:0,backend_id:'primary',schema_sha256:'a'.repeat(64),
  nodes:{'1':{class_type:'Sampler',inputs:{steps,cfg:7,text:'a lantern'}}},outputs:['1'],disabled:[],bypass:{},positions:{}});
const settle=()=>new Promise(r=>setTimeout(r,0));

(async()=>{
  await $('#loadNodes').onclick();await settle();
  W.load(draft('Saved name'));
  assert.equal(name.value,'Saved name','The document name renders into the box');

  // 1 · The name box keeps a half-typed name through a background re-render (schema refresh), focused or not.
  name.focus();name.value='My typed na';
  await $('#loadNodes').onclick();await settle();
  assert.equal(name.value,'My typed na','A background re-render must not overwrite the focused name box');
  name.value='My typed name';document.activeElement=null;
  const next=W.snapshot();next.positions['1']=[40,40];W.change(next);
  assert.equal(name.value,'My typed name','A re-render must not overwrite an unsent (dirty) name either');
  name.onchange();assert.equal(W.snapshot().name,'My typed name','Committing the name still records it');
  W.load(draft('Loaded document'));
  assert.equal(name.value,'Loaded document','A deliberately loaded document still brings its own name');
  const edited=W.snapshot();edited.name='Renamed elsewhere';W.change(edited);
  assert.equal(name.value,'Renamed elsewhere','An untouched name box follows the document');

  // 2 · The number box and the slider for one INT/FLOAT setting agree on every input, both ways.
  const steps=field('steps'),stepsSlider=field('steps slider');
  assert.ok(steps&&stepsSlider,'steps has a number box and a slider');
  steps.value='35';steps.oninput?.();
  assert.equal(stepsSlider.value,'35','Typing in the number box moves the slider');
  stepsSlider.value='60';stepsSlider.oninput?.();
  assert.equal(steps.value,'60','Dragging the slider updates the number box');
  const cfg=field('cfg'),cfgSlider=field('cfg slider');
  cfgSlider.value='12.5';cfgSlider.oninput?.();assert.equal(cfg.value,'12.5');
  cfg.value='3.5';cfg.oninput?.();assert.equal(cfgSlider.value,'3.5');
  cfg.value='';cfg.oninput?.();assert.equal(cfgSlider.value,'3.5','An emptied number box leaves the slider where it was');

  // 3 · Inspector fields: a half-typed value survives a background re-render, with focus and caret.
  W.load(draft('Inspector'));
  let text=field('text');text.focus();text.value='a lantern at dus';text.setSelectionRange(2,9);
  await $('#loadNodes').onclick();await settle();
  assert.notEqual(field('text'),text,'The inspector really was rebuilt');
  text=field('text');
  assert.equal(text.value,'a lantern at dus','A background re-render must not replace a half-typed inspector value');
  assert.equal(document.activeElement,text,'Focus returns to the field being typed in');
  assert.deepEqual([text.selectionStart,text.selectionEnd],[2,9],'The caret and selection return too');
  const typedSteps=field('steps');typedSteps.focus();typedSteps.value='4';
  await $('#loadNodes').onclick();await settle();
  assert.equal(field('steps').value,'4','A half-typed number survives too');
  assert.equal(document.activeElement,field('steps'));
  // Committing a value is not a draft: the re-render it causes shows the document, and an invalid entry still resets.
  field('steps').onchange();assert.equal(W.snapshot().nodes['1'].inputs.steps,4);assert.equal(field('steps').value,'4');
  const bad=field('steps');bad.value='2.5';bad.onchange();
  assert.equal(field('steps').value,'4','An invalid entry is still reset to the document value');
  // Another node's inspector does not inherit a draft.
  const two=W.snapshot();two.nodes['2']={class_type:'Sampler',inputs:{steps:9,cfg:7,text:'second'}};W.change(two);
  field('text').focus();field('text').value='unsent for node 1';
  W.inspect('2');assert.equal(field('text').value,'second','A draft is never written into another node');
  console.log('Workflow Studio keeps typed names and inspector values through re-renders; number boxes and sliders stay in sync.');
})().catch(error=>{console.error(error);process.exitCode=1;});
