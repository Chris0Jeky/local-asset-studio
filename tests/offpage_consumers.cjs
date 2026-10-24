// Consumers outside the Library keep working when their asset sits off the Library's one page (#1622): they read
// through assetRecord and resolve the ID with resolveAssetIDs before they write. The Library page here is empty.
'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8');
function world(extra={}) {
  const elements=new Map(),saved=[],resolved=new Map(),resolveCalls=[],messages=[],plain=v=>JSON.parse(JSON.stringify(v));
  const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}},showModal(){}});return elements.get(selector);};
  const context=vm.createContext({$,esc:String,document:{querySelector:$,querySelectorAll:()=>[],addEventListener(){}},CSS:{escape:String},window:{},setInterval(){},showView(){},
    assetState:{workspace_id:'1'.repeat(32),assets:[]},assetSelection:new Set(),catalog:{presets:[]},api:async()=>[],post:async()=>({}),
    assetRecord:id=>resolved.get(id)?.asset,
    resolveAssetIDs:async ids=>{resolveCalls.push(ids);for(const id of ids)resolved.set(id,{id,state:'active',asset:{id,title:'Off '+id,media_type:'image',review:'unreviewed',tags:[],metadata_revision:4}});return true;},
    refreshAssets:async()=>true,assetMessage:(m)=>messages.push(m),message:(m)=>messages.push(m),
    mutateAssets:async payload=>{for(const id of payload.ids)if(!context.assetRecord(id))throw Error('Reload the asset library before saving: its metadata revision is unavailable.');saved.push(payload);},
    ...extra});
  vm.runInContext(read('review-checks.js'),context);
  return {context,$,saved,resolveCalls,messages,resolved,plain};
}
test('Keep on a comparison candidate off the Library page resolves it before saving',async()=>{
  const w=world();vm.runInContext(read('production.js'),w.context);
  await w.context.reviewCandidateAsset('off-1','selected');
  assert.deepEqual(w.plain(w.saved),[{ids:['off-1'],action:'edit',review:'selected'}]);assert.deepEqual(w.plain(w.resolveCalls),[['off-1']]);
});
test('a quick check on a comparison candidate off the Library page resolves it before saving',async()=>{
  const w=world();vm.runInContext(read('production.js'),w.context);
  await w.context.checkCandidateAsset('off-2','style');
  assert.equal(w.saved.length,1);assert.deepEqual(w.plain(w.saved[0].ids),['off-2']);assert.match(w.saved[0].tags[0],/^check:style=/);
  assert.equal(w.context.candidateCheckAsset('off-2').id,'off-2','render-time lookups read the resolved set too');
});
test('a candidate that is truly gone still reports it and saves nothing',async()=>{
  const w=world({resolveAssetIDs:async ids=>true});vm.runInContext(read('production.js'),w.context);
  await assert.rejects(w.context.checkCandidateAsset('gone','style'),/no longer in the library/);assert.equal(w.saved.length,0);
});
test('a Recent runs output off the Library page is reviewable with K/W/X',async()=>{
  const w=world();vm.runInContext(read('output-review.js'),w.context);
  assert.equal(await w.context.window.StudioOutputReview.decide('off-3','selected'),true);
  assert.deepEqual(w.plain(w.saved),[{action:'edit',ids:['off-3'],review:'selected'}]);assert.deepEqual(w.plain(w.resolveCalls),[['off-3']]);
});
test('native export keeps resolved off-page selected assets',()=>{
  const w=world();vm.runInContext(read('production.js'),w.context);
  w.resolved.set('off-4',{id:'off-4',state:'active',asset:{id:'off-4',title:'Off picture',media_type:'image'}});w.context.assetSelection.add('off-4');
  w.$('#nativeExport').onclick();
  assert.match(w.$('#nativeAssetList').innerHTML,/Off picture/);assert.equal(vm.runInContext('nativeAssets.length',w.context),1);
});
