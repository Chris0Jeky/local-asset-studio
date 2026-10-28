// Execute shipped Make migration functions and listener; storage and rendering are inert doubles.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {test}=require('node:test');
const source=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8');
const section=(a,b)=>{assert.ok(source.includes(a)&&source.includes(b));return source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));};
const DRAFT='studio.make.picture-draft',TEXT='Keep the exact synthetic private wording.';
function store(){const data=new Map();return{data,getItem:k=>data.get(k)??null,setItem(k,v){data.set(k,String(v));},removeItem:k=>data.delete(k)};}
function fixture({scene=false,mode='throw'}={}){
  const localStorage=store(),sessionStorage=store(),events=new Map(),nodes=new Map();
  let privacy='regular',scope='regular';
  const field={value:scene?TEXT:''},warning={hidden:true,textContent:''};
  const state={goal:scene?'character':'edit',look:scene?'look':null,pick:scene?null:{id:'asset-1',workspace_id:'1'.repeat(32),privacy:'regular'},form:scene?{}:{change:TEXT},pose:null,
    runs:[],characters:[],review:{},polish:{},queries:{},openers:new Set(),tune:{},sweeps:{}};
  const context={Map,Set,JSON,structuredClone,console,localStorage,sessionStorage,state,GOALS:[{id:'edit',intent:'edit'},{id:'character',looks:['look']}],POLISH:{face:'Face'},
    view:{dataset:{},addEventListener(){}},q:s=>s==='#makeScene'?(scene?field:null):s==='#makeDraftWarning'?warning:nodes.get(s)||null,
    window:{StudioPrivacy:{creation:()=>privacy,scope:()=>scope}},document:{addEventListener:(name,listener)=>events.set(name,listener)},PE:()=>null,
    TUNES:'studio.make.tune',savedTunes:{},timers:new Map(),planning:new Set(),clearTimeout(){},clearCharForms(){},readSavedRuns:()=>[],restoredRuns:false,savedRuns:[],
    render(){},load(){},json:async(path,body)=>({workspace_id:'1'.repeat(32),items:body.ids.map(id=>({id,state:'active',asset:{id,workspace_id:'1'.repeat(32),privacy:'regular',media_type:'image'}}))})};
  vm.createContext(context);
  vm.runInContext(section('  const creationPrivacy=','  const json=')+section('  const classified=','  // Curated,')+section('  const DRAFT_KEY=','  window.StudioMake='),context);
  context.load=()=>vm.runInContext('restoreDraft(readDraft()).then(()=>{draftReady=true;view.dataset.draftState="ready";})',context);
  vm.runInContext('draftReady=true;rememberDraft()',context);
  const before=sessionStorage.getItem(DRAFT),original=sessionStorage.setItem.bind(sessionStorage);
  sessionStorage.setItem=(key,value)=>{if(key===DRAFT+'.private'){
    if(mode==='throw')throw Error('quota');if(mode==='drop')return;
  }original(key,value);};
  return {context,state,sessionStorage,localStorage,warning,before,
    async migrate(){const previousCreation=privacy;privacy='private';events.get('studio:privacy-change')({detail:{previousCreation,creation:privacy}});await context.load();},
    async browse(){scope='all';events.get('studio:privacy-change')({detail:{previousCreation:privacy,creation:privacy}});await context.load();},
    retry(){sessionStorage.setItem=original;vm.runInContext('draftReady=true;rememberDraft()',context);}};
}
for(const scene of [false,true])for(const mode of ['throw','drop'])test(`${scene?'scene':'picture'} draft survives ${mode} persistence refusal`,async()=>{
  const f=fixture({scene,mode});await f.migrate();
  assert.equal(f.sessionStorage.getItem(DRAFT),f.before,'retire no regular bytes before verified private write');
  if(!scene){assert.equal(f.state.pick.id,'asset-1');assert.equal(f.state.form.change,TEXT);}
  assert.equal(vm.runInContext('readDraft().scene',f.context),scene?TEXT:'');
  assert.equal(f.warning.hidden,false);assert.match(f.warning.textContent,/Keep this page open/);
  await f.browse();if(!scene)assert.equal(f.state.form.change,TEXT);
  assert.ok(!JSON.stringify([...f.localStorage.data]).includes(TEXT));
  f.retry();assert.ok(f.sessionStorage.getItem(DRAFT+'.private').includes(TEXT));assert.equal(f.warning.hidden,true);
});
test('successful private persistence permits retiring the regular draft',async()=>{
  const f=fixture({mode:'pass'});await f.migrate();assert.equal(f.sessionStorage.getItem(DRAFT),null);
  assert.equal(f.state.pick.id,'asset-1');assert.equal(f.state.form.change,TEXT);
  assert.ok(f.sessionStorage.getItem(DRAFT+'.private').includes(TEXT));
});
test('explicit Make navigation overrides a recovered goal and uses the active privacy namespace',async()=>{
  const f=fixture({mode:'pass'});await f.migrate();
  assert.equal(typeof f.context.chooseNavigation,'function');
  f.context.remember=()=>vm.runInContext('rememberDraft()',f.context);
  assert.equal(f.context.chooseNavigation({goal:'character',look:'look'}),true);
  assert.equal(f.state.goal,'character');assert.equal(f.state.look,'look');
  assert.equal(f.state.form.change,TEXT,'navigation does not erase current answers');
  assert.equal(JSON.parse(f.sessionStorage.getItem(DRAFT+'.private')).goal,'character');
  assert.equal(f.localStorage.data.size,0);
  assert.equal(f.context.chooseNavigation({goal:'unknown',look:'look'}),false);
  assert.equal(f.context.chooseNavigation({goal:'character',look:'foreign-look'}),false);
  assert.equal(f.state.goal,'character');
});
test('scene recovery survives a selective scene-key storage refusal',async()=>{
  const f=fixture({scene:true,mode:'pass'}),original=f.sessionStorage.setItem.bind(f.sessionStorage);
  f.sessionStorage.setItem=(key,value)=>{if(key==='studio.make.scene.character.private')throw Error('scene quota');original(key,value);};
  await f.migrate();assert.equal(vm.runInContext('sceneDraftValue()',f.context),TEXT);
});
for(const mode of ['throw','drop'])test(`private tune survives selective ${mode} migration failure without retiring regular recovery`,async()=>{
  const f=fixture({scene:true,mode:'pass'}),own={rev:'synthetic',negative:'Synthetic private tuning',rows:[],cleared:[]};
  f.context.savedTunes.look=own;f.localStorage.setItem('studio.make.tune',JSON.stringify({look:own}));
  const original=f.sessionStorage.setItem.bind(f.sessionStorage);
  f.sessionStorage.setItem=(key,value)=>{if(key==='studio.make.tune.private'){if(mode==='throw')throw Error('tune quota');return;}original(key,value);};
  await f.migrate();assert.equal(f.context.savedTunes.look?.negative,own.negative);
  assert.equal(f.localStorage.getItem('studio.make.tune'),JSON.stringify({look:own}));
  assert.equal(f.sessionStorage.getItem(DRAFT),f.before);assert.equal(f.warning.hidden,false);
  await f.browse();assert.equal(f.context.savedTunes.look?.negative,own.negative);
});
