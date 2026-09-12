'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const nodes=new Map();
function node(selector){if(!nodes.has(selector)){const classes=new Set();nodes.set(selector,{innerHTML:'',textContent:'',hidden:false,value:'',checked:false,disabled:false,dataset:{},handlers:{},classList:{toggle(name,on){on?classes.add(name):classes.delete(name);},contains(name){return classes.has(name);}},addEventListener(name,handler){this.handlers[name]=handler;},querySelector(){return null;},getAttribute(){return null;},replaceWith(){},showModal(){this.open=true;},close(){this.open=false;}});}return nodes.get(selector);}
const controls=[['render',{renderAction:'render'}],['export',{renderAction:'export'}],['save',{save:'shots:shot-a'}],['discard',{discardDrafts:''}],['reload',{}]].map(([name,dataset])=>Object.assign(node(name),{dataset}));
const liveInput=Object.assign(node('live-input'),{dataset:{field:'frames',section:'shots',clip:'shot-a'},type:'number',value:'72'});
const fixture={id:'scene-a',name:'Opening scene',revision:2,status:'saved',project:{fps:[24,1],size:[640,360],sample_rate:48000,shots:[{id:'shot-a',asset:'hero',source_in:0,frames:72,transition_frames:12}],audio:[{id:'audio-a',asset:'music',bus:'music',start_sample:0,source_sample:0,samples:96000,gain_db:-12,fade_in:4800,fade_out:4800,mute:false}],overlays:[{id:'overlay-a',asset:'title',start:4,frames:32,x:12,y:18,width:280,height:48,opacity:0.9}]},timing:{frames:72,samples:144000,shots:[{id:'shot-a',start_frame:0,end_frame:72}]},sources:[{key:'hero',asset_id:'asset-image',filename:'hero.png',kind:'image',sha256:'a'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/hero'},{key:'music',asset_id:'asset-audio',filename:'music.wav',kind:'audio',sha256:'b'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/music'},{key:'title',asset_id:'asset-title',filename:'title.png',kind:'image',sha256:'c'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/title'}],history:[{revision:1,action:'create',actor:'user',at:'now',summary:'Created'},{revision:2,action:'edit',actor:'user',at:'now',summary:'Trimmed music'}],render:{id:'attempt-a',status:'completed',revision:2,preview_revision:1,stale:true,preview_url:'/api/production/scene-a/files/preview.mp4',progress:1,message:'Done',artifacts:[]},capabilities:{render_ready:true,missing_tools:[],supported:['png','mp4','wav']}};
let revision=2,conflictNextEdit=false,polled=false,holdNextRead=false,holdNextPost=false,releaseRead,releasePost;const posts=[],calls=[];
function scene(){const copy=JSON.parse(JSON.stringify(fixture));copy.revision=revision;if(polled){copy.status='completed';copy.render.status='completed';copy.render.stale=false;}return copy;}
const sandbox={document:{querySelector:node,querySelectorAll(selector){return selector==='#avContent button'?controls:selector==='[data-field]'?[liveInput]:[];}},fetch:async(url,options={})=>{calls.push({url,method:options.method||'GET'});if(options.method==='POST'){const body=JSON.parse(options.body);posts.push(body);if(holdNextPost){holdNextPost=false;await new Promise(resolve=>{releasePost=resolve;});}if(body.action==='edit'&&conflictNextEdit){conflictNextEdit=false;return {ok:false,json:async()=>({error:'Scene conflict: another editor saved this scene.'})};}if(!['cancel','export'].includes(body.action))revision++;return {ok:true,json:async()=>scene()};}const data=url==='/api/av'?{projects:[{id:'scene-a',name:'Opening scene',revision,status:polled?'completed':'saved',render_stale:!polled}],capabilities:fixture.capabilities}:scene();if(holdNextRead){holdNextRead=false;await new Promise(resolve=>{releaseRead=resolve;});}return {ok:true,json:async()=>data};},location:{search:'',assign(){}},URLSearchParams,URL,CSS:{escape:value=>value},setInterval(){return 1;},clearInterval(){},console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/av.js'),'utf8'),sandbox);
function target(matches){return {closest(selector){return matches[selector]||null;}};}
async function click(matches){await node('#avContent').onclick({target:target(matches)});}
setImmediate(()=>{(async()=>{
  let html=node('#avContent').innerHTML;
  assert.match(html,/Source offset/);assert.match(html,/Dissolve/);assert.match(html,/Static overlays/);
  assert.match(html,/Preview from saved revision 1/);assert.match(html,/older than saved scene/);
  assert.match(html,/Render scene/);vm.runInContext("avDocument.render.status='running';renderDocument()",sandbox);assert.match(node('#avContent').innerHTML,/Cancel this render/);
  assert.match(html,/Restore as new revision/);assert.doesNotMatch(html,/base64/i);

  vm.runInContext("avDocument.render.status='completed';renderDocument()",sandbox);const beforeInputHtml=node('#avContent').innerHTML;liveInput.value='60';node('#avContent').handlers.input({target:liveInput});
  assert.equal(node('#avContent').innerHTML,beforeInputHtml,'typing must not replace the input or video DOM');assert.match(node('#avDraftNotice').innerHTML,/1 clip change is unsaved/);assert.equal(node('render').disabled,true);assert.equal(node('export').disabled,true);assert.equal(node('save').disabled,false);assert.equal(liveInput.disabled,false);
  vm.runInContext('renderDocument()',sandbox);html=node('#avContent').innerHTML;
  assert.match(html,/1 clip change is unsaved/);assert.match(html,/before using document actions/);assert.match(html,/Discard unsaved changes/);
  assert.match(html,/data-render-action="render" disabled/);assert.match(html,/data-render-action="export" disabled/);assert.match(html,/data-remove="shots:shot-a" disabled/);assert.match(html,/data-restore="1" disabled/);assert.match(html,/data-split disabled/);
  const beforeBlocked=posts.length;
  const beforeTransitions=calls.length;await node('#newScene').onclick();node('#avProjectList').onclick({target:target({'[data-project]':{dataset:{project:'scene-a'}}})});await vm.runInContext("createScene({preventDefault(){}})",sandbox);assert.equal(calls.length,beforeTransitions,'dirty scene transitions must not fetch');assert.equal(posts.length,beforeBlocked,'dirty scene creation must not post');assert.equal(vm.runInContext('avDrafts.size',sandbox),1);
  await click({'[data-render-action]':{dataset:{renderAction:'render'}}});await click({'[data-render-action]':{dataset:{renderAction:'export'}}});await click({'[data-remove]':{dataset:{remove:'shots:shot-a'}}});await click({'[data-add]':{dataset:{add:'shots'}}});await click({'[data-move]':{dataset:{move:'1'}}});await click({'[data-split]':{dataset:{}}});await click({'[data-restore]':{dataset:{restore:'1'}}});
  assert.equal(posts.length,beforeBlocked,'dirty document actions must not post');assert.match(node('#avStatus').textContent,/Save or discard unsaved clip changes/);
  await click({'[data-discard-drafts]':{dataset:{}}});assert.equal(vm.runInContext('avDrafts.size',sandbox),0);assert.match(node('#avStatus').textContent,/Discarded unsaved clip changes/);assert.doesNotMatch(node('#avContent').innerHTML,/clip change is unsaved/);const beforeOpen=calls.length;await node('#newScene').onclick();assert.equal(calls.length,beforeOpen+1);assert.equal(calls.at(-1).url,'/api/workspace');

  vm.runInContext("setDraft('shots','shot-a','frames','61');avSelection={section:'shots',id:'shot-a'}",sandbox);conflictNextEdit=true;await vm.runInContext("mutate({action:'edit',section:'shots',clip_id:'shot-a',changes:{frames:61}},()=>clearDraft('shots','shot-a'))",sandbox);
  assert.equal(vm.runInContext("avDrafts.get('shots:shot-a').conflict",sandbox),true);assert.match(node('#avContent').innerHTML,/server changed this scene/i);
  await click({'[data-discard-drafts]':{dataset:{}}});

  vm.runInContext("setDraft('shots','shot-a','frames','62');setDraft('audio','audio-a','gain_db','-9');avSelection={section:'shots',id:'shot-a'}",sandbox);await vm.runInContext("mutate({action:'edit',section:'shots',clip_id:'shot-a',changes:{frames:62}},()=>clearDraft('shots','shot-a'))",sandbox);
  assert.equal(vm.runInContext('avDrafts.size',sandbox),1);assert.equal(vm.runInContext('avDraftRevision',sandbox),3);assert.equal(posts.at(-1).expected_revision,2);
  vm.runInContext("avSelection={section:'audio',id:'audio-a'}",sandbox);await vm.runInContext("mutate({action:'edit',section:'audio',clip_id:'audio-a',changes:{gain_db:-9}},()=>clearDraft('audio','audio-a'))",sandbox);assert.equal(posts.at(-1).expected_revision,3);assert.equal(vm.runInContext('avDrafts.size',sandbox),0);

  vm.runInContext("setDraft('shots','shot-a','frames','63')",sandbox);polled=true;await vm.runInContext("loadScene('scene-a',true)",sandbox);assert.equal(vm.runInContext("draftValue('shots',clipBy('shots','shot-a'),'frames')",sandbox),'63');assert.equal(vm.runInContext('avDrafts.size',sandbox),1);assert.match(node('#avDocumentStatus').textContent,/Revision 4 · completed/);assert.match(node('#avProjectList').innerHTML,/completed/);
  await click({'[data-discard-drafts]':{dataset:{}}});
  // A poll captured before an edit cannot roll the document/render back afterwards.
  holdNextRead=true;const oldPoll=vm.runInContext("loadScene('scene-a',true)",sandbox);assert.equal(typeof releaseRead,'function');
  await vm.runInContext("mutate({action:'edit',section:'shots',clip_id:'shot-a',changes:{frames:64}})",sandbox);assert.equal(vm.runInContext('avDocument.revision',sandbox),5);releaseRead();await oldPoll;assert.equal(vm.runInContext('avDocument.revision',sandbox),5);
  // Export/cancel/reload share the edit guard; none can overlap and apply a late response.
  for(const action of ['export','cancel']){
    holdNextPost=true;const ongoing=click({'[data-render-action]':{dataset:{renderAction:action}}});const postCount=posts.length,callCount=calls.length;
    assert.equal(vm.runInContext('avMutationBusy',sandbox),true);assert.equal(liveInput.disabled,true);
    await click({'[data-render-action]':{dataset:{renderAction:action==='export'?'cancel':'export'}}});await click({'#documentReload':{}});await node('#reloadScene').onclick();await node('#newScene').onclick();await node('#avProjectList').onclick({target:target({'[data-project]':{dataset:{project:'other-scene'}}})});
    assert.equal(posts.length,postCount);assert.equal(calls.length,callCount);assert.equal(vm.runInContext('avId',sandbox),'scene-a');
    releasePost();await ongoing;assert.equal(vm.runInContext('avMutationBusy',sandbox),false);assert.equal(liveInput.disabled,false);
  }
  assert.equal(posts.at(-1).action,'cancel');assert.equal(Object.hasOwn(posts.at(-1),'expected_revision'),false,'cancel must retain its attempt-scoped request contract');
  holdNextRead=true;const reload=node('#reloadScene').onclick();const beforeReloadPosts=posts.length;await click({'[data-render-action]':{dataset:{renderAction:'render'}}});assert.equal(posts.length,beforeReloadPosts);releaseRead();await reload;
  vm.runInContext("avMessage('Render queued for revision 5.');avDocument.render.status='running'",sandbox);await vm.runInContext("loadScene('scene-a',true)",sandbox);assert.equal(node('#avStatus').textContent,'Done');
  console.log('Scene editor updates drafts without replacing fields and serializes commands against stale reads.');
})().catch(error=>{console.error(error);process.exitCode=1;});});
