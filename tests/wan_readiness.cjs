// Execute shipped Create handlers; the only held request is page-start catalogue loading.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
let failures=0;
function sandbox(){
  const elements=new Map(),listeners={};let requests=0;
  const element=s=>{
    if(!elements.has(s))elements.set(s,{value:'',files:[],textContent:'',classList:{toggle(){}},addEventListener(){}});
    return elements.get(s);
  };
  const context=vm.createContext({URL,window:{},location:{hash:''},setInterval(){},
    document:{querySelector:element,querySelectorAll:()=>[],addEventListener(n,fn){(listeners[n]??=[]).push(fn);}},
    fetch:()=>{requests++;return new Promise(()=>{});}});
  const run=s=>vm.runInContext(s,context);
  run(fs.readFileSync(__dirname+'/../app/static/app.js','utf8'));
  run('scheduleTimeEstimate=()=>{};online=schemaAvailable=true;continuationBlockers=()=>[];');
  function load(item){
    run('catalog='+JSON.stringify({presets:[item.preset]})+';selected=catalog.presets[0]');element('#i2vMode').value=item.mode||'';
    for(const k of ['width','height','frames'])element('[data-key="'+k+'"]').value=item.values[k]??'';
    run('updateReady()');
  }
  return {element,run,load,listeners,requests:()=>requests};
}
function test(name,fn){try{fn();console.log('PASS '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
for(const item of cases)test(item.name,()=>{
  const s=sandbox();s.load(item);
  assert.equal(Boolean(s.run('i2vModeBlocker()')),item.blocked);
  assert.equal(Boolean(s.element('#generate').disabled),item.blocked);
  assert.equal(s.requests(),1,'Readiness must not request preparation or dispatch');
});
const t2v=cases.find(c=>c.preset.id==='wan22-t2v');
test('typing updates readiness without waiting for a health poll',()=>{
  const s=sandbox();s.load(t2v);
  const control=s.element('[data-key="frames"]');control.value='33';
  assert.equal(typeof s.element('#controls').oninput,'function','Missing control input readiness handler');
  s.element('#controls').oninput({target:control});assert.equal(Boolean(s.element('#generate').disabled),false);
  control.value='81';s.element('#controls').onchange({target:control});assert.equal(Boolean(s.element('#generate').disabled),true);
});
test('variant and named recipe changes immediately recompute',()=>{
  const s=sandbox();s.load(t2v);
  s.element('#variants').onclick({target:{closest:()=>({dataset:{variant:String(t2v.preset.variants.findIndex(v=>v.controls.frames===33))}})}});
  assert.equal(Boolean(s.element('#generate').disabled),false);
  s.run('applyRecipe('+JSON.stringify({name:'Long',preset_id:t2v.preset.id,controls:{frames:81}})+')');
  assert.equal(Boolean(s.element('#generate').disabled),true);
});
test('saved setup overrides recompute after loading defaults',()=>{
  const s=sandbox();s.load(t2v);
  s.run('applySaved('+JSON.stringify({preset:t2v.preset.id,controls:{frames:33}})+')');
  assert.equal(Boolean(s.element('#generate').disabled),false);
});
test('invalid projected dimensions and latent batches remain blocked',()=>{
  for(const change of [{batch_size:2},{width:true},{length:null}]){
    const s=sandbox(),item=JSON.parse(JSON.stringify(t2v));
    assert.ok(item.preset.wan_decode_capacity,'Missing server projection');
    const latent=item.preset.wan_decode_capacity.latents[0];Object.assign(latent.shape,change);latent.bindings=[];
    s.load(item);assert.ok(s.run('i2vModeBlocker()'));
  }
});
test('unknown projection versions and malformed bindings show a hold instead of throwing',()=>{
  for(const mutate of [spec=>spec.version=2,spec=>spec.latents=[],spec=>spec.limits=null,spec=>spec.latents[0].bindings=[null]]){
    const s=sandbox(),item=JSON.parse(JSON.stringify(t2v));mutate(item.preset.wan_decode_capacity);
    s.load(item);assert.match(s.run('i2vModeBlocker()'),/unavailable/);assert.equal(s.element('#generate').disabled,true);
  }
});
if(failures)process.exitCode=1;
