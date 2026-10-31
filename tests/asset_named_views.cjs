'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
function memory(){return {values:new Map(),getItem(k){if(this.failRead)throw Error('denied');return this.values.get(k)??null;},setItem(k,v){if(this.failWrite)throw Error('quota');this.values.set(k,String(v));},removeItem(k){this.values.delete(k);}};}
function start(local=memory(),session=memory()){
  const s=setup({autoOpen:false,localStorage:local,storage:session});
  for(const [id,value] of Object.entries({assetSort:'newest',assetType:'all',assetArchiveFilter:'active',assetGroup:'none'}))if(!s.el('#'+id).value)s.el('#'+id).value=value;
  s.run('assetState.assets.forEach(asset=>asset.collections=[]);renderAssets()');return Object.assign(s,{local,session});
}
function view(s,values){
  for(const [key,id] of Object.entries({sort:'assetSort',type:'assetType',search:'assetSearch',archive:'assetArchiveFilter'}))s.el('#'+id).value=values[key];
  s.run(`assetScope=${JSON.stringify(values.scope)};assetSourceMode=${JSON.stringify(values.source)};assetGroupMode=${JSON.stringify(values.group)};renderAssets()`);
}
const snapshot=s=>JSON.parse(s.run("JSON.stringify({scope:assetScope,sort:$('#assetSort').value,type:$('#assetType').value,search:$('#assetSearch').value,archive:assetArchiveChoice(),source:assetSourceChoice(),group:assetGroupMode})"));
const save=(s,name)=>{s.el('#assetNamedName').value=name;return s.el('#assetNamedSave').onclick();};
const restore=(s,name)=>{s.el('#assetNamedViews').value=name;return s.el('#assetNamedRestore').onclick();};
const forest={scope:'favorite',sort:'title',type:'image',search:'forest',archive:'active',source:'all',group:'day'};
const repairs={scope:'needs_work',sort:'oldest',type:'all',search:'dusk',archive:'all',source:'mine',group:'recipe'};

test('two named working sets survive reload and restore every filter without changing assets or selection',()=>{
  const s=start();view(s,forest);assert.equal(save(s,'Forest'),true);view(s,repairs);assert.equal(save(s,'Repairs'),true);
  const reloaded=start(s.local,s.session),before=reloaded.run('JSON.stringify(assetState)');reloaded.run("assetSelection=new Set(['a','b'])");
  assert.equal(restore(reloaded,'Forest'),true);assert.deepEqual(snapshot(reloaded),forest);
  assert.equal(restore(reloaded,'Repairs'),true);assert.deepEqual(snapshot(reloaded),repairs);
  assert.equal(reloaded.run('JSON.stringify(assetState)'),before);assert.equal(reloaded.run('JSON.stringify([...assetSelection])'),'["a","b"]');
  assert.equal(s.writes.length+reloaded.writes.length,0);
});

test('named views and drafts stay within the exact workspace',()=>{
  const s=start();view(s,forest);save(s,'First workspace');s.el('#assetNamedName').value='Unfinished name';
  s.run("assetState.workspace_id='2'.repeat(32);renderAssets()");
  assert.equal(s.el('#assetNamedName').value,'');assert.doesNotMatch(s.el('#assetNamedViews').innerHTML,/First workspace/);
  const before=snapshot(s);assert.equal(restore(s,'First workspace'),false);assert.deepEqual(snapshot(s),before);
  view(s,repairs);save(s,'Second workspace');s.run("assetState.workspace_id='1'.repeat(32);renderAssets()");
  assert.match(s.el('#assetNamedViews').innerHTML,/First workspace/);assert.doesNotMatch(s.el('#assetNamedViews').innerHTML,/Second workspace/);
  assert.equal(restore(s,'First workspace'),true);assert.deepEqual(snapshot(s),forest);
});

