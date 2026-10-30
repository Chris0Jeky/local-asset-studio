'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
function page(){
  const nodes=new Map(),writes=[],listeners={},state={scope:'private',privacy:'private',revision:1};let respond;
  const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',innerHTML:'',textContent:'',disabled:false});return nodes.get(id);};
  const context=vm.createContext({console,document:{querySelector:node,addEventListener:(event,fn)=>(listeners[event]||=[]).push(fn)},
    StudioPrivacy:{capture:()=>({...state})},
    fetch:(url,options)=>{writes.push({url,options});return new Promise(resolve=>{respond=data=>resolve({ok:true,json:async()=>data});});},
    continuationPayload:()=>({}),tilePayload:()=>({}),parallaxPayload:()=>({}),attachedReferencePayload:()=>[],
    values:()=>({positive:node('#positive').value,negative:node('#negative').value,seed:'42'})});
  vm.runInContext(source.slice(0,source.indexOf('function i2vModeBlocker()')),context);
  vm.runInContext(source.slice(source.indexOf('function renderWildcardChips()'),source.indexOf('function renderNsfwIntel(')),context);
  const start=source.indexOf("$('#wildcardChips')?.addEventListener");
  // Only the document notifications; click insertion belongs to the existing chip handler.
  vm.runInContext(source.slice(source.indexOf('for (const event',start),source.indexOf("$('#variants').onclick",start)),context);
  vm.runInContext("selected={id:'demo',positive:['1','text'],negative:['2','text']};catalog={wildcards:[]}",context);
  node('#batch').value='2';
  return {context,node,writes,state,listeners,reply:data=>respond(data),run:js=>vm.runInContext(js,context)};
}
test('plain prompts disable wording preview with a visible accessible reason and send nothing',async()=>{
  const h=page();h.node('#positive').value='plain';h.run('renderWildcardChips()');
  const html=h.node('#wildcardChips').innerHTML;
  assert.match(html,/data-wildcard-preview[^>]*disabled/);assert.match(html,/aria-describedby="wildcardPreviewReason"/);
  assert.match(html,/No wildcards in this prompt\./);assert.equal(h.node('#wildcardChips').hidden,false);
  await h.run('previewWildcardWording()');assert.equal(h.writes.length,0);
});
test('either prompt enables preview even with no named wildcard lists',()=>{
  for(const [key,text] of [['positive','{red|blue}'],['negative','__lighting__']]){
    const h=page();h.node('#'+key).value=text;h.run('renderWildcardChips()');
    assert.equal(h.run('wildcardPreviewReason()'),'');assert.doesNotMatch(h.node('#wildcardChips').innerHTML,/ disabled/);
    assert.equal(h.writes.length,0);
  }
});
test('explicit preview uses creation payload and privacy headers, escapes both prompts and never submits',async()=>{
  const h=page();h.node('#positive').value='__lighting__';
  const pending=h.run('previewWildcardWording()');assert.equal(h.writes.length,1);assert.equal(h.writes[0].url,'/api/wildcards/preview');
  assert.equal(h.writes[0].options.headers['X-Studio-Creation-Privacy'],'private');assert.equal(h.writes[0].options.headers['X-Studio-Privacy'],'private');
  const payload=JSON.parse(h.writes[0].options.body);assert.equal(payload.preset_id,'demo');assert.equal(payload.batch_count,'2');assert.equal(payload.controls.seed,'42');
  h.reply({members:[{index:0,seed:9007199254740992,seed_text:'9007199254740993',positive:'<img onerror="bad">',negative:'<script>bad</script>'},{index:1,seed:null,seed_unknown:true,positive:'unknown & safe',negative:''}]});await pending;
  const html=h.node('#wildcardPreview').innerHTML;assert.doesNotMatch(html,/<img|<script/);assert.match(html,/&lt;img/);assert.match(html,/&lt;script/);assert.match(html,/Seed 9007199254740993/);assert.match(html,/Seed unknown/);assert.match(html,/unknown &amp; safe/);
  assert.equal(h.writes.length,1);assert.equal(h.node('[data-wildcard-preview]').disabled,false);
});
test('late private results cannot enter a changed privacy view',async()=>{
  const h=page();h.node('#positive').value='__lighting__';const pending=h.run('previewWildcardWording()');h.state.revision++;
  h.reply({members:[{index:0,seed:42,positive:'PRIVATE-CANARY',negative:''}]});await pending;
  assert.doesNotMatch(h.node('#wildcardPreview').innerHTML,/PRIVATE-CANARY/);
});
test('prompt edits and privacy changes clear displayed previews without requesting another',()=>{
  const h=page();h.node('#positive').value='__lighting__';h.run('renderWildcardChips()');
  assert.doesNotMatch(h.node('#wildcardChips').innerHTML,/ disabled/);
  h.node('#positive').value='plain';h.listeners.input[0]({target:h.node('#positive')});
  assert.match(h.node('#wildcardChips').innerHTML,/ disabled/);
  h.node('#wildcardChips').innerHTML='PRIVATE-CANARY';h.listeners['studio:privacy-change'][0]();
  assert.doesNotMatch(h.node('#wildcardChips').innerHTML,/PRIVATE-CANARY/);assert.equal(h.writes.length,0);
});
