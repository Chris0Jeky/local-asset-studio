const assert = require('node:assert/strict');
const F = require('../app/static/asset-family.js');
const scope = 'a'.repeat(32), hash = 'b'.repeat(64);
const record = () => ({version:1,asset_id:'asset-1',workspace_id:scope,observation_only:true,generation_submitted:false,media_bytes_verified:false,
 recipe:{preset_id:'p',controls:{seed:1},workflow:{}},controls:{seed:'18446744073709551615',positive:'exact words'},parent_assets:['source']});
(async()=>{
 let stamp='first',applied=[],approved=true;
 const options={context:()=>({workspace:scope,stamp}), read:async()=>record(),check:async()=>({matches:true,template_sha256:hash}),
  confirm:()=>approved,apply:(...args)=>applied.push(args),random:()=>7};
 await F.createRecall(options).prepare('asset-1','words');
 assert.equal(applied[0][0].controls.seed,'18446744073709551615');
 assert.equal(applied[0][0].controls.positive,'exact words');
 assert.equal(applied[0][1].template_sha256,hash);
 assert.equal(applied[0][2],'words');
 assert.equal(F.newSeed('7',()=>7),'8');
 assert.equal(F.newSeed('18446744073709551615',()=>7),'7');
 applied=[]; approved=false;
 assert.equal(await F.createRecall(options).prepare('asset-1','new'),false);assert.equal(applied.length,0);
 approved=true;
 const stale={...options,check:async()=>{stamp='newer';return {matches:true,template_sha256:hash};}};
 await assert.rejects(F.createRecall(stale).prepare('asset-1','new'),/changed/);assert.equal(applied.length,0);
 const wrong={...options,read:async()=>({...record(),workspace_id:'f'.repeat(32)})};
 await assert.rejects(F.createRecall(wrong).prepare('asset-1','words'),/identity/);
 const bad={...options,check:async()=>({matches:false,template_sha256:hash})};
 await assert.rejects(F.createRecall(bad).prepare('asset-1','new'),/validate/);
 await assert.rejects(F.createRecall(options).prepare('asset-1','run'),/mode/);
 let release; const held=new Promise(resolve=>release=resolve);
 const controller=F.createRecall({...options,read:()=>held}); const pending=controller.prepare('asset-1','new');
 controller.cancel();release(record());await assert.rejects(pending,/changed/);assert.equal(applied.length,0);
 const malicious={version:1,asset_id:'asset-1',workspace_id:scope,nodes:[{id:'asset-1',state:'active',title:'<img onerror=x>',operation:'<script>',seed:'1',strength:null}],edges:[],gaps:[],children:null,truncated:false,children_truncated:false,children_scanned:0,observation_only:true,generation_submitted:false,media_bytes_verified:false};
 const html=F.treeMarkup(F.validate(malicious,'asset-1',scope));assert.ok(!html.includes('<img'));assert.ok(html.includes('&lt;img'));
 assert.throws(()=>F.validate({...malicious,nodes:Array(65).fill(malicious.nodes[0])},'asset-1',scope),/family/);
 console.log('asset family UI: 14 recall, stale-response, identity, seed and markup contracts passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