test('Private and All views use isolated tab storage and never enter Regular local storage',async()=>{
  const s=start();view(s,forest);save(s,'Regular forest');const regular=JSON.stringify([...s.local.values]);
  await s.dispatch('studio:privacy-change',{detail:{scope:'private'}});view(s,repairs);save(s,'Secret repair');
  assert.equal(JSON.stringify([...s.local.values]),regular);assert.doesNotMatch(s.el('#assetNamedViews').innerHTML,/Regular forest/);
  await s.dispatch('studio:privacy-change',{detail:{scope:'all'}});assert.doesNotMatch(s.el('#assetNamedViews').innerHTML,/Secret repair|Regular forest/);
  view(s,forest);save(s,'Mixed view');assert.equal(JSON.stringify([...s.local.values]),regular);
  const reload=start(s.local,s.session);await reload.dispatch('studio:privacy-change',{detail:{scope:'private'}});
  assert.match(reload.el('#assetNamedViews').innerHTML,/Secret repair/);assert.doesNotMatch(reload.el('#assetNamedViews').innerHTML,/Mixed view/);
  const anotherTab=start(s.local);await anotherTab.dispatch('studio:privacy-change',{detail:{scope:'private'}});
  assert.doesNotMatch(anotherTab.el('#assetNamedViews').innerHTML,/Secret repair|Mixed view/);
});

const savedKey=s=>[...s.local.values].find(([,value])=>{try{return Array.isArray(JSON.parse(value)?.views);}catch{return false;}})[0];

test('removing a named view keeps pictures, current filters, checkbox selection and other views',()=>{
  const s=start();view(s,forest);save(s,'Forest');view(s,repairs);save(s,'Repairs');
  s.run("assetSelection=new Set(['a'])");const before=snapshot(s),assets=s.run('JSON.stringify(assetState)');
  s.el('#assetNamedViews').value='Forest';assert.equal(s.el('#assetNamedRemove').onclick(),true);
  assert.deepEqual(snapshot(s),before);assert.equal(s.run('JSON.stringify(assetState)'),assets);assert.equal(s.run('JSON.stringify([...assetSelection])'),'["a"]');
  const reloaded=start(s.local,s.session);assert.doesNotMatch(reloaded.el('#assetNamedViews').innerHTML,/Forest/);assert.match(reloaded.el('#assetNamedViews').innerHTML,/Repairs/);assert.equal(s.writes.length,0);
});

test('names are escaped, duplicates preserve the old view, and the twenty-view limit is recoverable',()=>{
  const s=start();view(s,forest);const name='A <img src=x> "view"';assert.equal(save(s,name),true);
  assert.match(s.el('#assetNamedViews').innerHTML,/&lt;img/);assert.doesNotMatch(s.el('#assetNamedViews').innerHTML,/<img/);
  const key=savedKey(s),original=s.local.getItem(key);view(s,repairs);assert.equal(save(s,name),false);assert.equal(s.local.getItem(key),original);
  assert.equal(save(s,'x'.repeat(61)),false);assert.equal(save(s,'bad\nname'),false);
  for(let i=1;i<20;i++)assert.equal(save(s,'View '+i),true);
  assert.equal(save(s,'Overflow'),false);assert.equal(JSON.parse(s.local.getItem(key)).views.length,20);
  s.el('#assetNamedViews').value=name;assert.equal(s.el('#assetNamedRemove').onclick(),true);assert.equal(save(s,'Replacement'),true);
});

test('storage denial preserves the saved record and current filters on refused operations',()=>{
  const s=start();view(s,forest);save(s,'Forest');const key=savedKey(s),original=s.local.getItem(key);
  view(s,repairs);const before=snapshot(s);s.local.failWrite=true;
  assert.equal(save(s,'Repairs'),false);s.el('#assetNamedViews').value='Forest';assert.equal(s.el('#assetNamedRemove').onclick(),false);
  assert.equal(s.local.values.get(key),original);assert.deepEqual(snapshot(s),before);
  s.local.failWrite=false;s.local.failRead=true;assert.equal(restore(s,'Forest'),false);assert.deepEqual(snapshot(s),before);assert.equal(s.local.values.get(key),original);
  s.local.failRead=false;assert.equal(restore(s,'Forest'),true);assert.deepEqual(snapshot(s),forest);
});

