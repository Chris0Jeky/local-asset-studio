// Drive the actual page handlers: opening it, validating, preparing and uncertain responses.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),schema=JSON.parse(fs.readFileSync(path.join(root,'scripts/procgen_generators.json')));
const code=fs.readFileSync(path.join(root,'app/static/procedural.js'),'utf8');
const response=data=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>data});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function element(){return {value:'',checked:false,disabled:false,hidden:false,innerHTML:'',textContent:'',title:'',classList:{toggle(){}},reportValidity:()=>true,querySelectorAll:()=>[]};}
function page(ready=false){
  const elements=new Map(),calls=[],$=selector=>{if(!elements.has(selector))elements.set(selector,element());return elements.get(selector);};
  $('#proceduralName').value='Test crate';$('#proceduralRender').checked=true;
  const catalog={generators:schema.generators,units:schema.units,runtime:{ready,missing:ready?[]:['Set Blender in config/local.json'],godot_available:ready,note:'Blender 5.4 is required; checks configured files only.'}};
  let post=async()=>response({id:'a'.repeat(32),name:'Test crate',kind:'procedural',state:{status:'planned'}});
  const context=vm.createContext({document:{querySelector:$},fetch:async(url,options={})=>{calls.push({url,...options});return options.method==='POST'?post(url,options):response(catalog);}});
  vm.runInContext(code,context);
  return {$,calls,context,catalog,setPost:fn=>post=fn};
}
async function preparation(){
  const p=page();await settle();const {$,calls,context}=p;
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/procedural');assert.equal(calls[0].method,undefined);
  assert.equal($('#proceduralPrepare').disabled,true);assert.match($('#proceduralRuntime').innerHTML,/Blender/);
  assert.equal(($('#proceduralGenerator').innerHTML.match(/<option /g)||[]).length,8);
  $('#proceduralGenerator').value='prop';$('#proceduralGenerator').onchange();
  for(const [key,spec] of Object.entries(schema.generators.prop.params))$('#proceduralParam-'+key).value=String(spec.default);
  $('#proceduralParam-kind').value='1';
  p.setPost(async(url,options)=>{assert.equal(url,'/api/procedural/validate');const body=JSON.parse(options.body);assert.equal(body.params.kind,1);assert.equal(typeof body.params.width,'number');return response({intent:body,generation_submitted:false});});
  await $('#proceduralCheck').onclick();assert.match($('#proceduralStatus').textContent,/valid/i);assert.equal(calls.length,2);
  await $('#proceduralForm').onsubmit({preventDefault(){}});assert.equal(calls.length,2,'Missing runtime cannot create a plan');
  p.catalog.runtime.ready=true;p.catalog.runtime.missing=[];await $('#proceduralRefresh').onclick();
  let finish;p.setPost(()=>new Promise(resolve=>finish=resolve));
  const first=$('#proceduralForm').onsubmit({preventDefault(){}}),second=$('#proceduralForm').onsubmit({preventDefault(){}});
  assert.equal(calls.filter(c=>c.url==='/api/procedural'&&c.method==='POST').length,1,'Rapid duplicate prepare is suppressed');
  assert.equal($('#proceduralFields').disabled,true,'Draft cannot change while its preparation is pending');
  finish(response({id:'a'.repeat(32),name:'Test crate',kind:'procedural',state:{status:'planned'}}));await Promise.all([first,second]);
  assert.equal($('#proceduralFields').disabled,false);assert.match($('#proceduralPrepared').innerHTML,/\?plan=a{32}#production/);
  assert.match($('#proceduralPrepared').innerHTML,/Start build/);assert.ok(calls.every(c=>!c.url.endsWith('/start')));
  p.setPost(async()=>{throw Error('response lost');});await $('#proceduralForm').onsubmit({preventDefault(){}});
  assert.match($('#proceduralStatus').textContent,/outcome.*not confirmed/i);assert.match($('#proceduralPrepared').innerHTML,/\?plan=a{32}#production/,'Previous retained plan link survives response loss');
  const count=calls.length;await settle();assert.equal(calls.length,count,'Uncertain prepare is never retried automatically');
  p.setPost(async()=>({ok:false,status:500,headers:{get:()=> 'application/json'},json:async()=>({error:'Project storage could not confirm the result.'})}));
  await $('#proceduralForm').onsubmit({preventDefault(){}});assert.match($('#proceduralStatus').textContent,/outcome.*not confirmed/i,'A server failure can happen after project persistence');
  assert.throws(()=>vm.runInContext('StudioProcedural.parameters({width:{type:"float",min:1,max:4}}, {width:""})',context),/number/);
  assert.throws(()=>vm.runInContext('StudioProcedural.parameters({detail:{type:"int",min:4,max:48}}, {detail:"4.5"})',context),/integer/);
  assert.throws(()=>vm.runInContext('StudioProcedural.parameters({width:{type:"float",min:1,max:4}}, {width:"Infinity"})',context),/number/);
}
function production(){
  const elements=new Map(),$=s=>{if(!elements.has(s))elements.set(s,element());return elements.get(s);};
  const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc:v=>String(v),api:async()=>[],post:async()=>({}),setInterval(){},showView(){}});
  vm.runInContext(fs.readFileSync(path.join(root,'app/static/production.js'),'utf8'),context);
  const p={id:'b'.repeat(32),name:'Test crate',kind:'procedural',stages:[],procedural:{generator:'prop',params:{kind:1,width:.6},verify_engine:false,render:true},state:{status:'planned',message:'Prepared',artifacts:[]}};
  vm.runInContext(`productionPlans=[${JSON.stringify(p)}];productionId='${p.id}';renderProduction()`,context);
  assert.match($('#productionDetail').innerHTML,/Start build/);assert.match($('#productionDetail').innerHTML,/Godot/);
  p.state.status='completed';p.state.procedural_verification={state:'incomplete',gates:[{gate:'triangle_budget',passed:true},{gate:'godot_import',passed:null}]};
  p.state.artifacts=[{path:'procedural/asset_LOD0.glb',url:'/fixture.glb',role:'procedural-model',asset_id:'c'.repeat(32)}];
  vm.runInContext(`productionPlans=[${JSON.stringify(p)}];renderProduction()`,context);
  const html=$('#productionDetail').innerHTML;assert.match(html,/model-viewer/);assert.match(html,/Godot.*not checked/i);assert.doesNotMatch(html,/autoplay/);
  assert.match(html,/data-candidate-open="c{32}"/);assert.match(html,/Prepare another asset/);
  assert.equal(vm.runInContext(`planKindNoun(${JSON.stringify(p)})`,context),'Procedural asset');
  const shell=fs.readFileSync(path.join(root,'app/static/studio-shell.js'),'utf8');assert.match(shell,/'procedural','Procedural assets'/);assert.match(shell,/location\.pathname\.includes\('procedural\.html'\)/);
}
(async()=>{await preparation();production();console.log('Procedural discovery, typed settings, explicit preparation, recovery and result contracts passed.');})().catch(error=>{console.error(error);process.exitCode=1;});
