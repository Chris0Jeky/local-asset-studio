'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {setup}=require('./asset_detail_contracts.cjs');
const scope='1'.repeat(32),stamp={epoch:'a'.repeat(32),revision:1};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(options={}){
  const s=setup({autoOpen:false,...options});
  s.el('#assetType').value='all';s.el('#assetSort').value='newest';
  s.run('refreshAssets='+s.actualRefresh.toString());
  return s;
}
function asset(id,label=null){return {id,workspace_id:scope,title:id,filename:id+'.png',notes:'',tags:[],review:'unreviewed',favorite:false,
  media_type:'image',preset_id:'test',preset_name:'Test',job_id:id,metadata_revision:0,created_at:1,collections:[],source:{},lineage:[],bytes:1,run_label:label};}
function reply(s,index,assets,next=null){
  s.reads[index].resolve({workspace_id:scope,catalogue:stamp,assets,cursor:query(s,index).get('cursor'),next_cursor:next,unavailable_assets:[],collection_page:{workspace_id:scope,catalogue:stamp,collections:[],next_cursor:null}});
}
function query(s,index){return new URL(s.reads[index].url,'http://fixture').searchParams;}

test('first Library query filters Mine before paging and keeps the source control available',async()=>{
  const s=fixture(),pending=s.actualRefresh(true);
  assert.equal(query(s,0).get('source'),'mine');
  reply(s,0,[asset('mine'),asset('make','Make · Portrait')]);await pending;
  assert.equal(s.run('assetSource()'),'mine');
  assert.equal(s.el('#assetSource').hidden,false);
  assert.equal(s.el('#assetSource').value,'mine');
  assert.equal(s.run('visibleAssets().length'),2);
  assert.equal(s.writes.length,0);
});

test('a saved Agent preference stays explicit on an empty page and offers All sources',async()=>{
  const s=fixture({localStorage:{getItem:key=>key==='studio.assets.source'?'agent':null,setItem(){}}});
  const pending=s.actualRefresh(true);assert.equal(query(s,0).get('source'),'agent');
  reply(s,0,[]);await pending;
  assert.equal(s.run('assetSource()'),'agent');assert.equal(s.el('#assetSource').hidden,false);
  assert.match(s.el('#assetGrid').innerHTML,/No agent runs here/);
  assert.match(s.el('#assetGrid').innerHTML,/data-asset-source="all"/);
  assert.doesNotMatch(s.el('#assetGrid').innerHTML,/Your library is empty/);
  assert.equal(s.writes.length,0);
});

test('changing source from page two restarts its query and preserves the complete selection',async()=>{
  const s=fixture();let pending=s.actualRefresh(true);reply(s,0,[asset('mine-first')],'mine-next');await pending;
  s.run("assetSelection=new Set(['mine-first','off-page'])");
  pending=s.run('moveAssetPage(true)');assert.equal(query(s,1).get('cursor'),'mine-next');reply(s,1,[asset('mine-second')]);await pending;
  s.run("chooseAssetSource('agent')");assert.equal(s.reads.length,3);
  assert.equal(query(s,2).get('source'),'agent');assert.equal(query(s,2).has('cursor'),false);
  reply(s,2,[asset('agent-only','Agent lab')]);await tick();
  assert.equal(s.run('assetPaging.history.length'),0);
  assert.equal(s.run('JSON.stringify([...assetSelection])'),'["mine-first","off-page"]');
  assert.equal(s.el('#assetSource').value,'agent');assert.equal(s.writes.length,0);
});

test('a held source response cannot replace the newer All sources choice',async()=>{
  const s=fixture();let pending=s.actualRefresh(true);reply(s,0,[asset('mine')]);await pending;
  s.run("chooseAssetSource('agent');chooseAssetSource('all')");
  assert.equal(s.reads.length,2);
  reply(s,1,[asset('obsolete','Agent lab')]);await tick();
  assert.equal(s.reads.length,3);assert.equal(query(s,2).get('source'),'all');
  assert.equal(s.run("assetState.assets.some(a=>a.id==='obsolete')"),false);
  reply(s,2,[asset('mine'),asset('agent','Agent lab')]);await tick();
  assert.equal(s.run('assetSource()'),'all');assert.equal(s.run('visibleAssets().length'),2);
  assert.equal(s.writes.length,0);
});
