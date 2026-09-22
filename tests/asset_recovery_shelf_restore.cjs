'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {setup}=require('./asset_detail_contracts.cjs');
const Core=require('../app/static/asset-recovery-shelf.js');
const Session=require('../app/static/asset-recovery-shelf-session.js');
const Journal=require('../app/static/asset-recovery.js');
const crypto=require('node:crypto').webcrypto;
const key=Journal.PREFIX+'detail';
const typing=(s,value)=>{s.el('#assetNotes').value=value;s.el('#assetNotes').emit('input');};
async function roundTrip(first){
  const payload=JSON.parse(first.storage.getItem(key));
  const sealed=await Core.seal('detail',payload,{id:'f'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);
  const [imported]=await Core.decode(await Core.encode([sealed],crypto),crypto);
  const before=Core.canonical(imported),target=setup({autoOpen:false});
  const session=Session.create({journal:Journal.create(target.storage),store:null,crypto});
  session.restore(imported,payload.workspace_id);
  assert.equal(Core.canonical(imported),before,'restoration must not mutate the stored record');
  return setup({storage:target.storage});
}
async function lose(s){const save=s.el('#saveAssetDetails').onclick();s.writes[0].reject(Error('lost reply'));await save;}

test('returning an imported draft to its baseline is clean and needs no discard confirmation',async()=>{
  const first=setup();typing(first,'unsaved');const next=await roundTrip(first);
  typing(next,'original');assert.equal(next.run('assetDetailDirty()'),false);
  assert.equal(next.storage.getItem(key),null);next.el('#closeAssetDialog').onclick();
  assert.equal(next.confirmations(),0);assert.equal(next.writes.length,0);
});
test('an unchanged imported pending snapshot normalizes after GET-only confirmation and clears the tab journal',async()=>{
  const first=setup();typing(first,'  normalized  ');await lose(first);
  const body=first.writes[0].options.body,next=await roundTrip(first);
  assert.equal(next.run('assetDetailPending.body'),body);
  const pending=next.run('checkAssetSave()');next.reads[0].resolve(first.receipt(0));await pending;
  assert.equal(next.writes.length,0);assert.equal(next.el('#assetNotes').value,'normalized');
  assert.equal(next.run('assetDetailDirty()'),false);assert.equal(next.storage.getItem(key),null);
});
for(const newer of ['newer local typing','snapshot '])test('imported confirmation preserves a genuinely newer draft: '+JSON.stringify(newer),async()=>{
  const first=setup();typing(first,'snapshot');await lose(first);typing(first,newer);
  const next=await roundTrip(first),body=next.run('assetDetailPending.body');
  const pending=next.run('checkAssetSave()');next.reads[0].resolve(first.receipt(0));await pending;
  assert.equal(next.writes.length,0);assert.equal(next.el('#assetNotes').value,newer);
  assert.equal(next.run('assetDetailDirty()'),true);assert.equal(next.run('activeAsset.notes'),'snapshot');
  assert.equal(body,first.writes[0].options.body);assert.equal(JSON.parse(next.storage.getItem(key)).operation,null);
});
test('an unchanged imported Trash snapshot closes only after its historical receipt is confirmed',async()=>{
  const first=setup();const save=first.el('#assetTrash').onclick();first.writes[0].reject(Error('lost reply'));await save;
  const next=await roundTrip(first),pending=next.run('checkAssetSave()');
  next.reads[0].resolve(first.receipt(0));await pending;
  assert.equal(next.writes.length,0);assert.equal(next.el('#assetDialog').open,false);
  assert.equal(next.storage.getItem(key),null);assert.equal(next.run('activeAsset.trashed_at'),123);
});
