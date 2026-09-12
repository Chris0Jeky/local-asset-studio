'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const nodes=new Map();
function node(selector){if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',hidden:false,value:'',checked:false,classList:{toggle(){}},addEventListener(){},showModal(){this.open=true;},close(){this.open=false;}});return nodes.get(selector);}
const fixture={id:'scene-a',name:'Opening scene',revision:2,status:'saved',project:{fps:[24,1],size:[640,360],sample_rate:48000,shots:[{id:'shot-a',asset:'hero',source_in:0,frames:72,transition_frames:12}],audio:[{id:'audio-a',asset:'music',bus:'music',start_sample:0,source_sample:0,samples:96000,gain_db:-12,fade_in:4800,fade_out:4800,mute:false}],overlays:[{id:'overlay-a',asset:'title',start:4,frames:32,x:12,y:18,width:280,height:48,opacity:0.9}]},timing:{frames:72,samples:144000,shots:[{id:'shot-a',start_frame:0,end_frame:72}]},sources:[{key:'hero',asset_id:'asset-image',filename:'hero.png',kind:'image',sha256:'a'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/hero'},{key:'music',asset_id:'asset-audio',filename:'music.wav',kind:'audio',sha256:'b'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/music'},{key:'title',asset_id:'asset-title',filename:'title.png',kind:'image',sha256:'c'.repeat(64),bytes:100,url:'/api/av/scene-a/sources/title'}],history:[{revision:1,action:'create',actor:'user',at:'now',summary:'Created'},{revision:2,action:'edit',actor:'user',at:'now',summary:'Trimmed music'}],render:{id:'attempt-a',status:'completed',revision:2,preview_revision:1,stale:true,preview_url:'/api/production/scene-a/files/preview.mp4',progress:1,message:'Done',artifacts:[]},capabilities:{render_ready:true,missing_tools:[],supported:['png','mp4','wav']}};
const sandbox={document:{querySelector:node,querySelectorAll(){return[];}},fetch:async url=>({ok:true,json:async()=>url==='/api/av'?{projects:[{id:'scene-a',name:'Opening scene',revision:2,status:'saved',render_stale:true}],capabilities:fixture.capabilities}:fixture}),location:{search:'',assign(){}},URLSearchParams,URL,CSS:{escape:value=>value},setInterval(){return 1;},clearInterval(){},console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/av.js'),'utf8'),sandbox);
setImmediate(()=>{
  const html=node('#avContent').innerHTML;
  assert.match(html,/Source offset/);assert.match(html,/Dissolve/);assert.match(html,/Static overlays/);
  assert.match(html,/Preview from revision 1/);assert.match(html,/older than this scene/);
  assert.match(html,/Render scene/);vm.runInContext("avDocument.render.status='running';renderDocument()",sandbox);assert.match(node('#avContent').innerHTML,/Cancel this render/);
  assert.match(html,/Restore as new revision/);assert.doesNotMatch(html,/base64/i);
  console.log('Scene editor frontend renders timing, stale preview, source provenance and explicit render controls.');
});
