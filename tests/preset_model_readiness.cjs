// Execute production render/handler code with inert DOM and transport boundaries.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const elements=new Map(), handlers={}, requests=[];
const element=key=>{
  if(!elements.has(key))elements.set(key,{value:'',files:[],textContent:'',innerHTML:'',className:'',disabled:false,hidden:false,classList:{toggle(){}},querySelector(){return null;},addEventListener(){}});
  return elements.get(key);
};
let inspection={requirements:[],nodes:[],graph:{}}, healthReply={online:true,schema_available:true,missing_models:{}}, libraryReply={assets:[],storage:{},inventory:[],folders:[]};
const context=vm.createContext({document:{querySelector:element,querySelectorAll:()=>[],addEventListener:(name,fn)=>handlers[name]=fn},
  URL,URLSearchParams,StudioUX:require('../app/static/studio-core.js'),Blob,location:{hash:''},setInterval(){},setTimeout(){},clearTimeout(){},console,
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

  const retained='C:\\model library\\'+('long folder\\'.repeat(32))+'.model-<img src=x onerror=bad()>&".unverified';
  const cleanup='Do not load this file. Inspect it manually; <script>bad()</script> is text.';
  const otherCleanup='Do not load this file. '+('Keep for inspection. '.repeat(20))+'<b>Manual cleanup</b> only.';
  const failure={status:'failed',message:cleanup+' Published file failed verification.'};
  const rows=[{id:'failed',name:'Failed download',download:failure},
    {id:'other',name:'Other failure',download:{status:'failed',message:'Other failure'}},
    {id:'installed',name:'Installed model',present:true,verified:true,download:{status:'installed'}},
    {id:'active',name:'Active download',download:{status:'downloading',updated_at:Date.now()/1000}},
    {id:'legacy',name:'Legacy failure',download:{status:'failed',message:'Original failure'}}]
    .map(row=>({family:'Fixture',file:row.id+'.safetensors',bytes:8,installable:true,...row}));
  const draw=async assets=>{libraryReply={...libraryReply,assets};await vm.runInContext('refreshLibrary()',context);return element('#modelCards').innerHTML;};
  const before=await draw(rows),buttons=value=>value.match(/<button data-install=[^>]+>[^<]+<\/button>/g);
  const recovered=await draw(rows.map(row=>({...row,download:{...row.download,
    unverified_path:row.id==='failed'?retained:row.id==='other'?'C:\\other.unverified':'STALE-PATH',
    cleanup:row.id==='failed'?cleanup:row.id==='other'?otherCleanup:'STALE-CLEANUP'}})));
  const cards=recovered.match(/<article class="model-card">[\s\S]*?<\/article>/g);
  const failed=cards.find(card=>card.includes('data-install="failed"'));
  assert.ok(failed.includes(retained.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')),
    'the failed card exposes the complete retained path beyond the short message budget');
  assert.ok(failed.includes('Retained unverified file'),'the path is explicitly identified for manual recovery');
  assert.ok(failed.includes('&lt;script&gt;bad()&lt;/script&gt;'),'complete cleanup text is escaped');
  assert.ok(!failed.includes('<script>')&&!failed.includes('<img'),'receipt fields cannot introduce markup');
  assert.equal(failed.split('Do not load this file.').length-1,1,'a cleanup prefix already in the bounded message is shown once');
  assert.ok(!failed.includes('C:\\other.unverified'),'another failure never owns this path');
  const other=cards.find(card=>card.includes('data-install="other"'));
  assert.ok(other.includes('C:\\other.unverified')&&!other.includes('long folder'),'each failed receipt retains its own path');
  assert.ok(other.includes(otherCleanup.replaceAll('<','&lt;').replaceAll('>','&gt;')),'cleanup is complete even beyond the message budget');
  assert.deepEqual(buttons(recovered),buttons(before),'recovery details preserve installer and active-download decisions');
  for(const id of ['installed','active']){
    const card=cards.find(value=>value.includes('data-install="'+id+'"'));
    assert.ok(!card.includes('STALE-PATH')&&!card.includes('STALE-CLEANUP')&&!card.includes('model-recovery'),
      'recovery fields are shown only on a failed receipt: '+id);
  }
  const legacy=await draw([{...rows[4],download:{status:'failed',message:'Original failure',unverified_path:{invalid:true},cleanup:['invalid']}}]);
  assert.ok(legacy.includes('Original failure')&&!legacy.includes('model-recovery'),'legacy and malformed optional fields keep the original error');
  await draw([{id:'manual',installable:false,install_note:'Pin only'},{id:'unknown'},{id:'ok',installable:true}]);
  assert.equal(count(),0,'rendering and readiness must not write');
  const disabled={disabled:true,dataset:{install:'manual'}};
  await handlers.click({target:{closest:s=>s==='[data-install]'?disabled:null}});assert.equal(count(),0,'disabled delegated controls never dispatch');
  const enabled={disabled:false,dataset:{install:'ok'}};
  await handlers.click({target:{closest:s=>s==='[data-install]'?enabled:null}});
  assert.equal(count(),1);assert.equal(requests.find(r=>r.options.method==='POST').url,'/api/models/install');
  console.log('Dependency and Models controls require explicit installer eligibility; failed recovery text is complete, escaped and receipt-owned; rendering stays read-only.');
})().catch(error=>{console.error(error);process.exitCode=1;});
