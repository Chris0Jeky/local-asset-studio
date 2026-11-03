'use strict';
// One shared switch for a wrong model environment (QA pass 3 Nov 2026, journeys-1 / manage-3): the Library picture dialog and Compare & review
// show a Switch button with its cost instead of a dead-end sentence. Real backends.js, asset-family.js and production.js; no browser, no ComfyUI, nothing generated.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8');
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// backends.js in a fake page: two environments, Main library running. #switchBackend.click() starts a "switch"; the test settles it.
function environments(){
  const nodes=new Map(),ticks=[],clicks=[];
  const options=[{value:'primary',textContent:'Main library · online'},{value:'moss',textContent:'MOSS-Image · isolated'}];
  const $=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'primary',textContent:'',disabled:false,hidden:false,checked:false,classList:{toggle(){}}});return nodes.get(selector);};
  const choice=$('#backendChoice'),go=$('#switchBackend');
  Object.defineProperty(choice,'value',{get(){return this._v??'primary';},set(v){if(options.some(o=>o.value===v))this._v=v;}});
  go.click=()=>{clicks.push(choice.value);vm.runInContext('backendSwitching=true',context);};
  const context=vm.createContext({$,esc,document:{querySelectorAll:()=>options,createElement:()=>({innerHTML:''}),activeElement:null},setInterval:cb=>{ticks.push(cb);return ticks.length;},clearInterval(){},
    controlKeys:[],updateReady(){},Date});
  vm.runInContext(read('backends.js').replace('refreshBackends();setInterval(','setInterval('),context);
  vm.runInContext("backendActive='primary'",context);
  const settle=(active,status='')=>{vm.runInContext('backendSwitching=false;backendActive='+JSON.stringify(active),context);$('#backendStatus').textContent=status;ticks.at(-1)();};
  return {context,$,clicks,settle,env:vm.runInContext('StudioEnvironment',context)};
}

test('the shared helper renders a labelled button with its cost, and reports success and refusals without generating',()=>{
  const f=environments(),reports=[];let done=0;
  const html=f.env.markup('moss');
  assert.match(html,/<button type="button"[^>]*data-env-switch="moss"[^>]*>Switch to MOSS-Image · isolated<\/button>/);
  assert.match(html,/Stops Main library\. About a minute\. Nothing is generated\./);
  for(const text of ['Switch to MOSS-Image · isolated to use this recipe.','Switch to MOSS-Image · isolated before starting it','Switch to MOSS-Image · isolated before resuming it'])assert.equal(f.env.target(text)?.id,'moss',text);
  assert.equal(f.env.target('Switch to Nowhere to use this recipe.'),null);assert.equal(f.env.target('Wait for the backend switch to finish'),null);
  f.env.switchTo('moss','MOSS-Image · isolated',(m,e)=>reports.push([m,!!e]),()=>done++);
  assert.deepEqual(Array.from(f.clicks),['moss'],'one press of the existing #switchBackend path');
  assert.match(reports[0][0],/^Switching to MOSS-Image · isolated… Nothing is generated\./);
  f.settle('moss');
  assert.deepEqual(reports.at(-1),['MOSS-Image · isolated is running. Nothing was generated. Try again.',false]);assert.equal(done,1);
  // A refusal reports the server's reason and keeps the old environment.
  const refused=[];f.env.switchTo('primary','Main library',(m,e)=>refused.push([m,!!e]));f.settle('moss','Studio work is running. Finish it first.');
  assert.deepEqual(refused.at(-1),['Did not switch to Main library: Studio work is running. Finish it first. Nothing was generated.',true]);
  // Busy or unknown environments never click anything.
  f.$('#switchBackend').disabled=true;const busy=[];f.env.switchTo('moss','MOSS-Image · isolated',(m,e)=>busy.push([m,!!e]));
  assert.equal(f.clicks.length,2);assert.equal(busy[0][1],true);
});

