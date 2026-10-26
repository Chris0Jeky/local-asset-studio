// #1211: the real dialog and comparison handlers preserve owner intent while checks are edited or observed.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup}=require('./asset_detail_contracts.cjs');
const source=name=>fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8');
function dialog(){
  const s=setup({autoOpen:false});s.run(source('review-checks.js'));
  s.run("catalog={presets:[]};assetState.assets[0].media_type='image';assetState.assets[0].tags=['check:style=yes','hero'];openAsset('a')");
  return s;
}
function comparison(){
  const s=setup({autoOpen:false});s.run(source('review-checks.js'));
  s.run("catalog={presets:[{id:'hero',review_set:'character'}]};observeAssetWorkspaceIdentity()");s.run(source('production.js'));
  const plan={id:'c'.repeat(32),name:'Saved answers',kind:'comparison',axis:'seed',values:[1],budget:{reserved:1,allowance:1},created_at:1790000000,
    stages:[{label:'A',job:{id:'job-off',preset_id:'hero',status:'completed',outputs:[{asset_id:'off',media_type:'image'}]}}],state:{status:'awaiting_review',message:'Finished'}};
  s.run(`productionPlans=${JSON.stringify([plan])};productionId=${JSON.stringify(plan.id)};renderProduction()`);
  const button={dataset:{candidateCheckLoad:'off'},textContent:'Load saved checks',disabled:false};
  const load=()=>s.el('#productionDetail').onclick({target:{closest:selector=>selector==='[data-candidate-check-load]'?button:null}});
  const observed={...JSON.parse(s.run('JSON.stringify(assetState.assets[0])')),id:'off',media_type:'image',preset_id:'hero',tags:['check:face=yes'],metadata_revision:4};
  const answer=(index=0,item={id:'off',state:'active',asset:observed})=>s.writes[index].resolve({workspace_id:'1'.repeat(32),items:[item]});
  return {...s,load,answer,button};
}
let count=0;
async function test(name,fn){await fn();count++;console.log('PASS',name);}
(async()=>{
  await test('Dialog quick-check and reason chip repaint keeps the same focused control',()=>{
    for(const [attribute,name,box,action] of [['reviewCheck','style','#assetReviewChecks',"toggleAssetReviewCheck('style')"],['reviewReason','hands','#assetReviewReasons',"toggleAssetReason('hands')"]]){
      const s=dialog(),document=s.run('document');document.body={};
      const original={dataset:{[attribute]:name},closest:()=>original},replacement={dataset:{[attribute]:name},focus(){document.activeElement=this;}};
      document.activeElement=original;
      s.el(box).querySelectorAll=()=>[replacement];document.querySelectorAll=()=>[replacement];
      Object.defineProperty(s.el(box),'innerHTML',{get(){return this.html||'';},set(value){this.html=value;if(document.activeElement===original)document.activeElement=document.body;}});
      s.run(action);assert.equal(document.activeElement,replacement,attribute+' focus survives its replaced button');
      const field={id:'assetTags'};document.activeElement=field;s.run('renderAssetReasons()');
      assert.equal(document.activeElement,field,'typing in tags never transfers focus to a chip');assert.equal(s.writes.length,0);
    }
  });
  await test('Cycling back to the saved tag set clears dirty state, recovery, handoff holds and no-op saves',async()=>{
    const s=dialog(),workbench=source('studio-workbench.js');s.run('q=$;');
    s.run(workbench.slice(workbench.indexOf('  function assetDetailsDirty(){'),workbench.indexOf('  function warnUnsavedAsset(){')));
    for(let i=0;i<3;i++)s.run("toggleAssetReviewCheck('style')");
    assert.equal(s.el('#assetTags').value,'hero, check:style=yes','the same answers can have a different draft order');
    assert.equal(s.run('assetDetailDirty()'),false);assert.equal(s.run('assetDetailsDirty()'),false);
    assert.equal(s.run('assetRetainedDetail'),null);assert.match(s.el('#assetDetailStatus').textContent,/No unsaved changes/);
    assert.equal(await s.el('#saveAssetDetails').onclick(),true);assert.equal(s.writes.length,0,'a restored answer set never creates a metadata command');
    s.el('#closeAssetDialog').onclick();assert.equal(s.confirmations(),0);
  });
  await test('Tag equality preserves real text edits and refuses changed invalid answers',async()=>{
    const s=dialog();s.el('#assetTags').value=' hero , check:style=yes, hero ';
    assert.equal(s.run('assetDetailDirty()'),false,'normalization and duplicate removal match the saved tag set');
    s.el('#assetNotes').value='new note';assert.equal(s.run('assetDetailDirty()'),true);
    const save=s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['a'],action:'edit',notes:'new note'});
    s.accept(0);assert.equal(await save,true);assert.equal(s.run('assetDetailDirty()'),false);
    s.el('#assetTags').value='hero, Check:style=yes';assert.equal(s.run('assetDetailDirty()'),true);
    assert.equal(await s.el('#saveAssetDetails').onclick(),false);assert.equal(s.writes.length,1);assert.equal(s.run('assetDetailPending'),null);
  });
  await test('An unloaded comparison candidate observes saved answers explicitly without changing them',async()=>{
    const s=comparison(),initial=s.el('#productionDetail').innerHTML;
    assert.match(initial,/Saved checks not loaded/);assert.match(initial,/data-candidate-check-load="off"/);
    assert.doesNotMatch(initial,/data-candidate-check="\w+" data-asset="off"/,'unknown saved answers are never presented as not checked');
    assert.equal(s.writes.length,0,'rendering does not issue an observation or a save');
    const first=s.load(),second=s.load();assert.equal(s.writes.length,1,'a repeated load press shares one in-flight read');
    assert.equal(s.writes[0].url,'/api/assets/selection');assert.deepEqual(s.payload(0),{workspace_id:'1'.repeat(32),ids:['off'],details:true});
    s.answer();await first;await second;
    assert.match(s.el('#productionDetail').innerHTML,/data-candidate-check="face" data-asset="off" aria-label="face: yes/);
    assert.match(s.el('#productionDetail').innerHTML,/face 1\/1/);assert.equal(s.writes.length,1);assert.equal(s.run('assetLibraryPending'),null);
    assert.equal(s.run('productionPlans[0].state.status'),'awaiting_review');
  });
  await test('Comparison answer observations cannot repaint a different plan or Workspace',async()=>{
    for(const change of ["productionId='other'","assetState.workspace_id='2'.repeat(32);observeAssetWorkspaceIdentity()","assetState.workspace_id='2'.repeat(32);observeAssetWorkspaceIdentity();assetState.workspace_id='1'.repeat(32);observeAssetWorkspaceIdentity()"]){
      const s=comparison(),reading=s.load();assert.equal(s.writes.length,1);s.run(change);
      s.el('#productionDetail').innerHTML='replacement detail';s.el('#productionMessage').textContent='replacement message';
      s.answer();await reading;
      assert.equal(s.el('#productionDetail').innerHTML,'replacement detail');assert.equal(s.el('#productionMessage').textContent,'replacement message');
      assert.equal(s.writes.length,1);
      if(change.includes('workspace_id'))assert.equal(s.run("assetResolved.has('off')"),false,'a stale Workspace observation never enters the cache');
    }
  });
  await test('A failed or receipt-stale comparison observation permits a fresh explicit read',async()=>{
    for(const fail of ['network','receipt']){
      const s=comparison(),reading=s.load();
      if(fail==='network')s.writes[0].reject(Error('injected read failure'));else{s.run('assetReceiptEpoch++');s.answer();}
      await reading;assert.equal(s.writes.length,1);assert.doesNotMatch(s.el('#productionDetail').innerHTML,/data-candidate-check="face" data-asset="off"/);
      assert.match(s.el('#productionMessage').textContent,/read failure|changed while loading/);
      const retry=s.load();assert.equal(s.writes.length,2);s.answer(1);await retry;
      assert.match(s.el('#productionDetail').innerHTML,/data-candidate-check="face" data-asset="off" aria-label="face: yes/);
      assert.ok(s.writes.every(request=>request.url==='/api/assets/selection'));
    }
  });
  await test('A missing comparison candidate has an unavailable state and never fabricated unchecked answers',async()=>{
    const s=comparison(),reading=s.load();s.answer(0,{id:'off',state:'missing',asset:null});await reading;
    assert.match(s.el('#productionDetail').innerHTML,/Saved checks unavailable/);
    assert.doesNotMatch(s.el('#productionDetail').innerHTML,/data-candidate-check="\w+" data-asset="off"/);assert.equal(s.writes.length,1);
    await s.run("loadCandidateChecks('not-in-this-plan')");assert.equal(s.writes.length,1,'a stale control outside the current comparison cannot read an unrelated ID');
  });
  console.log('Review check interaction contracts passed:',count);
})().catch(error=>{console.error(error);process.exitCode=1;});
