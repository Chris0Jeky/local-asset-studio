// Execute production render/handler code with inert DOM and transport boundaries.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const elements=new Map(), handlers={}, requests=[];
const element=key=>{
  if(!elements.has(key))elements.set(key,{value:'',files:[],textContent:'',innerHTML:'',className:'',disabled:false,hidden:false,classList:{toggle(){}},addEventListener(){}});
  return elements.get(key);
};
let inspection={requirements:[],nodes:[],graph:{}}, healthReply={online:true,schema_available:true,missing_models:{}}, libraryReply={assets:[],storage:{},inventory:[],folders:[]};
const context=vm.createContext({document:{querySelector:element,querySelectorAll:()=>[],addEventListener:(name,fn)=>handlers[name]=fn},
  URL,Blob,location:{hash:''},setInterval(){},setTimeout(){},clearTimeout(){},console,
  fetch:(url,options={})=>{
    requests.push({url,options});
    if(url==='/api/catalog')return new Promise(()=>{});
    return Promise.resolve({ok:true,json:async()=>url.startsWith('/api/inspect/')?inspection:url==='/api/health'?healthReply:url==='/api/library'?libraryReply:{}});
  }});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8'),context);
const markup=row=>{context.row=row;return vm.runInContext('dependencyMarkup(row)',context);};
const count=()=>requests.filter(r=>r.options.method==='POST').length;
(async()=>{
  const pin={file:'loras/a.safetensors',path:'C:/models/loras/a.safetensors',present:false,asset_id:'a'};
  for(const flag of [false,undefined,null,'true',1]){
    const html=markup({...pin,installable:flag,install_note:'Copy the reviewed file manually.'});
    assert.ok(!html.includes('data-install='));assert.ok(html.includes('Copy the reviewed file manually.'));
  }
  assert.ok(markup({...pin,installable:true}).includes('data-install="a"'));
  assert.ok(!markup({...pin,present:true,installable:true}).includes('data-install='));
  assert.ok(!markup({...pin,present:null,installable:true}).includes('data-install='));
  assert.ok(!markup({...pin,asset_id:null,installable:true}).includes('data-install='));
  const unknown=markup({...pin,path:null,present:null,installable:false,note:'Model folder unknown; declare model_files.'});
  assert.ok(!unknown.includes('data-copy='));assert.ok(unknown.includes('Model folder unknown'));
  const injected=markup({...pin,file:'<img src=x onerror=alert(1)>',installable:false,install_note:'<script>bad</script>',path:'" onclick="bad'});
  assert.ok(!injected.includes('<script>'));assert.ok(!injected.includes('<img'));assert.ok(injected.includes('&lt;script&gt;'));

  vm.runInContext("selected={id:'fixture'}",context);
  inspection={requirements:[{...pin,installable:false,install_note:'Pin-only GGUF: copy by hand.'},{...pin,file:'loras/b.safetensors',asset_id:'b',installable:true}],nodes:[],graph:{}};
  await vm.runInContext('inspectSelected()',context);
  assert.ok(element('#dependencies').innerHTML.includes('Pin-only GGUF'));
  assert.ok(element('#dependencies').innerHTML.includes('data-install="b"'));
  assert.ok(!element('#dependencies').innerHTML.includes('data-install="a"'));
  assert.equal(element('#dependencyCount').textContent,'0 / 2 present');

  healthReply={online:true,schema_available:true,missing_models:{fixture:['inpaint/fix.patch']}};
  await vm.runInContext('health()',context);
  assert.equal(element('#health').textContent,'Recipe needs models');assert.equal(element('#generate').disabled,true);
  healthReply={online:true,schema_available:true,missing_models:{}};
  await vm.runInContext('health()',context);assert.equal(element('#generate').disabled,false);

  libraryReply={...libraryReply,assets:[{id:'manual',installable:false,install_note:'Pin only'},{id:'unknown'},{id:'ok',installable:true}]};
  await vm.runInContext('refreshLibrary()',context);
  const html=element('#modelCards').innerHTML;
  assert.match(html,/data-install="manual" disabled/);assert.match(html,/data-install="unknown" disabled/);
  assert.ok(!/data-install="ok" disabled/.test(html));
  assert.equal(count(),0,'rendering and readiness must not write');
  const disabled={disabled:true,dataset:{install:'manual'}};
  await handlers.click({target:{closest:s=>s==='[data-install]'?disabled:null}});assert.equal(count(),0,'disabled delegated controls never dispatch');
  const enabled={disabled:false,dataset:{install:'ok'}};
  await handlers.click({target:{closest:s=>s==='[data-install]'?enabled:null}});
  assert.equal(count(),1);assert.equal(requests.find(r=>r.options.method==='POST').url,'/api/models/install');
  console.log('Dependency and Models controls require explicit installer eligibility; readiness and rendering stay read-only.');
})().catch(error=>{console.error(error);process.exitCode=1;});