test('corrupt, oversized, foreign and invalid stored records cannot overwrite or change the current view',()=>{
  const s=start();view(s,forest);save(s,'Forest');const key=savedKey(s),good=JSON.parse(s.local.getItem(key));view(s,repairs);const before=snapshot(s);
  const variants=['{',' '.repeat(32769),{...good,version:2},{...good,workspace_id:'2'.repeat(32)},{...good,privacy:'private'},
    {...good,views:'not a list'},{...good,views:[good.views[0],good.views[0]]},{...good,views:Array.from({length:21},(_,i)=>({...good.views[0],name:'View '+i}))},
    ...[{name:''},{name:'bad\nname'},{scope:'collection:../x'},{sort:'random'},{type:'unknown'},{archive:'private'},{source:'unknown'},{group:'unknown'},{search:'x'.repeat(201)}].map(bad=>({...good,views:[{...good.views[0],...bad}]}))];
  for(const variant of variants){const raw=typeof variant==='string'?variant:JSON.stringify(variant);s.local.values.set(key,raw);s.run('renderAssets()');
    assert.equal(restore(s,'Forest'),false);assert.equal(save(s,'New'),false);assert.deepEqual(snapshot(s),before);assert.equal(s.local.values.get(key),raw);}
});

test('a stale control cannot save into a new workspace and unavailable identity disables saved-view actions',()=>{
  const s=start();view(s,forest);save(s,'Forest');const original=JSON.stringify([...s.local.values]);
  s.run("assetState.workspace_id='2'.repeat(32)");assert.equal(save(s,'Stale name'),false);
  assert.equal(JSON.stringify([...s.local.values]),original);assert.equal(s.el('#assetNamedName').value,'');
  s.run("assetState.workspace_id=undefined;renderAssets()");assert.equal(s.el('#assetNamedSave').disabled,true);assert.equal(save(s,'Unknown workspace'),false);
  assert.equal(JSON.stringify([...s.local.values]),original);
});

test('an unavailable collection leaves its saved view and current filters intact',()=>{
  const s=start();s.run("assetState.collections=[{id:'c',name:'Collection',asset_ids:[]}]");view(s,{...forest,scope:'collection:c'});save(s,'Collection view');
  s.run('assetState.collections=[]');view(s,repairs);const before=snapshot(s),key=savedKey(s),original=s.local.getItem(key);
  assert.equal(restore(s,'Collection view'),false);assert.deepEqual(snapshot(s),before);assert.equal(s.local.getItem(key),original);assert.match(s.el('#assetNamedStatus').textContent,/collection is unavailable/i);
});

test('restoration sends one coherent page query through the existing read owner',()=>{
  const s=start();view(s,forest);save(s,'Forest');view(s,repairs);
  s.run("assetPaging={query:assetPageQuery()};globalThis.namedQueries=[];refreshAssets=async()=>{namedQueries.push(assetPageFilters());};assetSelection=new Set(['a'])");
  assert.equal(restore(s,'Forest'),true);
  assert.deepEqual(JSON.parse(s.run('JSON.stringify(namedQueries)')),[{visibility:'active',sort:'title',source:'all',q:'forest',favorite:true,media_type:'image'}]);
  assert.equal(s.run('JSON.stringify([...assetSelection])'),'["a"]');assert.equal(s.writes.length,0);
});

test('every action reads the latest store instead of overwriting another tabs completed save or removal',()=>{
  const s=start();view(s,forest);save(s,'Forest');const other=start(s.local);
  other.el('#assetNamedViews').value='Forest';assert.equal(other.el('#assetNamedRemove').onclick(),true);
  const before=snapshot(s);assert.equal(restore(s,'Forest'),false);assert.deepEqual(snapshot(s),before);
  assert.equal(save(s,'New'),true);view(other,repairs);assert.equal(save(other,'Other'),true);
  const final=start(s.local);assert.match(final.el('#assetNamedViews').innerHTML,/New/);assert.match(final.el('#assetNamedViews').innerHTML,/Other/);
});
