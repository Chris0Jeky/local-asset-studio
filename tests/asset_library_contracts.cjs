// Exercise the shipped library projection and selection policy; no inference or storage writes.
'use strict';
const assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
function library(count=3){
  const s=setup({autoOpen:false});
  s.el('#assetType').value='all';s.el('#assetSort').value='newest';
  s.run(`assetState.assets=Array.from({length:${count}},(_,i)=>({id:'a'+i,workspace_id:assetState.workspace_id,title:'Asset '+i,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:i,url:'/fixture.png',collections:[],metadata_revision:0,source:{},lineage:[],bytes:1}));renderAssets();`);
  return s;
}
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log('PASS',name);}catch(e){failed++;console.error('FAIL',name,'\n',e.message);}}
(async()=>{
  await test('Hidden selection is counted without silently changing its IDs',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1']);");s.el('#assetSearch').value='Asset 0';s.run('renderAssets()');
    assert.match(s.el('#assetSelectionSummary').textContent,/1 visible.*1 outside/i);assert.equal(s.run('assetSelection.size'),2);
  });
  await test('A filter miss in populated Trash is not an empty Trash claim',()=>{
    const s=library();s.run("assetState.assets[0].trashed_at=10;assetScope='trash';");s.el('#assetSearch').value='nothing matches';s.run('renderAssets()');
    assert.match(s.el('#assetGrid').innerHTML,/No matching assets/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/Trash is empty/);
  });
  await test('Empty Favorites explains the scope and offers All assets',()=>{
    const s=library();s.run("setAssetScope('favorite')");assert.match(s.el('#assetGrid').innerHTML,/No favorites yet/);assert.match(s.el('#assetGrid').innerHTML,/data-scope="all"/);
  });
  await test('An empty collection is distinct from an unavailable collection',()=>{
    const s=library();s.run("assetState.collections=[{id:'empty',name:'Empty project',count:0}];setAssetScope('collection:empty')");
    assert.match(s.el('#assetGrid').innerHTML,/This collection has no assets/);s.run("assetState.collections=[];renderAssets()");assert.match(s.el('#assetGrid').innerHTML,/Collection unavailable/);
  });
  await test('The visible selection limit is disclosed before and after selecting',()=>{
    const s=library(205);assert.match(s.el('#selectVisible').textContent,/200.*205/);s.el('#selectVisible').onclick();assert.equal(s.run('assetSelection.size'),200);assert.match(s.el('#assetMessage').textContent,/200.*205/);
  });
  await test('Filtered counts distinguish matches from total in scope',()=>{
    const s=library();s.el('#assetSearch').value='Asset 0';s.run('renderAssets()');assert.match(s.el('#assetVisibleCount').textContent,/1 of 3/);
  });
  await test('Filter reset preserves sort, selection, editor and pending-command bytes',()=>{
    const s=library();s.run("assetSelection=new Set(['a0']);openAsset('a0');assetLibraryPending={body:'exact original bytes'};");s.el('#assetNotes').value='my unsaved notes';s.el('#assetType').value='video';s.el('#assetSearch').value='nope';s.el('#assetSort').value='title';
    assert.equal(typeof s.el('#clearAssetFilters').onclick,'function');s.el('#clearAssetFilters').onclick();assert.equal(s.el('#assetSearch').value,'');assert.equal(s.el('#assetType').value,'all');assert.equal(s.el('#assetSort').value,'title');assert.equal(s.run('assetSelection.size'),1);assert.equal(s.el('#assetNotes').value,'my unsaved notes');assert.equal(s.run('assetLibraryPending.body'),'exact original bytes');assert.equal(s.writes.length,0);
  });
  await test('Selection review labels unavailable and trashed records and escapes titles',()=>{
    const s=library();s.run(`assetState.assets[0].title='<img src=x onerror=alert(1)>';assetState.assets[0].trashed_at=10;assetSelection=new Set(['a0','gone']);renderAssets();`);
    assert.match(s.el('#assetSelectedList').innerHTML,/In Trash/);assert.match(s.el('#assetSelectedList').innerHTML,/Unavailable/);assert.match(s.el('#assetSelectedList').innerHTML,/&lt;img/);assert.doesNotMatch(s.el('#assetSelectedList').innerHTML,/<img/);
  });
  await test('Keeping only visible IDs never rewrites an unconfirmed command',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1','gone']);assetLibraryPending={body:'do not replace',selection:['a0','a1']};");s.el('#assetSearch').value='Asset 0';
    assert.equal(typeof s.el('#keepVisibleSelection').onclick,'function');s.el('#keepVisibleSelection').onclick();assert.equal(s.run("JSON.stringify([...assetSelection])"),'["a0"]');assert.equal(s.run('assetLibraryPending.body'),'do not replace');assert.equal(s.run('assetLibraryPending.selection.length'),2);assert.equal(s.writes.length,0);
  });
  await test('Hidden selection requires consent; visible-only action does not',()=>{
    const s=library();s.run("assetSelection=new Set(['a0','a1']);");s.el('#assetSearch').value='Asset 0';assert.equal(s.run('typeof assetSelectionCanProceed'),'function');
    assert.equal(s.run("assetSelectionCanProceed('trash')"),false);assert.equal(s.confirmations(),1);s.approve(true);assert.equal(s.run("assetSelectionCanProceed('trash')"),true);s.el('#assetSearch').value='';assert.equal(s.run("assetSelectionCanProceed('trash')"),true);assert.equal(s.confirmations(),2);
  });
  await test('Unavailable and oversized selections are refused without losing IDs',()=>{
    const s=library(201);assert.equal(s.run('typeof assetSelectionCanProceed'),'function');s.run("assetSelection=new Set(['gone'])");assert.equal(s.run("assetSelectionCanProceed('export')"),false);assert.equal(s.run('assetSelection.size'),1);
    s.run('assetSelection=new Set(assetState.assets.map(a=>a.id))');assert.equal(s.run("assetSelectionCanProceed('favorite')"),false);assert.equal(s.run('assetSelection.size'),201);assert.equal(s.confirmations(),0);
  });
  await test('Keeper review scope is not confused with checkbox selection',()=>{
    const s=library();s.run("assetSelection.add('a0');setAssetScope('selected')");assert.equal(s.el('#assetScopeTitle').textContent,'Keepers');assert.match(s.el('#assetGrid').innerHTML,/No keepers yet/);assert.equal(s.run('assetSelection.size'),0);
  });
  await test('All assets empty because every original is in Trash offers recovery',()=>{
    const s=library();s.run('for(const asset of assetState.assets)asset.trashed_at=10;renderAssets();');assert.match(s.el('#assetGrid').innerHTML,/Your assets are in Trash/);assert.match(s.el('#assetGrid').innerHTML,/data-scope="trash"/);assert.doesNotMatch(s.el('#assetGrid').innerHTML,/library is empty/);
  });
  await test('Awaiting review has its own scope count and empty-state explanation',()=>{
    const s=library();s.run("assetState.assets[0].review='selected';setAssetScope('unreviewed')");s.el('#assetSearch').value='no match';s.run('renderAssets()');assert.match(s.el('#assetVisibleCount').textContent,/0 of 2/);s.run("for(const a of assetState.assets)a.review='selected';renderAssets()");assert.match(s.el('#assetGrid').innerHTML,/No assets awaiting review/);
  });
  const sourced=(options={})=>{
    const s=setup({autoOpen:false,...options});s.el('#assetType').value='all';s.el('#assetSort').value='newest';
    s.run(`assetState.assets=[['m0',null,1],['m1',null,2],['g0','lab p71 · G16',3],['g1','lab p71 · G16',4]].map(([id,label,at])=>({id,workspace_id:assetState.workspace_id,title:'Anima · 1',preset_name:'Anima',output_index:0,prompt_excerpt:'prompt of '+id,run_label:label,notes:'',tags:[],review:'unreviewed',favorite:false,media_type:'image',created_at:at,url:'/fixture.png',collections:[],metadata_revision:0,source:{},lineage:[],bytes:1,filename:'f.png',sha256:'a'}));renderAssets();`);
    return s;
  };
  const shown=s=>JSON.parse(s.run('JSON.stringify(visibleAssets().map(a=>a.id))'));
  const memory=()=>({values:new Map(),getItem(key){return this.values.get(key)??null;},setItem(key,value){this.values.set(key,String(value));}});
  await test('Without labelled assets every source is shown and the source filter stays hidden',()=>{
    const s=library();assert.equal(s.run('assetSource()'),'all');assert.equal(s.el('#assetSource').hidden,true);assert.equal(s.run('visibleAssets().length'),3);assert.doesNotMatch(s.el('#assetVisibleCount').textContent,/hidden/);
  });
  await test('Labelled assets default the library and Review next to Mine',()=>{
    const s=sourced();assert.equal(s.el('#assetSource').hidden,false);assert.equal(s.el('#assetSource').value,'mine');assert.deepEqual(shown(s),['m1','m0']);
    assert.match(s.el('#assetVisibleCount').textContent,/^2 assets · 2 agent runs hidden$/);assert.match(s.el('#reviewNext').textContent,/2 unreviewed/);
    s.run('startReviewQueue()');assert.equal(s.run('JSON.stringify(assetQueue.ids)'),'["m1","m0"]');
  });
  await test('The source choice persists like grouping and survives a missing store',()=>{
    const store=memory();let s=sourced({localStorage:store});s.el('#assetSource').value='agent';s.el('#assetSource').onchange();
    assert.deepEqual(shown(s),['g1','g0']);assert.equal(store.values.get('studio.assets.source'),'agent');assert.match(s.el('#assetVisibleCount').textContent,/2 of yours hidden/);
    s=sourced({localStorage:store});assert.equal(s.run('assetSource()'),'agent');assert.deepEqual(shown(s),['g1','g0']);
    s.run("chooseAssetSource('all')");assert.equal(shown(s).length,4);assert.equal(store.values.get('studio.assets.source'),'all');
    s.el('#assetSearch').value='p71';s.run('renderAssets()');assert.deepEqual(shown(s),['g1','g0']);
    s=sourced();s.run("chooseAssetSource('agent')");assert.deepEqual(shown(s),['g1','g0']);
  });
  await test('A source filter that hides the whole view offers every source in one click',()=>{
    const s=sourced();s.run('assetState.assets=assetState.assets.filter(a=>a.run_label);renderAssets()');
    assert.match(s.el('#assetGrid').innerHTML,/None of your own runs here/);assert.match(s.el('#assetGrid').innerHTML,/data-asset-source="all"/);
    s.run("chooseAssetSource('all')");assert.deepEqual(shown(s),['g1','g0']);
  });
  await test('Default titles carry the prompt excerpt; renamed titles and markup do not leak',()=>{
    const s=sourced();s.run("chooseAssetSource('all')");let html=s.el('#assetGrid').innerHTML;
    assert.match(html,/class="asset-card-prompt"[^>]*>prompt of m0</);assert.match(html,/class="asset-run-label"[^>]*>lab p71 · G16</);
    s.run("assetState.assets[0].title='My knight';assetState.assets[1].prompt_excerpt='<b>x</b>';assetState.assets[2].run_label='<i>';renderAssets()");html=s.el('#assetGrid').innerHTML;
    assert.doesNotMatch(html,/prompt of m0/);assert.match(html,/&lt;b&gt;x&lt;\/b&gt;/);assert.doesNotMatch(html,/<b>x|<i>/);
  });
  await test('The review dialog shows the prompt text and run label',()=>{
    const s=sourced();s.run("chooseAssetSource('all');openAsset('g0')");const html=s.el('#assetDetails').innerHTML;
    assert.match(html,/Prompt text: prompt of g0/);assert.match(html,/Run label: lab p71 · G16/);
    s.run("openAsset('m0')");assert.doesNotMatch(s.el('#assetDetails').innerHTML,/Run label/);
  });
  console.log(`Asset library contracts: ${passed} passed, ${failed} failed`);if(failed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
