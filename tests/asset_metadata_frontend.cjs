'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const conflict=(s,current)=>{const e=Error('Asset changed; nothing applied');e.status=409;e.data={workspace_id:s.run('activeAsset.workspace_id'),code:'asset_revision_conflict',request_id:s.payload(s.writes.length-1).request_id,current:[{trashed_at:null,...current}],conflict_ids:['a'],missing_ids:[]};s.writes.at(-1).reject(e);};
const saved=(s,fields={})=>({...JSON.parse(s.run('JSON.stringify(activeAsset)')),metadata_revision:1,...fields});
let count=0;
async function check(name,fn){await fn();count++;console.log('PASS',name);}
(async()=>{
  await check('Save binds the opened snapshot, not refreshed library metadata',async()=>{
    const s=setup();s.el('#assetNotes').value='edit';s.run('assetState.assets=assetState.assets.map(a=>({...a,metadata_revision:2}))');
    const p=s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,1);
    assert.deepEqual(s.payload(0).expected_revisions,{a:0});assert.equal(typeof s.payload(0).request_id,'string');
    s.accept(0);await p;assert.equal(s.run('activeAsset.metadata_revision'),1);
  });
  await check('Conflict retains edits, offers comparison and never auto-writes',async()=>{
    const s=setup();s.el('#assetTitle').value='My title';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,saved(s,{notes:'Their notes'}));await p;
    assert.equal(s.el('#assetTitle').value,'My title');assert.equal(s.el('#saveAssetDetails').disabled,true);
    assert.match(s.el('#assetDetailConflict').innerHTML,/Their notes/);assert.equal(s.writes.length,1);
    s.run('resolveAssetConflict(true)');assert.equal(s.el('#assetTitle').value,'My title');assert.equal(s.el('#assetNotes').value,'Their notes');
    assert.equal(s.run('activeAsset.metadata_revision'),1);assert.equal(s.writes.length,1);
    const next=s.el('#saveAssetDetails').onclick();assert.deepEqual(s.payload(1).expected_revisions,{a:1});assert.equal(s.payload(1).notes,undefined);
    s.accept(1);await next;assert.equal(s.el('#assetNotes').value,'Their notes');
  });
  await check('Same-field conflict preserves both versions and escapes markup',async()=>{
    const s=setup();s.el('#assetNotes').value='My correction';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,saved(s,{notes:'<img src=x onerror=evil()>Their correction'}));await p;
    assert.match(s.el('#assetDetailConflict').innerHTML,/Both changed/);assert.doesNotMatch(s.el('#assetDetailConflict').innerHTML,/<img/);
    s.run('resolveAssetConflict(false)');assert.equal(s.el('#assetNotes').value,'<img src=x onerror=evil()>Their correction');assert.equal(s.run('assetDetailDirty()'),false);assert.equal(s.writes.length,1);
  });
  await check('Unknown save retry keeps the same immutable body while newer typing survives',async()=>{
    const s=setup();s.el('#assetNotes').value='earlier';let p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('response lost'));await p;
    s.el('#assetNotes').value='newer';p=s.el('#saveAssetDetails').onclick();assert.equal(s.writes[1].options.body,s.writes[0].options.body);
    s.accept(1);await p;assert.equal(s.el('#assetNotes').value,'newer');assert.equal(s.run('assetDetailDirty()'),true);assert.equal(s.run('activeAsset.notes'),'earlier');
  });
  await check('Receipt lookup confirms without a second POST',async()=>{
    const s=setup();s.el('#assetNotes').value='earlier';const p=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost'));await p;
    const observing=s.run('checkAssetSave()');assert.equal(s.reads.length,1);assert.match(s.reads[0].url,/\/api\/assets\/commands\//);
    s.reads[0].resolve(s.receipt(0));await observing;assert.equal(s.writes.length,1);assert.equal(s.run('assetDetailDirty()'),false);
  });
  await check('Missing receipt stays unknown; malformed success is never accepted',async()=>{
    const s=setup();s.el('#assetNotes').value='keep';const p=s.el('#saveAssetDetails').onclick();s.writes[0].resolve({});await p;
    assert.equal(s.run('assetDetailDirty()'),true);assert.match(s.el('#assetDetailStatus').textContent,/not confirmed/);
    const observing=s.run('checkAssetSave()');s.reads[0].resolve({status:'unknown',workspace_id:s.payload(0).workspace_id,request_id:s.payload(0).request_id});await observing;
    assert.equal(s.writes.length,1);assert.equal(s.run('assetDetailDirty()'),true);assert.equal(s.el('#assetFavorite').disabled,true);
  });
  await check('Missing revision blocks writes rather than guessing zero',async()=>{
    const s=setup();s.run('delete activeAsset.metadata_revision');s.el('#assetNotes').value='keep';await s.el('#saveAssetDetails').onclick();assert.equal(s.writes.length,0);assert.match(s.el('#assetDetailStatus').textContent,/Reload/);
  });
  await check('A recovered Trash command cannot discard typing after its lost reply',async()=>{
    const s=setup();s.approve(true);s.el('#assetNotes').value='First draft';
    const p=s.el('#assetTrash').onclick();s.writes[0].reject(Error('lost Trash reply'));await p;
    s.el('#assetNotes').value='New notes after loss';const observing=s.run('checkAssetSave()');
    const receipt=s.receipt(0);receipt.applied={trashed_at:123};s.reads[0].resolve(receipt);await observing;
    assert.equal(s.el('#assetDialog').open,true);assert.equal(s.el('#assetNotes').value,'New notes after loss');
    assert.equal(s.run('activeAsset.trashed_at'),123);assert.equal(s.run('assetDetailDirty()'),true);
  });
  await check('Malformed conflict snapshots never replace the draft',async()=>{
    const s=setup();s.el('#assetNotes').value='Keep';const p=s.el('#saveAssetDetails').onclick();
    conflict(s,{id:'a',metadata_revision:1,tags:'not an array'});await p;
    assert.doesNotThrow(()=>s.run('resolveAssetConflict(false)'));assert.equal(s.el('#assetNotes').value,'Keep');
    assert.equal(s.run('assetDetailConflict'),null);assert.equal(s.run('assetDetailPending.body'),s.writes[0].options.body);
    assert.match(s.el('#assetDetailStatus').textContent,/could not be verified/);
  });
  await check('A library receipt does not wait for a stalled refresh',async()=>{
    const s=setup();s.run('refreshAssets=()=>new Promise(()=>{})');
    const p=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})");s.accept(0);
    const winner=await Promise.race([p.then(()=>true),new Promise(resolve=>setTimeout(()=>resolve(false),50))]);
    assert.equal(winner,true);assert.equal(s.run('assetState.assets[0].favorite'),true);
  });
  const library=()=>{const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';
    s.run("assetState.assets.forEach((a,i)=>{a.created_at=i;a.collections=[];a.preset_name='Recipe '+a.id;});renderAssets()");return s;};
  const sample="[{id:'1',preset_name:'Anima',job_id:'j1',created_at:0},{id:'2',preset_name:'Krea',job_id:'j1',created_at:0},{id:'3',preset_name:'Anima',job_id:'j2',created_at:0}]";
  await check('Grouping is a pure projection with first-seen sections',()=>{
    const s=setup({autoOpen:false});
    const group=(mode,field='key')=>JSON.parse(s.run(`JSON.stringify(assetGroups(${sample},'${mode}').map(g=>[g.${field},g.assets.map(a=>a.id)]))`));
    assert.deepEqual(group('recipe'),[['recipe:Anima',['1','3']],['recipe:Krea',['2']]]);
    assert.deepEqual(group('run'),[['run:j1',['1','2']],['run:j2',['3']]]);
    assert.deepEqual(group('none'),[['',['1','2','3']]]);
    assert.deepEqual(group('recipe','label')[0][0],'Anima');
    // The same input twice gives the same sections; grouping never reorders or drops an asset.
    assert.deepEqual(group('recipe'),group('recipe'));
  });
  await check('Day grouping keys on the local calendar date and names missing dates',()=>{
    const s=setup({autoOpen:false});
    assert.match(s.run("assetGroupOf({created_at:1789228800},'day').key"),/^day:\d{4}-\d{2}-\d{2}$/);
    assert.equal(s.run("assetGroupOf({created_at:1789228800},'day').key"),s.run("assetGroupOf({created_at:1789228800+60},'day').key"));
    assert.deepEqual(s.run("assetGroupOf({},'day').label"),'No date recorded');
    assert.deepEqual(s.run("assetGroupOf({job_id:''},'run').label"),'No run recorded');
  });
  await check('A queue decision uses the ordinary edit save and then advances',async()=>{
    const s=library();
    assert.match(s.el('#reviewNext').textContent,/2 unreviewed/);
    s.run('startReviewQueue()');
    assert.equal(s.run('activeAsset.id'),'b');assert.match(s.el('#assetQueue').innerHTML,/1 of 2/);
    const p=s.run("assetQueueDecide('needs_work')");
    assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['b'],action:'edit',review:'needs_work'});
    s.accept(0);await p;
    assert.equal(s.run('activeAsset.id'),'a');assert.match(s.el('#assetQueue').innerHTML,/2 of 2/);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='b').review"),'needs_work');
  });
  await check('An unconfirmed queue decision never advances past its evidence',async()=>{
    const s=library();s.run('startReviewQueue()');
    const p=s.run("assetQueueDecide('selected')");s.writes[0].reject(Error('response lost'));await p;
    assert.equal(s.run('activeAsset.id'),'b');assert.match(s.el('#assetDetailStatus').textContent,/not confirmed/);
  });
  await check('Opening an asset outside the queue leaves queue mode instead of skipping one',()=>{
    const s=library();s.run("assetState.assets.push({...assetState.assets[0],id:'c',title:'c',job_id:'job-b',review:'selected',metadata_revision:0});renderAssets();startReviewQueue()");
    assert.equal(s.run('assetQueue.ids.length'),2);assert.equal(s.run('activeAsset.id'),'b');
    s.run("openAsset('c')");
    assert.equal(s.run('activeAsset.id'),'c');assert.equal(s.run('assetQueue'),null);
    assert.equal(s.el('#assetQueue').hidden,true);assert.match(s.el('#assetMessage').textContent,/Left the review queue/);
  });
  await check('The end of the queue still asks before discarding unsaved typing',()=>{
    const s=library();s.run('startReviewQueue()');
    s.run('assetQueue.index=assetQueue.ids.length-1');s.el('#assetNotes').value='unsaved thought';
    s.run('assetQueueStep(1)');
    assert.equal(s.el('#assetDialog').open,true);assert.equal(s.confirmations(),1);
    assert.equal(s.el('#assetNotes').value,'unsaved thought');assert.equal(s.writes.length,0);
  });
  await check('Reason chips toggle tags without typing and save nothing on their own',()=>{
    const s=setup();
    s.run("toggleAssetReason('hands')");
    assert.equal(s.el('#assetTags').value,'tag, hands');assert.match(s.el('#assetReviewReasons').innerHTML,/aria-pressed="true"/);
    s.run("toggleAssetReason('hands')");
    assert.equal(s.el('#assetTags').value,'tag');assert.equal(s.writes.length,0);
  });
  await check('A confirmed single review updates the loaded record without refetching the workspace',async()=>{
    const s=setup();s.run('globalThis.__refetches=0;refreshAssets=async()=>{globalThis.__refetches++;};');
    s.el('#assetReview').value='selected';const p=s.el('#saveAssetDetails').onclick();s.accept(0);await p;
    assert.equal(s.run('globalThis.__refetches'),0);
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').review"),'selected');
  });
  await check('Bulk review saves each selected asset once and lists every failure',async()=>{
    const s=library();s.run("assetSelection=new Set(['a','b']);renderAssets()");
    const p=s.run("bulkReviewSelected('rejected')");
    assert.equal(s.writes.length,2);assert.deepEqual(s.payload(0).ids,['a']);assert.deepEqual(s.payload(1).ids,['b']);
    assert.equal(s.payload(0).review,'rejected');assert.deepEqual(s.payload(0).expected_revisions,{a:0});
    s.accept(0);s.writes[1].reject(Error('Workspace unavailable'));await p;
    assert.equal(s.run("assetState.assets.find(a=>a.id==='a').review"),'rejected');
    assert.equal(s.run("assetState.assets.find(a=>a.id==='b').review"),'unreviewed');
    assert.match(s.el('#assetBulkReviewStatus').textContent,/1 of 2 marked as Rejected/);
    assert.match(s.el('#assetBulkReviewStatus').textContent,/1 failed and no retry was sent/);
    assert.match(s.el('#assetBulkReviewStatus').textContent,/not confirmed/);
  });
  // Group triage (#939): the same edit command as selection review, one confirmed decision per visible group.
  const tick=()=>new Promise(resolve=>setImmediate(resolve));
  const groupLibrary=(n,recipe='WAI v17 • illustration')=>{const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';
    s.run(`assetGroupMode='recipe';assetState.assets=Array.from({length:${n}},(_,i)=>({id:'g'+i,workspace_id:assetState.workspace_id,title:'g'+i,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',preset_name:${JSON.stringify(recipe)},preset_id:'wai',job_id:'job-g',metadata_revision:0,source:{},lineage:[],collections:[],created_at:i,bytes:1}));renderAssets()`);
    s.run('globalThis.__prompts=[];window.confirm=m=>{__prompts.push(m);return globalThis.__approve??true;}');return s;};
  const acceptBatch=(s,i)=>{const r=s.receipt(i);r.current=r.current.slice(0,10);s.writes[i].resolve(r);};
  const review=(s,id)=>s.run(`assetState.assets.find(a=>a.id==='${id}').review`);
  const groupKey="'recipe:WAI v17 • illustration'";
  await check('Group triage names the count and decision and marks only visible unreviewed assets of that group',async()=>{
    const s=groupLibrary(5);
    s.run("assetState.assets[0].review='selected';assetState.assets[1].media_type='video';assetState.assets.push({...assetState.assets[2],id:'other',title:'other',preset_name:'Krea'});");
    s.el('#assetType').value='image';s.run('renderAssets()');
    assert.deepEqual(JSON.parse(s.run(`JSON.stringify(assetGroupReviewPlan(${groupKey}).ids)`)).sort(),['g2','g3','g4']);
    s.run('globalThis.__approve=false');
    assert.equal(await s.run(`bulkReviewGroup(${groupKey},'rejected')`),false);
    assert.equal(s.writes.length,0);assert.match(s.el('#assetMessage').textContent,/Nothing was changed/);
    s.run('globalThis.__approve=true');
    const p=s.run(`bulkReviewGroup(${groupKey},'rejected')`);
    const prompt=s.run('__prompts.at(-1)');
    assert.match(prompt,/^Mark 3 unreviewed pictures in 'WAI v17 • illustration' as Rejected\?/);
    assert.match(prompt,/1 already reviewed keeps its review/);assert.match(prompt,/changed back individually/);
    assert.equal(s.writes.length,1);assert.deepEqual(s.metadata(0),{ids:['g4','g3','g2'],action:'edit',review:'rejected'});
    assert.deepEqual(s.payload(0).expected_revisions,{g4:0,g3:0,g2:0});
    s.accept(0);assert.equal(await p,true);
    for(const id of ['g2','g3','g4'])assert.equal(review(s,id),'rejected');
    assert.equal(review(s,'g0'),'selected');assert.equal(review(s,'g1'),'unreviewed');assert.equal(review(s,'other'),'unreviewed');
    assert.match(s.el('#assetMessage').textContent,/Marked 3 of 3 in 'WAI v17 • illustration' as Rejected/);
    assert.equal(s.run(`assetGroupReviewPlan(${groupKey}).ids.length`),0);
  });
  await check('Group actions are escaped buttons naming their count, and vanish once nothing is unreviewed',()=>{
    const s=groupLibrary(2,'<img src=x onerror=evil()>');
    const html=s.run('assetGroupActionsHTML(assetGroups(visibleAssets(),assetGroupMode)[0])');
    assert.doesNotMatch(html,/<img/);assert.match(html,/Mark 2 unreviewed as/);
    assert.equal((html.match(/<button type="button" data-group-review=/g)||[]).length,3);
    assert.match(html,/aria-label="Mark 2 unreviewed in &lt;img src=x onerror=evil\(\)&gt; as Needs work"/);
    s.run("assetState.assets.forEach(a=>{a.review='needs_work';})");
    assert.equal(s.run('assetGroupActionsHTML(assetGroups(visibleAssets(),assetGroupMode)[0])'),'');
    s.run("assetGroupMode='none'");assert.equal(s.run(`assetGroupReviewPlan('recipe:x')`),null);
  });
  await check('A group larger than the command limit is split into sequential batches with their own preconditions',async()=>{
    const s=groupLibrary(205);
    const p=s.run(`bulkReviewGroup(${groupKey},'needs_work')`);
    assert.match(s.run('__prompts[0]'),/^Mark 205 unreviewed pictures/);
    assert.equal(s.writes.length,1);assert.equal(s.payload(0).ids.length,200);
    // Revisions are fixed at confirmation: a refresh that saw another client's change cannot become an overwrite.
    s.run("assetState.assets.find(a=>a.id==='g0').metadata_revision=7");
    acceptBatch(s,0);await tick();
    assert.equal(s.writes.length,2);assert.equal(s.payload(1).ids.length,5);
    assert.equal(s.payload(1).expected_revisions.g0,0);assert.notEqual(s.payload(0).request_id,s.payload(1).request_id);
    assert.deepEqual(new Set([...s.payload(0).ids,...s.payload(1).ids]).size,205);
    acceptBatch(s,1);assert.equal(await p,true);
    assert.match(s.el('#assetMessage').textContent,/Marked 205 of 205/);
    assert.equal(review(s,'g0'),'unreviewed');assert.equal(review(s,'g1'),'needs_work');
  });
  await check('A stale revision stops the run cleanly and reports how many were applied',async()=>{
    const s=groupLibrary(401);
    const p=s.run(`bulkReviewGroup(${groupKey},'rejected')`);
    acceptBatch(s,0);await tick();assert.equal(s.writes.length,2);
    const e=Error('Selected asset metadata changed or no longer exists; nothing changed in this batch');e.status=409;
    e.data={code:'asset_revision_conflict',workspace_id:s.payload(1).workspace_id,request_id:s.payload(1).request_id,conflict_ids:[s.payload(1).ids[0]],missing_ids:[],current:[]};
    s.writes[1].reject(e);assert.equal(await p,false);await tick();
    assert.equal(s.writes.length,2);
    const text=s.el('#assetMessage').textContent;
    assert.match(text,/^200 of 401 marked/);assert.match(text,/Batch 2 \(200 pictures\) was not applied: 1 of its assets changed elsewhere/);assert.match(text,/No retry was sent/);
    assert.equal(s.run("assetState.assets.filter(a=>a.review==='rejected').length"),200);
    assert.equal(s.run('assetBulkReviewBusy'),false);
  });
  await check('An unconfirmed batch stops the run without a retry or a later batch',async()=>{
    const s=groupLibrary(401);
    const p=s.run(`bulkReviewGroup(${groupKey},'selected')`);
    s.writes[0].reject(Error('response lost'));assert.equal(await p,false);await tick();
    assert.equal(s.writes.length,1);assert.equal(s.run("assetState.assets.filter(a=>a.review==='selected').length"),0);
    assert.match(s.el('#assetMessage').textContent,/^0 of 401 marked.*Batch 1 \(200 pictures\) is not confirmed: it may or may not have been applied/);
  });
  await check('Group status belongs to its Workspace generation and a replaced Workspace gets no further batch',async()=>{
    const s=groupLibrary(401);
    const p=s.run(`bulkReviewGroup(${groupKey},'rejected')`);
    assert.equal(await s.run(`bulkReviewGroup(${groupKey},'needs_work')`),false);assert.equal(s.writes.length,1);
    s.run("assetState={...assetState,workspace_id:'2'.repeat(32),assets:assetState.assets.map(a=>({...a,workspace_id:'2'.repeat(32)}))};renderAssets()");
    acceptBatch(s,0);assert.equal(await p,false);await tick();
    assert.equal(s.writes.length,1);
    assert.equal(s.run("assetState.assets.filter(a=>a.review!=='unreviewed').length"),0);
    assert.match(s.el('#assetMessage').textContent,/Workspace changed while it ran\. 200 of 401 were confirmed.*earlier Workspace\. Nothing was marked in the Workspace now shown/);
  });
  // Group source marking (#939): the same confirmed, batched edit as group triage, carrying run_label instead of review.
  const labels=s=>JSON.parse(s.run('JSON.stringify(Object.fromEntries(assetState.assets.map(a=>[a.id,a.run_label??null])))'));
  await check('Group source marking names count and label, hides the group under Mine, and is reversible',async()=>{
    const s=groupLibrary(3);s.run("assetState.assets.push({...assetState.assets[0],id:'other',title:'other',preset_name:'Krea'});renderAssets()");
    const html=s.run('assetGroupSourceHTML(assetGroups(visibleAssets(),assetGroupMode)[0])');
    assert.match(html,/data-group-source="agent"[^>]*>Mark 3 as agent runs</);assert.doesNotMatch(html,/data-group-source="mine"/);
    s.run('globalThis.__approve=false');assert.equal(await s.run(`bulkSourceGroup(${groupKey},'agent')`),false);assert.equal(s.writes.length,0);
    s.run('globalThis.__approve=true');
    const p=s.run(`bulkSourceGroup(${groupKey},'agent')`);
    assert.match(s.run('__prompts.at(-1)'),/^Mark 3 pictures in 'WAI v17 • illustration' as agent runs \(label 'Agent lab'\)\?\n\nThe Mine view hides agent runs; Mark as mine brings them back\./);
    assert.deepEqual(s.metadata(0),{ids:['g2','g1','g0'],action:'edit',run_label:'Agent lab'});assert.deepEqual(s.payload(0).expected_revisions,{g2:0,g1:0,g0:0});
    s.accept(0);assert.equal(await p,true);
    assert.deepEqual(labels(s),{g0:'Agent lab',g1:'Agent lab',g2:'Agent lab',other:null});
    assert.deepEqual(JSON.parse(s.run('JSON.stringify(visibleAssets().map(a=>a.id))')),['other']);
    assert.match(s.el('#assetMessage').textContent,/^Marked 3 of 3 in 'WAI v17 • illustration' as agent runs\. The Mine view now hides them/);
    s.run("chooseAssetSource('agent')");
    assert.match(s.run('assetGroupSourceHTML(assetGroups(visibleAssets(),assetGroupMode)[0])'),/data-group-source="mine"[^>]*>Mark 3 as mine</);
    const back=s.run(`bulkSourceGroup(${groupKey},'mine')`);assert.match(s.run('__prompts.at(-1)'),/as yours\?\n\nThis clears their run label/);
    assert.deepEqual(s.metadata(1),{ids:['g2','g1','g0'],action:'edit',run_label:null});s.accept(1);assert.equal(await back,true);
    assert.deepEqual(labels(s),{g0:null,g1:null,g2:null,other:null});assert.equal(s.el('#assetSource').hidden,true);
  });
  await check('Group source marking changes only the other source, refuses a bad label and shares the busy lock',async()=>{
    const s=groupLibrary(3);s.run("assetState.assets[0].run_label='Night lab';chooseAssetSource('all')");
    const plan=JSON.parse(s.run(`JSON.stringify(assetGroupSourcePlan(${groupKey},'agent'))`));assert.deepEqual(plan.ids,['g2','g1']);assert.equal(plan.unchanged,1);
    s.el('#bulkRunLabel').value='line\nbreak';assert.equal(await s.run(`bulkSourceGroup(${groupKey},'agent')`),false);assert.equal(s.run('__prompts.length'),0);
    assert.match(s.el('#assetMessage').textContent,/printable characters/);
    s.el('#bulkRunLabel').value='';const p=s.run(`bulkSourceGroup(${groupKey},'agent')`);
    assert.match(s.run('__prompts.at(-1)'),/; 1 already an agent run keeps its label\.$/);
    assert.equal(await s.run(`bulkReviewGroup(${groupKey},'rejected')`),false);assert.equal(s.writes.length,1);
    s.accept(0);assert.equal(await p,true);assert.deepEqual(labels(s),{g0:'Night lab',g1:'Agent lab',g2:'Agent lab'});
    assert.match(s.el('#assetMessage').textContent,/Mark as mine reverses it\.$/);
  });
  await check('Bulk review names the saved reviews it would replace and writes nothing without consent',async()=>{
    const s=library();s.run("assetState.assets.find(a=>a.id==='a').review='selected';assetState.assets.find(a=>a.id==='b').review='needs_work';assetSelection=new Set(['a','b']);renderAssets()");
    s.run('globalThis.__prompts=[];window.confirm=m=>{__prompts.push(m);return !!globalThis.__approve;}');
    await s.run("bulkReviewSelected('rejected')");
    assert.equal(s.writes.length,0);assert.match(s.run('__prompts[0]'),/^Replace 2 saved reviews\? 1 keeper, 1 needs work will change to Rejected\./);
    assert.match(s.el('#assetBulkReviewStatus').textContent,/Nothing was changed/);
    s.run('__approve=true');const p=s.run("bulkReviewSelected('rejected')");assert.equal(s.writes.length,2);s.accept(0);s.accept(1);await p;
    assert.equal(s.run("assetState.assets.filter(a=>a.review==='rejected').length"),2);
    // Only unreviewed or already-matching assets: no question is asked.
    s.run('__prompts=[]');const again=s.run("bulkReviewSelected('rejected')");s.accept(2);s.accept(3);await again;assert.equal(s.run('__prompts.length'),0);
  });
  console.log('Asset metadata frontend contracts passed:',count);
})().catch(e=>{console.error(e);process.exitCode=1;});
