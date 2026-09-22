'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const {PREFIX}=require('../app/static/asset-recovery.js');
const fields=['id','workspace_id','metadata_revision','title','notes','tags','review','favorite','trashed_at'];
const metadata=s=>Object.fromEntries(fields.map(k=>[k,k==='trashed_at'?null:JSON.parse(s.run('JSON.stringify(activeAsset)'))[k]]));
function response(s){return {error:'Selected asset metadata changed; nothing changed',code:'asset_revision_conflict',workspace_id:s.payload(0).workspace_id,
  request_id:s.payload(0).request_id,conflict_ids:['a'],missing_ids:[],current:[{...metadata(s),metadata_revision:2,notes:'saved elsewhere'}]};}
const error=data=>Object.assign(Error('Synthetic conflict response'),{status:409,data});
function begin(s){s.el('#assetNotes').value='submitted';return s.el('#saveAssetDetails').onclick();}
const record=s=>JSON.parse(s.storage.getItem(PREFIX+'detail'));
const invalid={
  'different request':d=>{d.request_id='different_request_1';},
  'missing request identity':d=>{delete d.request_id;},
  'wrong Workspace':d=>{d.workspace_id='2'.repeat(32);},
  'absent conflict IDs':d=>{delete d.conflict_ids;},
  'wrong conflict target':d=>{d.conflict_ids=['b'];},
  'duplicate conflict IDs':d=>{d.conflict_ids=['a','a'];},
  'string conflict IDs':d=>{d.conflict_ids='a';},
  'absent missing IDs':d=>{delete d.missing_ids;},
  'null missing IDs':d=>{d.missing_ids=null;},
  'object missing IDs':d=>{d.missing_ids={};},
  'missing target':d=>{d.missing_ids=['a'];},
  'absent current snapshot':d=>{delete d.current;},
  'empty current snapshot':d=>{d.current=[];},
  'non-array current':d=>{d.current={};},
  'duplicate current row':d=>{d.current.push({...d.current[0]});},
  'unexpected current target':d=>{d.current.push({...d.current[0],id:'b',notes:'FOREIGN_SENTINEL'});},
  'foreign current Workspace':d=>{d.current[0].workspace_id='2'.repeat(32);d.current[0].notes='FOREIGN_SENTINEL';},
  'same revision':d=>{d.current[0].metadata_revision=0;},
  'negative revision':d=>{d.current[0].metadata_revision=-1;},
  'unsafe revision':d=>{d.current[0].metadata_revision=Number.MAX_SAFE_INTEGER+1;},
  'wrong notes type':d=>{d.current[0].notes={private:'not text'};},
  'oversized notes':d=>{d.current[0].notes='x'.repeat(8001);},
  'invalid review enum':d=>{d.current[0].review='approved';},
  'oversized title':d=>{d.current[0].title='x'.repeat(201);},
  'missing lifecycle':d=>{delete d.current[0].trashed_at;},
  'invalid lifecycle':d=>{d.current[0].trashed_at='yesterday';},
  'non-finite lifecycle':d=>{d.current[0].trashed_at=Infinity;},
  'oversized tag':d=>{d.current[0].tags=['x'.repeat(61)];},
  'too many tags':d=>{d.current[0].tags=Array(31).fill('tag');}
};
for(const [name,change] of Object.entries(invalid))test('unverified conflict retains exact recovery: '+name,async()=>{
  const s=setup(),sending=begin(s),data=response(s),body=s.writes[0].options.body;change(data);
  s.el('#assetNotes').value='newer typing';s.writes[0].reject(error(data));await sending;
  assert.equal(s.run('assetDetailPending?.body'),body,'must retain immutable pending command');
  assert.equal(s.run('assetDetailConflict'),null,'must not authorize conflict resolution');
  assert.equal(record(s).operation.body,body);assert.equal(record(s).draft.notes,'newer typing');
  assert.equal(s.el('#assetNotes').value,'newer typing');assert.equal(s.run('activeAsset.notes'),'original');
  assert.doesNotMatch(s.el('#assetDetailConflict').innerHTML,/FOREIGN_SENTINEL/);
  const next=setup({storage:s.storage});assert.equal(next.run('assetDetailPending.body'),body);assert.equal(next.writes.length,0);
});
test('GET error cannot discharge pending evidence even with a matching conflict envelope',async()=>{
  const s=setup(),sending=begin(s),data=response(s);s.writes[0].reject(Error('lost'));await sending;
  const inspecting=s.run('checkAssetSave()');s.reads[0].reject(error(data));await inspecting;
  assert.equal(s.run('assetDetailPending?.body'),s.writes[0].options.body);assert.equal(s.run('assetDetailConflict'),null);assert.equal(s.writes.length,1);
});
test('valid POST conflict permits explicit comparison then a fresh reviewed command',async()=>{
  const s=setup(),sending=begin(s),data=response(s);data.current[0].title='界'.repeat(200);data.current[0].notes='😀'.repeat(8000);
  // Extra media/source fields are observations, not metadata admitted into recovery.
  data.current[0].source={private_path:'/not-retained'};
  s.writes[0].reject(error(data));await sending;assert.equal(s.run('assetDetailPending'),null);
  assert.equal(s.el('#saveAssetDetails').disabled,true);assert.equal(record(s).conflict.current[0].source,undefined);
  s.run('resolveAssetConflict(true)');assert.equal(s.writes.length,1);assert.equal(s.el('#assetNotes').value,'submitted');
  const newer=s.el('#saveAssetDetails').onclick();assert.notEqual(s.payload(1).request_id,s.payload(0).request_id);assert.deepEqual(s.payload(1).expected_revisions,{a:2});
  s.accept(1);await newer;assert.equal(s.run('assetDetailPending'),null);
});
