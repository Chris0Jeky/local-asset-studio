// #1725: an opened Library picture carries its own verdict row (Keep K, Needs work W, Not this X) without a review queue.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
// The listener starts the save and does not return it, so settle lets the receipt and repaint finish.
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const key=async(s,k,event={})=>{await s.dispatch('keydown',{key:k,target:{tagName:'BUTTON'},preventDefault(){},...event});await settle();};
const open=(review='unreviewed')=>{const s=setup({autoOpen:false});s.run(`Object.assign(assetState.assets[0],{media_type:'image',review:${JSON.stringify(review)}});openAsset('a')`);return s;};
const pressed=s=>[...s.el('#assetQueue').innerHTML.matchAll(/data-queue-review="(\w+)" aria-pressed="(\w+)"/g)].filter(m=>m[2]==='true').map(m=>m[1]);
const shape=s=>{const {request_id,...rest}=s.payload(0);return rest;};
let count=0;
async function test(name,fn){await fn();count++;console.log('PASS',name);}
(async()=>{
  await test('Without a queue the open picture shows the verdict row once, with its saved mark pressed',()=>{
    const s=open(),html=s.el('#assetQueue').innerHTML;
    assert.equal(s.el('#assetQueue').hidden,false);assert.equal(s.run('assetQueue'),null);
    assert.deepEqual([...html.matchAll(/data-queue-review="(\w+)"/g)].map(m=>m[1]),['selected','needs_work','rejected']);
    assert.match(html,/Keep <kbd>K<\/kbd>.*Needs work <kbd>W<\/kbd>.*Not this <kbd>X<\/kbd>/);
    assert.doesNotMatch(html,/data-queue-(skip|step|exit)|Review queue| of \d/,'no queue-only controls');
    assert.deepEqual(pressed(s),[]);assert.match(html,/role="status" aria-live="polite">Not reviewed yet/);
    for(const [review,label] of [['selected','Kept'],['needs_work','Needs work'],['rejected','Not this']]){
      const t=open(review);assert.deepEqual(pressed(t),[review]);assert.match(t.el('#assetQueue').innerHTML,new RegExp('Marked '+label));
    }
    s.el('#assetDialog').close();assert.equal(s.el('#assetQueue').hidden,true,'a closed dialog shows no verdict row');
  });
  await test('With a queue active the panel is the queue row alone: no second verdict row, no pressed state',()=>{
    const s=open();s.run("assetQueue={ids:['a','b'],index:0,transition:{}};renderAssetQueue()");
    const html=s.el('#assetQueue').innerHTML;
    assert.equal((html.match(/data-queue-review="selected"/g)||[]).length,1);assert.equal((html.match(/data-queue-review=/g)||[]).length,3);
    assert.match(html,/Review queue<\/b><span role="status" aria-live="polite">1 of 2/);assert.match(html,/data-queue-skip/);assert.doesNotMatch(html,/aria-pressed/);
    s.run('assetQueue=null;renderAssetQueue()');assert.match(s.el('#assetQueue').innerHTML,/aria-pressed/,'leaving the queue hands the panel back to the verdict row');
  });
  await test('K, W and X save the mark with the queue request shape and stay on the picture',async()=>{
    for(const [k,review] of [['k','selected'],['w','needs_work'],['x','rejected']]){
      const s=open(),event={prevented:false,preventDefault(){event.prevented=true;}};
      const pending=key(s,k,event);assert.equal(event.prevented,true);assert.equal(s.writes.length,1);
      assert.equal(s.writes[0].url,'/api/assets/update');assert.deepEqual(s.metadata(0),{ids:['a'],action:'edit',review});assert.deepEqual(s.payload(0).expected_revisions,{a:0});
      const queue=setup({autoOpen:false});queue.run("Object.assign(assetState.assets[0],{media_type:'image'});assetQueue={ids:['a','b'],index:0,transition:{}};openAsset('a')");
      const decided=queue.run(`assetQueueDecide(${JSON.stringify(review)})`);assert.deepEqual(shape(queue),shape(s),'the same request as a queue decision');assert.equal(queue.writes[0].options.headers['X-Studio-Privacy'],s.writes[0].options.headers['X-Studio-Privacy']);
      queue.accept(0);await decided;
      s.accept(0);await pending;
      assert.equal(s.run('activeAsset.id'),'a','a verdict outside the queue never advances');assert.equal(s.run('assetQueue'),null);assert.equal(s.el('#assetDialog').open,true);
      assert.equal(s.run('activeAsset.review'),review);assert.deepEqual(pressed(s),[review]);assert.equal(s.el('#assetReview').value,review);
      assert.match(s.el('#assetQueue').innerHTML,/Marked /);assert.match(s.el('#assetDetailStatus').textContent,/^Marked .*Saved for this picture/);assert.equal(s.run('assetDetailDirty()'),false);
    }
    const s=open('selected');await key(s,'k');assert.equal(s.writes.length,0,'re-marking the saved mark sends nothing');
    const change=key(s,'w');s.accept(0);await change;const back=key(s,'k');assert.equal(s.payload(1).expected_revisions.a,1,'the second mark carries the confirmed revision');s.accept(1);await back;assert.deepEqual(pressed(s),['selected']);
  });
  await test('A verdict outside the queue names the other edits it saved with the mark',async()=>{
    const s=open();s.el('#assetTitle').value='Half-typed title';const pending=key(s,'k');
    assert.equal(s.metadata(0).title,'Half-typed title','the same bundled save as the queue');s.accept(0);await pending;
    assert.match(s.el('#assetDetailStatus').textContent,/^Marked .*Saved for this picture, with your edits to title\.$/);
  });
  await test('A verdict button press saves the same way and keeps its focus after repainting',async()=>{
    const s=open(),document=s.run('document');
    const button={dataset:{queueReview:'needs_work'}};
    const pending=s.clickClosest('[data-queue-review]',button.dataset);assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['a'],action:'edit',review:'needs_work'});
    let focused=null;document.activeElement={closest:selector=>selector==='#assetQueue [data-queue-review]'?button:null};
    s.el('#assetQueue').querySelector=selector=>({focus(){focused=selector;}});
    s.accept(0);await pending;assert.equal(focused,'[data-queue-review="needs_work"]');
  });
  await test('The shortcuts are ignored while typing, with modifiers, with the dialog closed or mid-save',async()=>{
    const s=open();
    for(const target of [{tagName:'INPUT'},{tagName:'TEXTAREA'},{tagName:'SELECT'},{tagName:'DIV',isContentEditable:true}])await key(s,'k',{target});
    for(const modifier of ['ctrlKey','metaKey','altKey','shiftKey'])await key(s,'x',{[modifier]:true});
    await key(s,'w',{defaultPrevented:true});await key(s,'s');await key(s,'ArrowRight');
    assert.equal(s.writes.length,0,'nothing was sent');
    const first=key(s,'k');assert.equal(s.writes.length,1);await key(s,'w');await key(s,'x');
    assert.equal(s.writes.length,1,'a decision in flight blocks the next shortcut');
    s.accept(0);await first;
    s.el('#assetDialog').open=false;await key(s,'w');assert.equal(s.writes.length,1,'a closed dialog ignores the shortcut');
  });
  await test('An unconfirmed earlier save or a conflict is never replayed or replaced by a verdict',async()=>{
    const s=open();s.el('#assetNotes').value='draft';const lost=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('response lost'));await lost;
    assert.notEqual(s.run('assetDetailPending'),null);const body=s.writes[0].options.body;
    await key(s,'k');assert.equal(s.writes.length,1,'the shortcut does not resend the earlier command');assert.equal(s.writes[0].options.body,body);
    assert.match(s.el('#assetDetailStatus').textContent,/Resolve the earlier save .* review mark/);
    const c=open();c.run("assetDetailConflict={current:[]}");await key(c,'x');assert.equal(c.writes.length,0);assert.match(c.el('#assetDetailStatus').textContent,/Resolve the earlier save/);
  });
  await test('A private picture saves its verdict under the private scope',async()=>{
    const W='1'.repeat(32),s=setup({autoOpen:false});
    await s.dispatch('studio:privacy-change',{detail:{scope:'private',previousScope:'regular'}});
    s.run(`assetState.assets=[{id:'p1',workspace_id:${JSON.stringify(W)},privacy:'private',title:'p',notes:'',tags:[],review:'unreviewed',favorite:false,trashed_at:null,media_type:'image',job_id:'pj',metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,url:'/api/assets/p1/file?privacy=private'}];openAsset('p1')`);
    const pending=key(s,'k');assert.equal(s.writes.length,1);
    assert.equal(s.writes[0].options.headers['X-Studio-Privacy'],'private');assert.deepEqual(s.metadata(0),{ids:['p1'],action:'edit',review:'selected'});assert.equal(s.payload(0).workspace_id,W);
    s.accept(0);await pending;assert.deepEqual(pressed(s),['selected']);
    await s.dispatch('studio:privacy-change',{detail:{scope:'regular',previousScope:'private'}});
    assert.equal(s.el('#assetQueue').hidden,true,'switching scope retires the private picture and its row');await key(s,'w');assert.equal(s.writes.length,1);
  });
  console.log('Asset verdict row contracts passed:',count);
})().catch(error=>{console.error(error);process.exitCode=1;});
