// Causal page, selection and same-run contracts against the shipped Workspace script.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const scope='1'.repeat(32),stamp={epoch:'a'.repeat(32),revision:1};
const asset=(id,extra={})=>({id,workspace_id:scope,title:id,notes:'notes',tags:[],review:'unreviewed',favorite:false,trashed_at:null,
  media_type:'image',preset_id:'hero',preset_name:'Hero',job_id:'run',created_at:1,metadata_revision:0,source:{},lineage:[],collections:[],bytes:1,...extra});
const collection=(catalogue=stamp,extra={})=>({format:'studio.collection-page/v1',workspace_id:scope,catalogue,collections:[],next_cursor:null,observation_only:true,...extra});
const page=(assets,extra={})=>{const catalogue=extra.catalogue||stamp;return {format:'studio.asset-page/v1',workspace_id:scope,catalogue,assets,cursor:null,next_cursor:null,unavailable_assets:[],collection_page:collection(catalogue),observation_only:true,...extra};};
const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
const value=(s,code)=>JSON.parse(s.run('JSON.stringify('+code+')'));
const query=(s,i)=>new URL(s.reads[i].url,'http://fixture').searchParams;
function init(){const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';s.run('refreshAssets='+s.actualRefresh.toString());return s;}
// The baseline used a second read: settle it only to expose each independent defect.
function reply(s,i,data){s.reads[i].resolve(data);if(s.reads[i+1]?.url.startsWith('/api/collections?'))s.reads[i+1].resolve(collection(data.catalogue));}
async function load(s,assets=[asset('a')],extra={},position=null){const i=s.reads.length,p=s.actualRefresh(true,position);reply(s,i,page(assets,extra));assert.equal(await p,true);return i;}
async function observe(s,items){const i=s.writes.length,p=s.run('resolveAssetIDs('+JSON.stringify(items.map(a=>a.id))+')');s.writes[i].resolve({workspace_id:scope,catalogue:stamp,items});assert.equal(await p,true);}
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log('PASS',name);}catch(error){failed++;console.error('FAIL',name,'\n'+error.stack);}}
(async()=>{
  await test('The Library reads assets and collections in one bounded observation',async()=>{
    const s=init();await load(s);assert.equal(s.reads.length,1);assert.equal(query(s,0).get('include_collections'),'true');assert.equal(query(s,0).get('details'),'true');assert.equal(query(s,0).get('limit'),'100');
  });
  await test('An inconsistent collection bundle cannot replace the accepted page',async()=>{
    const s=init();await load(s);const i=s.reads.length,p=s.actualRefresh(true);
    reply(s,i,page([asset('foreign')],{collection_page:collection(stamp,{workspace_id:'2'.repeat(32)})}));
    assert.equal(await p,false);assert.equal(s.run('assetState.assets[0].id'),'a');assert.match(s.el('#assetMessage').textContent,/Workspace or catalogue/);
  });
  await test('Unavailable detail rows are counted on this page without becoming editable or missing',async()=>{
    const s=init();await load(s,[asset('a')],{unavailable_assets:[{id:'oversized',code:'asset_read_limit',error:'Notes exceed <limit>'}],next_cursor:'continue'});
    s.run("assetSelection=new Set(['oversized']);renderAssets()");
    assert.match(s.el('#assetVisibleCount').textContent,/1 available of 2 observed assets on this page/);
    assert.match(s.el('#assetPaging').innerHTML,/oversized/);assert.match(s.el('#assetPaging').innerHTML,/Notes exceed &lt;limit&gt;/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="oversized"/);
    assert.equal(s.run('assetSelectionInfo().unresolved'),1);assert.equal(s.run('assetSelectionInfo().missing'),0);assert.equal(s.run("assetRecord('oversized')"),undefined);assert.equal(s.run('assetPaging.next'),'continue');
  });
  await test('A page with only unavailable details does not claim the Library is empty',async()=>{
    const s=init();await load(s,[],{unavailable_assets:[{id:'large',code:'asset_read_limit',error:'Too large'}]});
    assert.match(s.el('#assetGrid').innerHTML,/Details unavailable on this page/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/Your library is empty|None of your own runs here|Nothing in this view/);
    assert.match(s.el('#assetTotal').textContent,/0 available of 1/);
  });
  await test('A refused detail row is not automatically reread through Recent outputs or retained selection',async()=>{
    const s=init();s.run("jobs=[{outputs:[{asset_id:'large'}]}];assetSelection=new Set(['large'])");
    const i=s.reads.length,p=s.actualRefresh(true,{cursor:null,history:[],reanchor:true});reply(s,i,page([asset('a')],{unavailable_assets:[{id:'large',code:'asset_read_limit',error:'Too large'}]}));await flush();
    assert.equal(s.writes.length,0);assert.equal(await p,true);assert.match(s.el('#assetPaging').innerHTML,/Too large/);assert.equal(s.run('assetSelectionInfo().unresolved'),1);
  });
  await test('A known missing Recent output is observed once until the catalogue changes',async()=>{
    const s=init();s.run("jobs=[{outputs:[{asset_id:'gone'}]}]");let i=s.reads.length,p=s.actualRefresh(true);reply(s,i,page([asset('a')]));await flush();
    assert.equal(s.writes.length,1);s.writes[0].resolve({workspace_id:scope,catalogue:stamp,items:[{id:'gone',state:'missing',asset:null}]});await p;
    i=s.reads.length;p=s.actualRefresh();reply(s,i,page([asset('a')]));await flush();assert.equal(s.writes.length,1,'an unchanged page must not re-query a known deletion');assert.equal(await p,true);
    i=s.reads.length;p=s.actualRefresh();reply(s,i,page([asset('a')],{catalogue:{...stamp,revision:2}}));await flush();assert.equal(s.writes.length,2);
    s.writes[1].resolve({workspace_id:scope,catalogue:{...stamp,revision:2},items:[{id:'gone',state:'missing',asset:null}]});assert.equal(await p,true);
  });
  await test('A refused off-page supplemental observation cannot hide the accepted complete Library page',async()=>{
    const s=init();await load(s,[asset('before')]);s.run("jobs=[{outputs:[{asset_id:'oversized-off-page'}]}]");const i=s.reads.length,n=s.writes.length,p=s.actualRefresh(true);
    reply(s,i,page([asset('complete')]));await flush();assert.equal(s.writes[n].url,'/api/assets/selection');s.writes[n].reject(Object.assign(Error('Asset details exceed the observation bound'),{status:503,data:{code:'asset_read_unavailable'}}));assert.equal(await p,false);
    assert.match(s.el('#assetGrid').innerHTML,/data-asset-card="complete"/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/data-asset-card="before"/);assert.equal(s.run("assetRecord('oversized-off-page')"),undefined);assert.match(s.el('#assetMessage').textContent,/page.*loaded.*details.*could not/i);assert.equal(s.writes.length,n+1);
  });
  await test('A confirmed Library edit reanchors its page and refreshes off-page selection accounting',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'page-three',next_cursor:'page-four'},{cursor:'page-three',history:[null,'page-two']});
    await observe(s,[{id:'off',state:'active',asset:asset('off')}]);s.run("assetSelection=new Set(['a','off'])");
    const n=s.writes.length,r=s.reads.length,p=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})");s.accept(n);await p;await flush();
    assert.equal(query(s,r).get('cursor'),'page-three');assert.equal(query(s,r).get('reanchor'),'true');assert.equal(query(s,r).get('workspace_id'),scope);assert.equal(s.run('assetLibraryPending'),null);
    reply(s,r,page([asset('a',{favorite:true,metadata_revision:1})],{cursor:'fresh-three',next_cursor:'fresh-four',catalogue:{...stamp,revision:2}}));await flush();
    assert.equal(s.writes.length,n+2,'only the retained off-page selection needs a bounded observation');assert.equal(s.writes[n+1].url,'/api/assets/selection');assert.deepEqual(JSON.parse(s.writes[n+1].options.body).ids,['off']);
    s.writes[n+1].resolve({workspace_id:scope,catalogue:{...stamp,revision:2},items:[{id:'off',state:'trashed',asset:asset('off',{trashed_at:0,metadata_revision:4})}]});await flush();
    assert.equal(s.run('assetPaging.cursor'),'fresh-three');assert.deepEqual(value(s,'assetPaging.history'),[null,'page-two']);assert.deepEqual(value(s,'[...assetSelection]'),['a','off']);assert.equal(s.run('assetSelectionInfo().unresolved'),0);assert.match(s.el('#assetSelectedList').innerHTML,/In Trash/);
  });
  await test('Only a historical Previous anchor may reanchor; Next remains strict after the write',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'page-three',next_cursor:'page-four'},{cursor:'page-three',history:[null,'page-two']});
    const n=s.writes.length,r=s.reads.length,p=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})");s.accept(n);await p;
    reply(s,r,page([asset('a',{metadata_revision:1,favorite:true})],{cursor:'fresh-three',next_cursor:'fresh-four',catalogue:{...stamp,revision:2}}));await flush();
    let i=s.reads.length,m=s.run('moveAssetPage(true)');assert.equal(query(s,i).get('cursor'),'fresh-four');assert.equal(query(s,i).has('reanchor'),false);assert.equal(s.reads.length,i+1);
    reply(s,i,page([asset('four')],{cursor:'fresh-four',catalogue:{...stamp,revision:2}}));await m;
    i=s.reads.length;m=s.run('moveAssetPage(false)');assert.equal(query(s,i).get('cursor'),'fresh-three');assert.equal(query(s,i).has('reanchor'),false);reply(s,i,page([asset('a')],{cursor:'fresh-three',next_cursor:'fresh-four',catalogue:{...stamp,revision:2}}));await m;
    i=s.reads.length;m=s.run('moveAssetPage(false)');assert.equal(query(s,i).get('cursor'),'page-two');assert.equal(query(s,i).get('reanchor'),'true');reply(s,i,page([asset('two')],{cursor:'fresh-two',next_cursor:'fresh-three',catalogue:{...stamp,revision:2}}));await m;assert.match(s.el('#assetPaging').innerHTML,/Page 2/);
  });
  await test('A held page overlapping a receipt preserves its boundary on the bounded reread',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'second'},{cursor:'second',history:[null]});s.run("openAsset('a')");
    const r=s.reads.length,reading=s.actualRefresh();s.el('#assetNotes').value='confirmed';const n=s.writes.length,saving=s.el('#saveAssetDetails').onclick();s.accept(n);await saving;
    reply(s,r,page([asset('a')],{cursor:'second'}));await flush();const next=r+1;
    assert.equal(query(s,next).get('cursor'),'second');assert.equal(query(s,next).get('reanchor'),'true');reply(s,next,page([asset('a',{metadata_revision:1,notes:'confirmed'})],{cursor:'new-second',catalogue:{...stamp,revision:2}}));assert.equal(await reading,true);assert.equal(s.run('assetPaging.cursor'),'new-second');assert.equal(s.run("assetRecord('a').notes"),'confirmed');
  });
  await test('A stale cursor rejection racing an own receipt reanchors the same boundary',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'second'},{cursor:'second',history:[null]});s.run("openAsset('a')");const r=s.reads.length,reading=s.actualRefresh();
    s.el('#assetNotes').value='confirmed';const n=s.writes.length,saving=s.el('#saveAssetDetails').onclick();s.accept(n);await saving;
    s.reads[r].reject(Object.assign(Error('Catalogue changed'),{status:409,data:{code:'asset_cursor_stale'}}));await flush();
    assert.equal(query(s,r+1).get('cursor'),'second');assert.equal(query(s,r+1).get('reanchor'),'true');reply(s,r+1,page([asset('a',{metadata_revision:1,notes:'confirmed'})],{cursor:'new-second',catalogue:{...stamp,revision:2}}));assert.equal(await reading,true);assert.equal(s.reads.length,r+2);assert.equal(s.run('assetPaging.history.length'),1);
  });
  await test('A reanchor cannot accept a complete bundle from a different Workspace',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'second'},{cursor:'second',history:[null]});const i=s.reads.length,p=s.actualRefresh(true,{cursor:'second',history:[null],reanchor:true});
    reply(s,i,page([asset('foreign',{workspace_id:'2'.repeat(32)})],{cursor:'foreign',workspace_id:'2'.repeat(32),collection_page:collection(stamp,{workspace_id:'2'.repeat(32)})}));
    assert.equal(await p,false);assert.equal(s.run('assetState.workspace_id'),scope);assert.equal(s.run('assetState.assets[0].id'),'a');
  });
  await test('A refused post-receipt reanchor retains the page and confirmed command state',async()=>{
    const s=init();await load(s,[asset('a')],{cursor:'second'},{cursor:'second',history:[null]});const r=s.reads.length,n=s.writes.length,p=s.run("mutateAssets({ids:['a'],action:'edit',favorite:true})");s.accept(n);await p;
    s.reads[r].reject(Object.assign(Error('Catalogue epoch changed; refresh explicitly'),{status:409,data:{code:'asset_cursor_stale'}}));if(s.reads[r+1]?.url.startsWith('/api/collections?'))s.reads[r+1].resolve(collection());await flush();
    assert.equal(s.reads.length,r+1,'do not silently fall back or walk pages after an explicit confirmed-write anchor');assert.equal(s.run('assetPaging.cursor'),'second');assert.equal(s.run("assetRecord('a').favorite"),true);assert.equal(s.run('assetLibraryPending'),null);assert.match(s.el('#assetMessage').textContent,/confirmed.*could not be refreshed/i);
  });
  await test('A held Library page cannot return through a Workspace ABA transition',async()=>{
    const s=init();await load(s);const r=s.reads.length,p=s.actualRefresh();s.run("assetState.workspace_id='2'.repeat(32);observeAssetWorkspaceIdentity();assetState.workspace_id='1'.repeat(32);observeAssetWorkspaceIdentity()");reply(s,r,page([asset('late')]));assert.equal(await p,false);assert.equal(s.run('assetState.assets[0].id'),'a');
  });
  await test('A held collection continuation cannot return through a Workspace ABA transition',async()=>{
    const s=init();await load(s,[asset('a')],{collection_page:collection(stamp,{next_cursor:'more'})});const i=s.reads.length,p=s.run('moreAssetCollections()');s.run("assetState.workspace_id='2'.repeat(32);observeAssetWorkspaceIdentity();assetState.workspace_id='1'.repeat(32);observeAssetWorkspaceIdentity()");s.reads[i].resolve(collection(stamp,{collections:[{id:'late',name:'Late',count:1}]}));assert.equal(await p,false);assert.equal(s.run('assetState.collections.length'),0);
  });
  await test('A confirmed receipt retires a held collection continuation before its counts can repaint',async()=>{
    const s=init();await load(s,[asset('a')],{collection_page:collection(stamp,{next_cursor:'more'})});const i=s.reads.length,p=s.run('moreAssetCollections()');s.run('assetReceiptEpoch++');s.reads[i].resolve(collection(stamp,{collections:[{id:'late',name:'Late',count:99}]}));assert.equal(await p,false);assert.equal(s.run('assetState.collections.length'),0);
  });
  await test('Same-run preview identifies loaded outputs and offers an explicit bounded read',async()=>{
    const s=init();await load(s,[asset('a')]);s.run("openAsset('a')");assert.equal(s.el('#assetSameRun').hidden,false);assert.match(s.el('#assetSameRun').innerHTML,/Loaded outputs/);assert.match(s.el('#assetSameRun').innerHTML,/Load run outputs/);assert.equal(s.reads.length,1);
  });
  await test('Same-run loading queries one exact job across sources and leaves the Library page alone',async()=>{
    const s=init();await load(s,[asset('a')]);s.run("openAsset('a')");const i=s.reads.length,p=s.run("loadAssetSiblings('load')");const q=query(s,i);assert.equal(q.get('job_id'),'run');assert.equal(q.get('workspace_id'),scope);assert.equal(q.get('limit'),'20');assert.equal(q.get('source'),'all');assert.equal(q.get('visibility'),'active');assert.equal(q.get('details'),'true');assert.equal(s.reads.length,i+1);
    reply(s,i,page([asset('a'),asset('older')],{next_cursor:'run-next'}));assert.equal(await p,true);assert.deepEqual(value(s,'assetState.assets.map(a=>a.id)'),['a']);assert.equal(s.run("assetRecord('older').id"),'older');assert.match(s.el('#assetSameRun').innerHTML,/2 available outputs on this page/);assert.match(s.el('#assetSameRun').innerHTML,/Next outputs/);assert.equal(s.writes.length,0);
    assert.equal(await s.run("openAsset('older')"),true);assert.equal(s.run('activeAsset.id'),'older');assert.equal(s.writes.length,0);
  });
  await test('Same-run continuation is explicit and a stale continuation keeps the shown siblings',async()=>{
    const s=init();await load(s);s.run("openAsset('a')");let i=s.reads.length,p=s.run("loadAssetSiblings('load')");reply(s,i,page([asset('a'),asset('sibling')],{next_cursor:'run-next'}));await p;
    i=s.reads.length;p=s.run("loadAssetSiblings('next')");assert.equal(query(s,i).get('cursor'),'run-next');assert.equal(query(s,i).has('reanchor'),false);assert.equal(s.reads.length,i+1);s.reads[i].reject(Object.assign(Error('Catalogue changed; reload run outputs'),{status:409,data:{code:'asset_cursor_stale'}}));assert.equal(await p,false);assert.match(s.el('#assetSameRun').innerHTML,/data-asset-open="sibling"/);assert.match(s.el('#assetSameRun').innerHTML,/Catalogue changed/);assert.equal(s.reads.length,i+1);
  });
  for(const change of ['editor','workspace','aba','receipt','catalogue'])await test('Held same-run replies cannot replace a newer '+change+' owner',async()=>{
    const s=init();await load(s,[asset('a'),asset('b',{job_id:'another'})]);s.run("openAsset('a')");const i=s.reads.length,p=s.run("loadAssetSiblings('load')");
    if(change==='editor')s.run("openAsset('b')");else if(change==='receipt')s.run('assetReceiptEpoch++');else if(change==='catalogue')s.run('assetPageEpoch++');else{s.run("assetState.workspace_id='2'.repeat(32);observeAssetWorkspaceIdentity()");if(change==='aba')s.run("assetState.workspace_id='1'.repeat(32);observeAssetWorkspaceIdentity()");}
    const before=s.el('#assetSameRun').innerHTML;reply(s,i,page([asset('late')]));assert.equal(await p,false);assert.equal(s.run("assetResolved.has('late')"),false);assert.doesNotMatch(s.el('#assetSameRun').innerHTML,/data-asset-open="late"/);if(change==='editor')assert.equal(s.el('#assetSameRun').innerHTML,before);
  });
  await test('A foreign same-run record refuses the whole observation without fabricated metadata',async()=>{
    const s=init();await load(s);s.run("openAsset('a')");const i=s.reads.length,p=s.run("loadAssetSiblings('load')");reply(s,i,page([asset('wrong',{job_id:'other'})]));assert.equal(await p,false);assert.equal(s.run("assetResolved.has('wrong')"),false);assert.match(s.el('#assetSameRun').innerHTML,/invalid/);
  });
  await test('Same-run unavailable details are explicit and never offer an editable partial record',async()=>{
    const s=init();await load(s);s.run("openAsset('a')");const i=s.reads.length,p=s.run("loadAssetSiblings('load')");reply(s,i,page([asset('a')],{unavailable_assets:[{id:'large',code:'asset_read_limit',error:'Too <large>'}],next_cursor:'next'}));assert.equal(await p,true);assert.match(s.el('#assetSameRun').innerHTML,/1 available of 2 observed outputs on this page/);assert.match(s.el('#assetSameRun').innerHTML,/Too &lt;large&gt;/);assert.doesNotMatch(s.el('#assetSameRun').innerHTML,/data-asset-open="large"/);assert.equal(s.run("assetRecord('large')"),undefined);
  });
  console.log(`Library page contracts: ${passed} passed, ${failed} failed`);if(failed)process.exitCode=1;
})();
