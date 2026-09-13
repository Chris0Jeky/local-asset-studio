/* Run the shipped app transition functions and coach with deterministic DOM/history/HTTP seams.
 * Native rendering and browser history ordering are additionally covered by studio_guide_browser.py.
 */
const {test}=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const C=require('../app/static/studio-guide-state.js');
const root=path.join(__dirname,'../app/static'), flush=()=>new Promise(resolve=>setImmediate(resolve));
function hub() {
  const listeners=new Map();
  return {listeners,addEventListener(type,fn){if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(fn);},
    removeEventListener(type,fn){listeners.get(type)?.delete(fn);},
    dispatchEvent(event){for(const fn of [...(listeners.get(event.type)||[])])fn(event);}};
}
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.value='';this.files=[];this.textContent='';this.hidden=false;this.classList={add(){},remove(){},toggle(){}};}
  setAttribute(k,v){if(k==='class')this.className=v;else this[k]=v;}
  append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
  prepend(...nodes){for(const n of nodes)n.parent=this;this.children.unshift(...nodes);}
  replaceChildren(...nodes){for(const n of this.children)n.parent=null;this.children=[];this.append(...nodes);}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}
  contains(node){return node===this||this.children.some(n=>n.contains?.(node));}
  querySelector(){return null;} closest(){return null;} getClientRects(){return this.hidden?[]:[{}];}
  matches(){return true;} focus(){} scrollIntoView(){} addEventListener(){}
}
async function page(check='readiness',target=null) {
  const document=hub(), window=hub(), main=new Element('main'), controls=new Map(), calls=[], writes=[];
  const node=id=>{if(!controls.has(id)){const e=new Element();e.id=id;controls.set(id,e);}return controls.get(id);};
  const walk=(n,id)=>n.id===id?n:n.children.map(c=>walk(c,id)).find(Boolean);
  document.createElement=tag=>new Element(tag);
  document.getElementById=id=>walk(main,id)||controls.get(id)||null;
  document.querySelector=s=>s==='main'?main:s.startsWith('#')?node(s.slice(1)):node(s);
  document.querySelectorAll=()=>[];document.defaultView={getComputedStyle:()=>({visibility:'visible'})};
  for(const id of ['createView','positive','reference','lastReference'])node(id);
  node('positive').value='Current wording';
  let location=new URL('http://127.0.0.1:8191/?guide=fixture&stage=one#create');
  const context=vm.createContext({window,document,URL,URLSearchParams,AbortController,Event,CustomEvent,Blob,
    setInterval(){},setTimeout,clearTimeout,console,confirm:()=>true,localStorage:{getItem(){return null;},setItem(k,v){writes.push([k,v]);}},
    get location(){return location;},history:{pushState(_s,_t,url){location=new URL(url,location);},replaceState(_s,_t,url){location=new URL(url,location);}},
    fetch:async(url,options={})=>{calls.push([options.method||'GET',url]);if(url==='/api/catalog')return new Promise(()=>{});
      let data;
      if(url==='/api/workflow-studio/guides')data={guides:[{id:'fixture',title:'Fixture',steps:[
        {id:'one',title:'One',detail:'Test',check,route:'/#create',target},
        {id:'two',title:'Two',detail:'Test',check:'manual',route:'/#assets'}]}]};
      else if(url==='/api/backends')data={active:'primary',busy:false,profiles:[{id:'primary',url:'http://127.0.0.1:8188'}]};
      else if(url==='/api/health'){if(context.holdHealth)await context.holdHealth;data={online:true,schema_available:true,worker_alive:true,missing_models:{},comfy_url:'http://127.0.0.1:8188'};}
      else throw Error('Unexpected request '+url);
      return{ok:true,text:async()=>JSON.stringify(data),json:async()=>data};}});
  window.StudioGuideState=C;
  vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8'),context);
  const run=s=>vm.runInContext(s,context);
  run(`catalog={presets:[{id:'a',name:'A'},{id:'b',name:'B',runtime_block:'Fixture blocked'}]};selected=catalog.presets[0];
    var backendActive='primary';renderPresets=()=>{};renderSelected=()=>{};clearReference=()=>{};updateLoraHints=()=>{};scheduleTimeEstimate=()=>{};`);
  vm.runInContext(fs.readFileSync(path.join(root,'studio-guide.js'),'utf8'),context);await flush();
  const evidence=()=>document.getElementById('guideEvidence'), button=()=>document.getElementById('checkGuideStep');
  return {document,window,node,main,calls,writes,run,context,evidence,button,
    async ready(){await button().onclick();assert.equal(evidence().dataset.state,'met');},
    history(stage,hash){location=new URL('?guide=fixture&stage='+stage+'#'+hash,location);window.dispatchEvent(new Event('popstate'));},
    hash(hash){location.hash=hash;window.dispatchEvent(new Event('hashchange'));}};
}
test('programmatic preset selection invalidates observed readiness without an input event',async()=>{
  const p=await page();await p.ready();p.run("selectPreset('b')");assert.equal(p.evidence().dataset.state,'unknown');
  await p.button().onclick();assert.equal(p.evidence().dataset.state,'blocked');assert.match(p.evidence().textContent,/Fixture blocked/);
});
test('same-preset setup and saved import notify after their fields are applied',async()=>{
  for(const change of ["applyRecipe({preset_id:'a',name:'Tuned',controls:{positive:'New wording'}})","applySaved({preset:'a',controls:{positive:'New wording'}})"]){
    const p=await page('prompt');await p.ready();const observations=[];
    p.document.addEventListener('studio:recipe',()=>observations.push(p.node('positive').value));p.run(change);
    assert.equal(p.evidence().dataset.state,'unknown',change);assert.equal(observations.at(-1),'New wording',change);
  }
});
test('invalid preset selection does not claim a transition',async()=>{
  const p=await page();await p.ready();assert.throws(()=>p.run("selectPreset('missing')"),/unavailable/);assert.equal(p.evidence().dataset.state,'met');
});
test('A to B to A while checking discards the first recipe evidence',async()=>{
  const p=await page();let release;p.context.holdHealth=new Promise(resolve=>release=resolve);
  const checking=p.button().onclick();await flush();p.run("selectPreset('b');selectPreset('a')");release();await checking;
  assert.equal(p.evidence().dataset.state,'unknown');assert.match(p.evidence().textContent,/discarded/);
  assert.equal(p.calls.filter(x=>x[1]==='/api/health').length,1,'no automatic recheck');
});
test('popstate then paired hashchange keeps the restored manual stage',async()=>{
  const p=await page('manual');p.history('two','assets');p.window.dispatchEvent(new Event('hashchange'));
  assert.equal(p.evidence().dataset.state,'manual');p.history('one','create');p.window.dispatchEvent(new Event('hashchange'));
  assert.equal(p.evidence().dataset.state,'manual');assert.equal(p.main.children.filter(n=>n.className==='studio-guide-panel').length,1);
});
test('real tool changes and input edits still invalidate a manual stage',async()=>{
  const p=await page('manual');p.hash('assets');assert.equal(p.evidence().dataset.state,'unknown');
  p.history('two','assets');p.document.dispatchEvent({type:'input',target:p.node('positive')});
  p.window.dispatchEvent(new Event('hashchange'));assert.equal(p.evidence().dataset.state,'unknown','paired history cannot erase a newer invalidation');
});
test('history never restores a previously observed success',async()=>{
  const p=await page();await p.ready();p.history('two','assets');p.history('one','create');p.window.dispatchEvent(new Event('hashchange'));
  assert.equal(p.evidence().dataset.state,'unknown');assert.ok(p.writes.every(([,v])=>!v.includes('New wording')&&!v.includes('met')));
});
test('remount cleans listeners, and the coach does not write to HTTP APIs',async()=>{
  const p=await page();for(let i=0;i<3;i++){p.history('two','assets');p.history('one','create');}
  assert.equal(p.document.listeners.get('studio:recipe')?.size,1);assert.equal(p.window.listeners.get('hashchange')?.size,1);
  p.main.children[0].children.flatMap(n=>n.children).find(n=>n.textContent==='Pause guide').onclick();
  assert.equal(p.document.listeners.get('studio:recipe')?.size,0);assert.equal(p.window.listeners.get('hashchange')?.size,0);
  assert.ok(p.calls.every(([method])=>method==='GET'));
});
test('the real picker, variation, seed and mode handlers notify without text input',async()=>{
  const actions=[
    p=>p.node('presetList').onclick({target:{closest:()=>({dataset:{id:'b'}})}}),
    p=>p.node('variants').onclick({target:{closest:()=>({dataset:{variant:'0'}})}}),
    p=>p.node('randomSeed').onclick(),
    p=>p.run("selected.i2v_modes=[{id:'test',name:'Fixture mode',controls:{positive:'Mode wording'}}];updateReady=()=>{};applyI2VMode('test')"),
  ];
  for(const action of actions){const p=await page();await p.ready();action(p);assert.equal(p.evidence().dataset.state,'unknown');}
});

test('recipe selection refreshes guide targets after rendering without losing early invalidation',async()=>{
  const p=await page('prompt','#reference');p.node('reference').hidden=true;await p.ready();
  p.run(`renderSelected=()=>{window.stateDuringRender=document.getElementById('guideEvidence').dataset.state;
    $('#reference').hidden=selected.id!=='b';};selectPreset('b');`);
  assert.equal(p.window.stateDuringRender,'unknown','old evidence is invalid before rendering');
  assert.match(p.document.getElementById('guideTargetStatus').textContent,/Target control is available/,'newly visible target discovered without clicking Show');
  p.run("selectPreset('a')");
  assert.match(p.document.getElementById('guideTargetStatus').textContent,/not visible/,'hidden target is no longer offered');
  await p.ready();p.run("renderSelected=()=>{throw Error('Fixture render failure');}");
  assert.throws(()=>p.run("selectPreset('b')"),/Fixture render failure/);
  assert.equal(p.evidence().dataset.state,'unknown','failed render cannot keep old success');
});