// asset-family.js on a fake dialog, wired to the real helper.
function dialog(env){
  const elements=new Map(),statusListeners=[];
  class Element{
    constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.listeners={};this.hidden=false;this.isConnected=true;this.innerHTML='';
      this.classList={add(){},remove(){},toggle(){}};}
    set id(value){this._id=value;elements.set(value,this);}get id(){return this._id;}
    set textContent(value){this._text=value;this.children=[];}get textContent(){return this._text??'';}
    append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;this.innerHTML='';}
    before(){}after(){}setAttribute(){}removeAttribute(){}hasAttribute(){return false;}addEventListener(name,callback){this.listeners[name]=callback;}
    contains(value){return this===value||this.children.some(node=>node.contains?.(value));}querySelector(s){return document.querySelector(s);}
  }
  const document={querySelector:s=>elements.get(s.slice(1))||null,querySelectorAll:()=>[],createElement:tag=>new Element(tag)};
  for(const id of ['assetDialog','assetLineage','assetDetailMedia','assetFamilyActions','assetFamilyStatus','assetFamilyTree','assetFamilyChildren']){const e=new Element();e.id=id;}
  elements.get('assetDialog').open=true;document.body=new Element('body');document.activeElement=document.body;
  return {document,elements,Element,statusListeners};
}
test('Library: "Same recipe, new seed" on a recipe from another environment shows the Switch button, and pressing it switches',async()=>{
  let failure='Switch to MOSS-Image · isolated to use this recipe.';const F=require('../app/static/asset-family.js'),f=environments(),d=dialog(f.env),scope='a'.repeat(32),hash='b'.repeat(64),messages=[];
  const prior=globalThis.StudioEnvironment;globalThis.StudioEnvironment=f.env;
  try{
    const record={version:1,asset_id:'one',workspace_id:scope,observation_only:true,generation_submitted:false,media_bytes_verified:false,recipe:{preset_id:'moss-look',controls:{seed:'7'}},controls:{seed:'7'}};
    const report={version:1,asset_id:'one',workspace_id:scope,nodes:[{id:'one',state:'active',title:'One',operation:null,seed:null,strength:null}],edges:[],gaps:[],children:null,truncated:false,children_truncated:false,children_scanned:0,observation_only:true,generation_submitted:false,media_bytes_verified:false};
    const options={document:d.document,asset:()=>({id:'one',media_type:'image'}),comparisonContext:()=>({workspace:scope,session:'detail',stamp:'detail'}),context:()=>({workspace:scope,stamp:'detail'}),say:m=>messages.push(m),
      read:async url=>url.includes('/recall/')?record:report,check:async()=>{throw Error(failure);},confirm:()=>true,apply(){throw Error('must not apply');}};
    const family=F.install(options);await family.opened();
    const actions=d.elements.get('assetFamilyActions'),recall=actions.children[0].children.find(b=>b.dataset.familyRecall==='new');
    await actions.listeners.click({target:{closest:()=>recall}});
    const status=d.elements.get('assetFamilyStatus');
    assert.equal(status.textContent,'Switch to MOSS-Image · isolated to use this recipe.');
    const box=status.children.find(n=>/data-env-switch="moss"/.test(n.innerHTML||''));
    assert.ok(box,'the refusal carries a Switch button');assert.match(box.innerHTML,/Stops Main library\. About a minute\. Nothing is generated\./);
    assert.equal(typeof status.listeners.click,'function','the status line handles the press');
    await status.listeners.click({target:{closest:()=>({dataset:{envSwitch:'moss',envName:'MOSS-Image · isolated'},disabled:false})}});
    assert.deepEqual(Array.from(f.clicks),['moss']);assert.match(status.textContent,/^Switching to MOSS-Image · isolated…/);
    f.settle('moss');assert.match(status.textContent,/^MOSS-Image · isolated is running\. Nothing was generated\./);
    // Other failures stay plain text.
    failure='The retained recipe did not validate.';
    await actions.listeners.click({target:{closest:()=>recall}});
    assert.equal(status.children.some(n=>/data-env-switch/.test(n.innerHTML||'')),false);
  }finally{if(prior===undefined)delete globalThis.StudioEnvironment;else globalThis.StudioEnvironment=prior;}
});

// production.js rendering a plan prepared in another environment.
test('Compare & review: a plan from another environment disables Start with its reason and a Switch button beside it',async()=>{
  const f=environments(),elements=new Map(),requests=[],messages=[];
  const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
  const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,safeUrl:u=>u,setInterval(){},showView(){},StudioEnvironment:f.env,api:async()=>[],post:async(url,data)=>{requests.push(url);return {};}});
  vm.runInContext(read('production.js'),context);
  const plan={id:'d'.repeat(32),name:'MOSS study',kind:'comparison',axis:'steps',values:[8,20],created_at:Date.now()/1000,recipe:{preset_id:'moss-look'},budget:{reserved:2,allowance:4},stages:[],
    state:{status:'planned',message:'Ready for explicit Start. No generation submitted.',artifacts:[]}};
  const render=value=>vm.runInContext(`productionPlans=${JSON.stringify([value])};productionId=${JSON.stringify(plan.id)};renderProduction();`,context);
  render(plan);assert.doesNotMatch($('#productionDetail').innerHTML,/data-env-switch/);assert.doesNotMatch($('#productionDetail').innerHTML,/data-project-action="start" disabled/);
  render({...plan,backend_id:'moss',runtime_block:'Switch to MOSS-Image · isolated before starting it'});
  const html=$('#productionDetail').innerHTML;
  assert.match(html,/data-project-action="start" disabled/,'Start is disabled, not failing after the press');
  assert.match(html,/Runs in MOSS-Image · isolated, not the running environment\./);
  assert.match(html,/data-env-switch="moss"[^>]*>Switch to MOSS-Image · isolated<\/button>/);assert.match(html,/Stops Main library\. About a minute\. Nothing is generated\./);
  render({...plan,state:{...plan.state,status:'interrupted'},backend_id:'moss',runtime_block:'Switch to MOSS-Image · isolated before resuming it'});
  assert.match($('#productionDetail').innerHTML,/data-project-action="resume" disabled/);
  // Pressing Switch goes through the existing switch path, then re-reads the plans; it never starts the plan.
  const button={dataset:{envSwitch:'moss',envName:'MOSS-Image · isolated'},disabled:false};
  $('#productionMessage');await $('#productionDetail').onclick({target:{closest:s=>s==='[data-env-switch]'?button:null}});
  assert.deepEqual(Array.from(f.clicks),['moss']);assert.match($('#productionMessage').textContent,/^Switching to MOSS-Image · isolated…/);assert.deepEqual(requests,[]);
});
