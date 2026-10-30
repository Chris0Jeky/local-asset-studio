'use strict';
// #1678 second slice: the Library's read-only preview of POST /api/assets/migration-plan (actual workspace.js, inert DOM, controllable I/O).
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs');
const {setup}=require('./asset_detail_contracts.cjs');
const PLAN='/api/assets/migration-plan',HASH='0123456789abcdef'.repeat(4);
function configured(privacies=['regular','regular'],view='all'){
  const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';s.el('#assetArchiveFilter').value='active';
  s.run(`assetActivePrivacy=${JSON.stringify(view)};assetState.assets[0].privacy=${JSON.stringify(privacies[0])};assetState.assets[1].privacy=${JSON.stringify(privacies[1])};`);
  s.focused=[];for(const id of ['#closeMigration','#migrationSwitch','#previewMigration','#assetMigrate'])s.el(id).focus=()=>s.focused.push(id);
  s.run('window.switched=[];window.StudioPrivacy={setScope(v){window.switched.push(v);}};');s.switched=()=>JSON.parse(s.run('JSON.stringify(window.switched)'));
  return s;
}
const select=(s,ids)=>{s.run(`assetSelection=new Set(${JSON.stringify(ids)});renderAssetSelection();`);};
const plan=(over={})=>({workspace_id:'1'.repeat(32),scope:'all',destination:'private',asset_ids:['a','b'],job_ids:[],
  items:[{kind:'run',id:'job-a',bytes:10},{kind:'run_file',id:'job-a/recipe.json',bytes:5},{kind:'run_file',id:'job-a/state.json',bytes:5},
    {kind:'asset',id:'a',bytes:1048576},{kind:'asset',id:'b',bytes:2097152},{kind:'thumbnail',id:'t',bytes:2048},
    {kind:'lineage_child',id:'c'},{kind:'receipt',id:'asset_commands/r1'},
    {kind:'external_copy',id:'comfyui/output/a.png',bytes:3145728}],
  item_count:9,blockers:[],applicable:true,byte_estimate:3147776,remaining_copies:'ComfyUI history and backups may keep further copies.',plan_sha256:HASH,apply_available:false,writes:false,...over});

test('The action appears only for a homogeneous selection and names the opposite classification',()=>{
  let s=configured();assert.equal(s.el('#previewMigration').hidden,undefined);
  select(s,['a','b']);assert.equal(s.el('#previewMigration').hidden,false);assert.equal(s.el('#previewMigration').textContent,'Preview move to Private…');
  select(s,[]);assert.equal(s.el('#previewMigration').hidden,true);
  s=configured(['private','private']);select(s,['a','b']);assert.equal(s.el('#previewMigration').hidden,false);assert.equal(s.el('#previewMigration').textContent,'Preview move to Regular…');
  s=configured(['regular','private']);select(s,['a','b']);assert.equal(s.el('#previewMigration').hidden,true,'mixed selections get no action');
  select(s,['b']);assert.equal(s.el('#previewMigration').hidden,false);
  select(s,['a','missing']);assert.equal(s.el('#previewMigration').hidden,true,'an unresolved ID has no known classification');
});
test('Preview sends one read-only planner request under the All header and renders counts, bytes, external copies and the short hash',async()=>{
  const s=configured();select(s,['a','b']);const done=s.el('#previewMigration').onclick();
  assert.equal(s.writes.length,1);assert.equal(s.reads.length,0);
  const w=s.writes[0];assert.equal(w.url,PLAN);assert.equal(w.options.method,'POST');
  assert.equal(w.options.headers['X-Studio-Privacy'],'all');
  assert.deepEqual(JSON.parse(w.options.body),{workspace_id:'1'.repeat(32),destination:'private',asset_ids:['a','b']});
  assert.equal(s.el('#migrationDialog').open,true);assert.equal(s.el('#migrationTitle').textContent,'Preview move to Private');
  assert.match(s.el('#migrationStatus').textContent,/Preparing the preview.*Nothing is changed/);assert.deepEqual(s.focused,['#closeMigration']);
  w.resolve(plan());await done;
  const html=s.el('#migrationBody').innerHTML;
  assert.match(html,/<li>1 run<\/li>/);assert.match(html,/<li>2 run files<\/li>/);assert.match(html,/<li>2 outputs<\/li>/);assert.match(html,/<li>1 thumbnail<\/li>/);
  assert.match(html,/1 related item that stays where it is/);assert.match(html,/1 past receipt that stays/);
  assert.match(html,/About 3\.0 MiB/);assert.match(html,/1 ComfyUI copy was found and would stay in place/);assert.match(html,/comfyui\/output\/a\.png<\/code> · 3\.0 MiB/);
  assert.match(html,/ComfyUI history and backups may keep further copies\./);assert.match(html,/No blockers/);
  assert.match(html,/<code>0123456789ab<\/code>/);assert.doesNotMatch(html,new RegExp(HASH));
  assert.match(s.el('#migrationStatus').textContent,/Preview ready: 9 items, no blockers\. Nothing was changed\./);
  assert.equal(s.writes.length,1,'no other POST is ever made');
});
test('Every blocker code is explained in one sentence and server text is escaped',async()=>{
  const codes=['missing_run','run_storage_alias','unsupported_operation','run_not_settled','already_in_destination','missing_run_record','run_too_large','missing_sibling','missing_reference','privacy_mismatch','missing_snapshot','snapshot_changed','collection_mixed','receipts_overflow','scope_partial'];
  const s=configured();select(s,['a']);const done=s.el('#previewMigration').onclick();
  const hostile='<img src=x onerror=alert(1)>';
  s.writes[0].resolve(plan({asset_ids:['a'],blockers:[...codes.map(code=>({code,message:'server words '+code})),{code:'brand_new_code',message:'x'},{code:'run_not_settled',run_id:hostile}],
    items:[{kind:'external_copy',id:'comfyui/<script>alert(2)</script>.png',bytes:1},{kind:'mystery',id:'q'}],remaining_copies:'<b>kept</b>'}));await done;
  const html=s.el('#migrationBody').innerHTML;
  assert.match(html,/Blockers \(17\)/);
  for(const code of codes)assert.doesNotMatch(html,new RegExp('server words '+code),'the mapped sentence, not the server message, is shown');
  assert.match(html,/queued, running, partial or uncertain/);assert.match(html,/already in the destination/);assert.match(html,/Something blocks this move \(brand_new_code\)/);
  assert.equal((html.match(/<li>/g)||[]).length,19,'one count line, one external copy and 17 blockers');
  assert.doesNotMatch(html,/<img|<script|<b>kept/);assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);assert.match(html,/&lt;script&gt;/);assert.match(html,/1 other item/);
});
test('A refusal, a narrower or different answer, and a lost response are text, never a preview',async()=>{
  for(const [answer,pattern] of [[Error('Unknown job'),/^No preview: Unknown job Nothing was changed\.$/],
    [plan({scope:'private'}),/did not cover both privacy views/],[plan({destination:'regular'}),/different move/],[plan({asset_ids:['a']}),/different move/],
    [plan({plan_sha256:'abc'}),/incomplete/],[{error:'x'},/not understood/],[Error(''),/the request failed/]]){
    const s=configured();select(s,['a','b']);const done=s.el('#previewMigration').onclick();
    if(answer instanceof Error)s.writes[0].reject(answer);else s.writes[0].resolve(answer);await done;
    assert.equal(s.el('#migrationBody').innerHTML,'');assert.match(s.el('#migrationStatus').textContent,pattern);assert.equal(s.writes.length,1);
  }
});
test('Outside the All view the preview asks to switch, requests nothing and never switches by itself',async()=>{
  for(const view of ['regular','private']){
    const s=configured([view==='private'?'private':'regular','regular'],view);select(s,['a']);
    await s.el('#previewMigration').onclick();
    assert.equal(s.writes.length+s.reads.length,0);assert.equal(s.run('assetActivePrivacy'),view);assert.deepEqual(s.switched(),[]);
    assert.match(s.el('#migrationStatus').textContent,/needs the All view.*Nothing was requested/);assert.equal(s.el('#migrationSwitch').hidden,false);assert.equal(s.focused.at(-1),'#migrationSwitch');
    s.el('#migrationSwitch').onclick();assert.deepEqual(s.switched(),['all']);assert.equal(s.el('#migrationDialog').open,false);assert.equal(s.writes.length,0);
  }
});
test('The open asset gets the same preview from the detail dialog',async()=>{
  const s=configured(['private','regular']);s.run("openAsset('a')");
  assert.equal(s.el('#assetMigrate').hidden,false);assert.equal(s.el('#assetMigrate').textContent,'Preview move to Regular…');
  const done=s.el('#assetMigrate').onclick();assert.equal(s.writes.length,1);
  assert.deepEqual(JSON.parse(s.writes[0].options.body),{workspace_id:'1'.repeat(32),destination:'regular',asset_ids:['a']});assert.equal(s.writes[0].options.headers['X-Studio-Privacy'],'all');
  s.writes[0].resolve(plan({destination:'regular',asset_ids:['a']}));await done;assert.match(s.el('#migrationBody').innerHTML,/No blockers/);
});
test('Closing returns focus to the opener, ignores a late answer and a reopened preview starts clean',async()=>{
  const s=configured();select(s,['a','b']);const first=s.el('#previewMigration').onclick();
  s.el('#closeMigration').onclick();assert.equal(s.el('#migrationDialog').open,false);assert.equal(s.focused.at(-1),'#previewMigration');
  s.writes[0].resolve(plan());await first;assert.equal(s.el('#migrationBody').innerHTML,'','a late answer cannot repaint a closed dialog');
  const second=s.el('#previewMigration').onclick();assert.equal(s.writes.length,2);assert.equal(s.el('#migrationBody').innerHTML,'');
  s.run('assetPrivacyEpoch++');s.writes[1].resolve(plan());await second;assert.equal(s.el('#migrationBody').innerHTML,'','a privacy change makes the answer stale');
});
test('Markup is a native, labelled dialog with a live status, the not-available line and no apply control',()=>{
  const html=fs.readFileSync('app/static/index.html','utf8'),dialog=html.match(/<dialog id="migrationDialog"[\s\S]*?<\/dialog>/)[0];
  assert.match(dialog,/aria-labelledby="migrationTitle"/);assert.match(dialog,/id="migrationStatus" role="status" aria-live="polite"/);
  assert.match(dialog,/Moving is not available yet; this preview changes nothing\./);
  assert.deepEqual([...dialog.matchAll(/<button[^>]*id="(\w+)"/g)].map(m=>m[1]),['migrationSwitch','closeMigration']);
  assert.doesNotMatch(dialog,/apply|move now|confirm/i);assert.match(html,/id="previewMigration" hidden/);assert.match(html,/id="assetMigrate" hidden/);
  const s=configured();assert.equal(s.el('#migrationDialog').events.cancel,undefined,'Escape keeps the native close');
});
