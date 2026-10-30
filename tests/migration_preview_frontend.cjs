'use strict';
// #1678 second and fourth slices: the Library's preview of POST /api/assets/migration-plan and its Move to Private control for POST /api/assets/migration-apply (actual workspace.js, inert DOM, controllable I/O).
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs');
const {setup}=require('./asset_detail_contracts.cjs');
const PLAN='/api/assets/migration-plan',APPLY='/api/assets/migration-apply',HASH='0123456789abcdef'.repeat(4);
function configured(privacies=['regular','regular'],view='all'){
  const s=setup({autoOpen:false});s.el('#assetType').value='all';s.el('#assetSort').value='newest';s.el('#assetArchiveFilter').value='active';
  s.run(`assetActivePrivacy=${JSON.stringify(view)};assetState.assets[0].privacy=${JSON.stringify(privacies[0])};assetState.assets[1].privacy=${JSON.stringify(privacies[1])};`);
  s.focused=[];for(const id of ['#closeMigration','#migrationSwitch','#migrationApply','#migrationRecheck','#migrationRepreview','#previewMigration','#assetMigrate'])s.el(id).focus=()=>s.focused.push(id);
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
  s=configured(['regular','private']);select(s,['a','b']);assert.equal(s.el('#previewMigration').hidden,false,'a mixed selection keeps the action visible, disabled');assert.equal(s.el('#previewMigration').disabled,true);
  select(s,['b']);assert.equal(s.el('#previewMigration').hidden,false);assert.equal(s.el('#previewMigration').disabled,false);
});
const REASON='#previewMigrationReason',MIXED='Select only Regular or only Private items to preview a move.',LOAD='Load the off-page items first.';
test('A selection that cannot be previewed shows the action disabled with one visible reason and sends nothing',async()=>{
  let s=configured(['regular','private']);select(s,['a','b']);
  assert.equal(s.el('#previewMigration').hidden,false);assert.equal(s.el('#previewMigration').disabled,true);assert.equal(s.el(REASON).hidden,false);assert.equal(s.el(REASON).textContent,MIXED);
  await s.el('#previewMigration').onclick();assert.equal(s.writes.length+s.reads.length,0,'no request while unavailable');assert.equal(s.el('#migrationDialog').open,false);
  select(s,['a','missing']);
  assert.equal(s.el('#previewMigration').hidden,false);assert.equal(s.el('#previewMigration').disabled,true);assert.equal(s.el(REASON).textContent,LOAD,'an unresolved ID has no known classification');
  await s.el('#previewMigration').onclick();assert.equal(s.writes.length+s.reads.length,0);
  select(s,['b']);assert.equal(s.el('#previewMigration').disabled,false);assert.equal(s.el(REASON).hidden,true);assert.equal(s.el(REASON).textContent,'','the reason clears once the selection is homogeneous');
  select(s,[]);assert.equal(s.el('#previewMigration').hidden,true);assert.equal(s.el(REASON).hidden,true);
  s=configured();select(s,['a','b']);assert.equal(s.el('#previewMigration').disabled,false);assert.equal(s.el(REASON).hidden,true);assert.equal(s.el(REASON).textContent,'');
});
test('A Regular or Private view never says "mixed": an unresolved ID gets the neutral wording',()=>{
  for(const view of ['regular','private']){
    const s=configured([view,view],view);select(s,['a','missing']);
    assert.equal(s.el('#previewMigration').disabled,true);assert.equal(s.el(REASON).textContent,LOAD);assert.doesNotMatch(s.el(REASON).textContent,/mixed|Private|Regular/i);
    select(s,['a','b']);assert.equal(s.el('#previewMigration').disabled,false);assert.equal(s.el(REASON).hidden,true);
    s.run(`assetState.assets[1].privacy=${JSON.stringify(view==='regular'?'private':'regular')};renderAssetSelection();`);
    assert.doesNotMatch(s.el(REASON).textContent,/Select only|mixed/i,'the view alone never explains a hidden classification');
  }
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
test('Review shortcuts are inert while the preview is open over the details dialog, and work again once it closes',async()=>{
  const s=configured();s.run(fs.readFileSync('app/static/review-checks.js','utf8'));s.run("assetQueue={ids:['a','b'],index:0};openAsset('a')");
  const key=(k,extra={})=>s.dispatch('keydown',{key:k,target:{tagName:'BUTTON'},preventDefault(){this.prevented=true;},...extra});
  const done=s.el('#assetMigrate').onclick();assert.equal(s.writes.length,1);assert.equal(s.el('#assetDialog').open,true);assert.equal(s.el('#migrationDialog').open,true);
  const tags=s.el('#assetTags').value;
  for(const k of ['k','w','x','K','s','ArrowRight','ArrowLeft','1','2','3','4','5']){const event={key:k,target:{tagName:'BUTTON'},preventDefault(){this.prevented=true;}};await s.dispatch('keydown',event);assert.notEqual(event.prevented,true,k+' must not be claimed by the dialog underneath');}
  assert.equal(s.writes.length,1,'only the planner request exists: no /api/assets/update from a shortcut');assert.equal(s.run('assetQueue.index'),0);assert.equal(s.run('activeAsset.id'),'a');assert.equal(s.el('#assetTags').value,tags);assert.equal(s.run('assetDetailDirty()'),false);
  s.writes[0].resolve(plan({asset_ids:['a'],destination:'private'}));await done;
  s.el('#closeMigration').onclick();await key('k');
  assert.equal(s.writes.length,2,'the same key acts again on the details dialog once the preview is closed');assert.match(s.writes[1].url,/^\/api\/assets/);
});
test('Switching to All leaves focus on the search box, not on a hidden opener',()=>{
  const s=configured(['regular','regular'],'regular');s.el('#assetSearch').focus=()=>s.focused.push('#assetSearch');select(s,['a']);
  s.el('#previewMigration').onclick();s.focused.length=0;s.el('#migrationSwitch').onclick();
  assert.equal(s.focused.at(-1),'#assetSearch');
});
test('Closing returns focus to the opener, ignores a late answer and a reopened preview starts clean',async()=>{
  const s=configured();select(s,['a','b']);const first=s.el('#previewMigration').onclick();
  s.el('#closeMigration').onclick();assert.equal(s.el('#migrationDialog').open,false);assert.equal(s.focused.at(-1),'#previewMigration');
  s.writes[0].resolve(plan());await first;assert.equal(s.el('#migrationBody').innerHTML,'','a late answer cannot repaint a closed dialog');
  const second=s.el('#previewMigration').onclick();assert.equal(s.writes.length,2);assert.equal(s.el('#migrationBody').innerHTML,'');
  s.run('assetPrivacyEpoch++');s.writes[1].resolve(plan());await second;assert.equal(s.el('#migrationBody').innerHTML,'','a privacy change makes the answer stale');
});
test('Markup is a native, labelled dialog with a live status and every move control hidden until the script shows it',()=>{
  const html=fs.readFileSync('app/static/index.html','utf8'),dialog=html.match(/<dialog id="migrationDialog"[\s\S]*?<\/dialog>/)[0];
  assert.match(dialog,/aria-labelledby="migrationTitle"/);assert.match(dialog,/id="migrationStatus" role="status" aria-live="polite"/);
  assert.match(dialog,/id="migrationNote"><b>This preview changes nothing\.<\/b>/);assert.doesNotMatch(dialog,/not available yet/);
  assert.deepEqual([...dialog.matchAll(/<button[^>]*id="(\w+)"([^>]*)>/g)].map(m=>[m[1],/ hidden/.test(m[2])]),[['migrationApply',true],['migrationRecheck',true],['migrationRepreview',true],['migrationSwitch',true],['closeMigration',false]]);
  assert.match(html,/id="previewMigration" hidden/);assert.match(html,/id="assetMigrate" hidden/);assert.match(html,/<small id="previewMigrationReason" role="status" aria-live="polite" hidden><\/small>/);
  const s=configured(),event={preventDefault(){this.prevented=true;}};s.el('#migrationDialog').emit('cancel',event);assert.notEqual(event.prevented,true,'with no move in flight Escape keeps the native close');
});

// ---- Apply (Move to Private): the fourth #1678 slice ----
const ready=(over={})=>plan({apply_available:true,...over});
const fail=(code,status=409,extra={})=>Object.assign(Error('server words '+code),{status,data:{code,error:'server words '+code,...extra}});
const receipt=(id,over={})=>({request_id:id,plan_sha256:HASH,destination:'private',stage:'complete',published:true,job_ids:['job-a'],asset_ids:['a','b'],collection_ids:[],cleanup_remaining:[],external_copies:[],...over});
const tick=()=>new Promise(r=>setImmediate(r));
async function previewed(over,privacies,view){
  const s=configured(privacies,view);select(s,['a','b']);s.run("globalThis.refreshed=0;refreshAssets=async()=>{globalThis.refreshed++;return true;}");
  const done=s.el('#previewMigration').onclick();s.writes[0].resolve(ready(over));await done;return s;
}
test('The Move button shows only for a clean, applicable, current Regular-to-Private preview and carries the run count',async()=>{
  let s=await previewed({items:[...plan().items,{kind:'run',id:'job-b'},{kind:'run',id:'job-c'}]});
  assert.equal(s.el('#migrationApply').hidden,false);assert.equal(s.el('#migrationApply').textContent,'Move 3 runs to Private');
  assert.match(s.el('#migrationNote').innerHTML,/cannot be moved back yet/);
  s=await previewed();assert.equal(s.el('#migrationApply').textContent,'Move 1 run to Private');
  s=await previewed({blockers:[{code:'run_not_settled',run_id:'job-a'}]});assert.equal(s.el('#migrationApply').hidden,true,'a blocker hides it');
  s=await previewed({apply_available:false});assert.equal(s.el('#migrationApply').hidden,true,'the server says apply is unavailable');
  s=await previewed({items:[{kind:'asset',id:'a'}]});assert.equal(s.el('#migrationApply').hidden,true,'no run, nothing to move');
  s=configured(['private','private']);select(s,['a','b']);let done=s.el('#previewMigration').onclick();
  s.writes[0].resolve(ready({destination:'regular'}));await done;
  assert.equal(s.el('#migrationApply').hidden,true,'Private to Regular stays preview-only');assert.match(s.el('#migrationNote').innerHTML,/Moving back to Regular is not available yet; this preview changes nothing\./);
  s=configured();select(s,['a','b']);done=s.el('#previewMigration').onclick();s.run('assetPrivacyEpoch++');s.writes[0].resolve(ready());await done;
  assert.equal(s.el('#migrationApply').hidden,true,'a stale privacy epoch never shows it');
  s=await previewed();s.run('migrationEpoch++');s.el('#migrationApply').onclick();await tick();
  assert.equal(s.writes.length,1,'a stale preview epoch sends nothing');assert.match(s.el('#migrationStatus').textContent,/out of date\. Nothing was sent/);assert.equal(s.el('#migrationApply').hidden,true);assert.equal(s.el('#migrationRepreview').hidden,false);
  s=await previewed();s.run('assetWorkspaceEpoch++');s.el('#migrationApply').onclick();await tick();assert.equal(s.writes.length,1,'a changed Workspace epoch sends nothing');
  s=await previewed();s.run("assetState.workspace_id='2'.repeat(32)");s.el('#migrationApply').onclick();await tick();assert.equal(s.writes.length,1,'a different Workspace sends nothing');
});
test('One click sends one apply request with the plan hash, a fresh request ID and the All header; the dialog holds until it answers',async()=>{
  const s=await previewed();s.el('#assetSearch').focus=()=>s.focused.push('#assetSearch');const done=s.el('#migrationApply').onclick();
  assert.equal(s.writes.length,2);const w=s.writes[1];assert.equal(w.url,APPLY);assert.equal(w.options.method,'POST');assert.equal(w.options.headers['X-Studio-Privacy'],'all');
  const body=JSON.parse(w.options.body);assert.deepEqual(Object.keys(body).sort(),['asset_ids','destination','plan_sha256','request_id','workspace_id']);
  assert.deepEqual({...body,request_id:0},{workspace_id:'1'.repeat(32),destination:'private',asset_ids:['a','b'],plan_sha256:HASH,request_id:0});assert.match(body.request_id,/^[A-Za-z0-9_-]{16,128}$/);
  assert.equal(s.el('#migrationApply').disabled,true);assert.equal(s.el('#closeMigration').disabled,true);assert.match(s.el('#migrationStatus').textContent,/Moving 1 run to Private.*closing it would hide the result/);
  s.el('#migrationApply').onclick();s.el('#migrationApply').onclick();assert.equal(s.writes.length,2,'no double submit while in flight');
  s.el('#closeMigration').onclick();assert.equal(s.el('#migrationDialog').open,true,'Close is held while the move runs');
  const cancel={preventDefault(){this.prevented=true;}};s.el('#migrationDialog').emit('cancel',cancel);assert.equal(cancel.prevented,true,'Escape is cancelled');
  s.el('#migrationDialog').close();assert.equal(s.el('#migrationDialog').open,true,'a close that slips past cancel reopens the modal');
  assert.equal(s.focused.includes('#previewMigration'),false,'no opener focus while the move runs');
  w.resolve(receipt(body.request_id));await done;
  assert.match(s.el('#migrationStatus').textContent,/^Moved 1 run \(2 outputs\) to Private\.$/);assert.equal(s.el('#migrationTitle').textContent,'Moved to Private');
  assert.equal(s.el('#migrationApply').hidden,true);assert.equal(s.el('#migrationApply').disabled,false);assert.equal(s.el('#closeMigration').disabled,false);assert.equal(s.focused.at(-1),'#closeMigration');
  assert.equal(s.run('globalThis.refreshed'),1,'the Library is refreshed once');assert.equal(s.run('assetSelection.size'),0);assert.equal(s.writes.length,2);
  assert.equal(s.el('#migrationDialog').open,true);s.el('#closeMigration').onclick();assert.equal(s.el('#migrationDialog').open,false);assert.equal(s.focused.at(-1),'#assetSearch','the hidden opener hands focus to the search box');
});
test('Leftover Regular copies are reported with the success, and an open asset detail learns it is Private',async()=>{
  const s=configured(['regular','regular']);s.run("globalThis.refreshed=0;refreshAssets=async()=>{globalThis.refreshed++;return true;}");s.run("openAsset('a')");
  const pre=s.el('#assetMigrate').onclick();s.writes[0].resolve(ready({asset_ids:['a']}));await pre;
  const done=s.el('#migrationApply').onclick();assert.deepEqual(JSON.parse(s.writes[1].options.body).asset_ids,['a']);
  s.writes[1].resolve(receipt(JSON.parse(s.writes[1].options.body).request_id,{asset_ids:['a'],cleanup_remaining:['x','y']}));await done;
  assert.match(s.el('#migrationStatus').textContent,/Moved 1 run \(1 output\) to Private\. 2 leftover copies in Regular could not be deleted yet/);
  assert.equal(s.run('activeAsset.privacy'),'private');assert.equal(s.el('#assetMigrate').textContent,'Preview move to Regular…');
});
test('Each refusal code is one plain sentence, hides Apply, offers only what is safe, and never sends a second request by itself',async()=>{
  const cases=[['migration_blocked',/^This move is blocked now, so nothing was moved\. Preview again to see why\.$/,'preview'],
    ['migration_stale',/^Something changed since the preview, so nothing was moved\. Preview again\.$/,'preview'],
    ['migration_busy',/^Another move is running, possibly this one\. Wait a moment, then press Check again\.$/,'check'],
    ['migration_request_conflict',/names a different move.*Preview again/,'preview'],
    ['migration_recovery_pending',/earlier move did not finish.*Restart the Studio/,''],
    ['migration_destination_occupied',/same ID already exists.*Private view/,''],
    ['migration_scope_required',/needs the All view/,''],
    ['migration_direction_unsupported',/back to Regular is not built yet/,''],
    ['migration_in_progress',/has not finished.*nothing is retried automatically/,''],
    ['migration_storage_full',/disk is full/,'preview'],['migration_verify_failed',/did not match its original/,'preview'],['migration_failed',/failed before anything was published/,'preview']];
  for(const [code,pattern,offer] of cases){
    const s=await previewed();const done=s.el('#migrationApply').onclick();s.writes[1].reject(fail(code,code==='migration_failed'?500:409,{blockers:[{code:'run_not_settled',run_id:'job-a'}]}));await done;await tick();
    const text=s.el('#migrationStatus').textContent;assert.match(text,pattern,code);assert.doesNotMatch(text,/server words/,'the mapped sentence, not the server text');
    assert.equal(s.el('#migrationApply').hidden,true,code);assert.equal(s.el('#migrationRecheck').hidden,offer!=='check',code);assert.equal(s.el('#migrationRepreview').hidden,offer!=='preview',code);
    assert.equal(s.el('#migrationApply').disabled,false);assert.equal(s.el('#closeMigration').disabled,false);assert.equal(s.writes.length,2,code+': no automatic second request');assert.equal(s.run('globalThis.refreshed'),0,'a refusal changes nothing, so nothing is refreshed');
    if(code==='migration_blocked')assert.match(s.el('#migrationBody').innerHTML,/queued, running, partial or uncertain/,'the fresh blockers are listed in plain words');
  }
});
test('After migration_stale, Preview again asks the planner afresh and the next Move click uses a new request ID',async()=>{
  const s=await previewed();let done=s.el('#migrationApply').onclick();const first=JSON.parse(s.writes[1].options.body);s.writes[1].reject(fail('migration_stale'));await done;
  done=s.el('#migrationRepreview').onclick();assert.equal(s.writes.length,3);assert.equal(s.writes[2].url,PLAN);assert.deepEqual(JSON.parse(s.writes[2].options.body),{workspace_id:'1'.repeat(32),destination:'private',asset_ids:['a','b']});
  assert.equal(s.el('#migrationRepreview').hidden,true);assert.equal(s.el('#migrationApply').hidden,true);
  s.writes[2].resolve(ready({plan_sha256:'f'.repeat(64)}));await done;assert.equal(s.el('#migrationApply').hidden,false);
  done=s.el('#migrationApply').onclick();const second=JSON.parse(s.writes[3].options.body);
  assert.equal(second.plan_sha256,'f'.repeat(64));assert.notEqual(second.request_id,first.request_id);s.writes[3].resolve(receipt(second.request_id));await done;assert.match(s.el('#migrationStatus').textContent,/^Moved/);
});
test('A lost answer is uncertain: no automatic retry, and Check again re-sends the SAME body and request ID until the server answers',async()=>{
  for(const lost of [Error('NetworkError when attempting to fetch'),Object.assign(Error('boom'),{status:500,data:{error:'boom'}}),'garbled',{published:false,request_id:'x'}]){
    const s=await previewed();let done=s.el('#migrationApply').onclick();const sent=s.writes[1].options.body,id=JSON.parse(sent).request_id;
    if(lost instanceof Error)s.writes[1].reject(lost);else s.writes[1].resolve(lost);await done;await tick();
    assert.match(s.el('#migrationStatus').textContent,/^The move may or may not have happened/);assert.match(s.el('#migrationStatus').textContent,/same move; the server never moves it twice\. Do not start a new move first, and reload the Library/);
    assert.equal(s.writes.length,2,'no automatic retry');assert.equal(s.el('#migrationApply').hidden,true,'no fresh Apply');assert.equal(s.el('#migrationRecheck').hidden,false);assert.equal(s.focused.at(-1),'#migrationRecheck');assert.equal(s.run('globalThis.refreshed'),0);
    done=s.el('#migrationRecheck').onclick();assert.equal(s.writes.length,3);assert.equal(s.writes[2].url,APPLY);assert.equal(s.writes[2].options.body,sent,'identical body');assert.equal(JSON.parse(s.writes[2].options.body).request_id,id);assert.equal(s.writes[2].options.headers['X-Studio-Privacy'],'all');
    assert.equal(s.el('#migrationRecheck').disabled,true);
    s.writes[2].reject(fail('migration_busy'));await done;await tick();assert.match(s.el('#migrationStatus').textContent,/Wait a moment, then press Check again/);assert.equal(s.writes.length,3);assert.equal(s.el('#migrationRecheck').hidden,false);
    done=s.el('#migrationRecheck').onclick();assert.equal(s.writes[3].options.body,sent,'busy keeps the same identity');
    s.writes[3].resolve(receipt(id,{stage:'cleanup-needed',cleanup_remaining:['one']}));await done;
    assert.match(s.el('#migrationStatus').textContent,/^Moved 1 run \(2 outputs\) to Private\. 1 leftover copy/);assert.equal(s.el('#migrationRecheck').hidden,true);assert.equal(s.writes.length,4);assert.equal(s.run('globalThis.refreshed'),1);
  }
});
test('An unknown outcome survives Close: previewing again offers only Check again with the same request ID until the server answers',async()=>{
  const s=await previewed();let done=s.el('#migrationApply').onclick();const sent=s.writes[1].options.body;s.writes[1].reject(Error('network'));await done;await tick();
  s.el('#migrationDialog').close();assert.equal(s.el('#migrationDialog').open,false);
  s.el('#previewMigration').onclick();await tick();
  assert.equal(s.writes.length,2,'no planner request and no new move while the outcome is unknown');assert.equal(s.el('#migrationDialog').open,true);
  assert.equal(s.el('#migrationTitle').textContent,'Earlier move: outcome unknown');assert.equal(s.el('#migrationApply').hidden,true);assert.equal(s.el('#migrationRecheck').hidden,false);assert.equal(s.focused.at(-1),'#migrationRecheck');
  done=s.el('#migrationRecheck').onclick();assert.equal(s.writes[2].url,APPLY);assert.equal(s.writes[2].options.body,sent,'the same body and request ID');
  s.writes[2].resolve(receipt(JSON.parse(sent).request_id));await done;assert.match(s.el('#migrationStatus').textContent,/^Moved 1 run/);
  s.el('#migrationDialog').close();select(s,['a','b']);s.el('#previewMigration').onclick();assert.equal(s.writes[3].url,PLAN,'a settled outcome lets a fresh preview start');
});
test('A definitive refusal on Check again settles the unknown outcome, mapped or not, so previews are never locked',async()=>{
  for(const [answer,text] of [[fail('migration_interrupted',500),/^The move was interrupted and rolled back/],[fail('not_found',404),/^The move did not go through \(server words not_found\)\. Preview again/]]){
    const s=await previewed();let done=s.el('#migrationApply').onclick();s.writes[1].reject(Error('network'));await done;await tick();
    s.el('#migrationDialog').close();s.el('#previewMigration').onclick();await tick();assert.equal(s.writes.length,2);
    done=s.el('#migrationRecheck').onclick();s.writes[2].reject(answer);await done;await tick();
    assert.match(s.el('#migrationStatus').textContent,text);assert.equal(s.el('#migrationRecheck').hidden,true);assert.equal(s.el('#migrationRepreview').hidden,false);
    s.el('#migrationDialog').close();select(s,['a','b']);s.el('#previewMigration').onclick();assert.equal(s.writes.length,4);assert.equal(s.writes[3].url,PLAN,'a fresh preview starts after a definitive answer');
  }
});
test('A receipt for another request, a non-private destination or an unfinished stage is never reported as a move',async()=>{
  for(const odd of [r=>({...r,request_id:'someone-elses-request-0001'}),r=>({...r,destination:'regular'}),r=>({...r,published:null}),r=>({...r,job_ids:undefined})]){
    const s=await previewed();const done=s.el('#migrationApply').onclick();s.writes[1].resolve(odd(receipt(JSON.parse(s.writes[1].options.body).request_id)));await done;
    assert.match(s.el('#migrationStatus').textContent,/may or may not have happened/);assert.equal(s.el('#migrationRecheck').hidden,false);assert.equal(s.run('globalThis.refreshed'),0);
  }
});
test('A move that outlives a privacy change still reports through the Library message and never repaints another preview',async()=>{
  const s=await previewed();const done=s.el('#migrationApply').onclick();const id=JSON.parse(s.writes[1].options.body).request_id;
  s.run('assetPrivacyEpoch++');s.el('#migrationDialog').close();assert.equal(s.el('#migrationDialog').open,false,'a scope change may close the dialog even mid-move');
  s.el('#previewMigration').onclick();assert.equal(s.writes.length,2,'no second planner request while the move runs');assert.match(s.el('#assetMessage').textContent,/A move is still running/);
  s.writes[1].resolve(receipt(id));await done;
  assert.match(s.el('#assetMessage').textContent,/^Moved 1 run \(2 outputs\) to Private\.$/);assert.equal(s.el('#migrationTitle').textContent,'Preview move to Private','the closed dialog is not repainted');assert.equal(s.run('globalThis.refreshed'),1);
  const lost=await previewed();const d2=lost.el('#migrationApply').onclick();lost.run('assetPrivacyEpoch++');lost.el('#migrationDialog').close();lost.writes[1].reject(Error('network'));await d2;
  assert.match(lost.el('#assetMessage').textContent,/may or may not have happened/);assert.equal(lost.writes.length,2);
});
test('Library shortcuts stay inert for the whole life of the Move dialog, including while a move is in flight',async()=>{
  const s=configured();s.run(fs.readFileSync('app/static/review-checks.js','utf8'));s.run("assetQueue={ids:['a','b'],index:0};openAsset('a')");
  const pre=s.el('#assetMigrate').onclick();s.writes[0].resolve(ready({asset_ids:['a']}));await pre;
  const done=s.el('#migrationApply').onclick();assert.equal(s.writes.length,2);
  for(const k of ['k','w','x','s','ArrowRight','1','5']){const event={key:k,target:{tagName:'BUTTON'},preventDefault(){this.prevented=true;}};await s.dispatch('keydown',event);assert.notEqual(event.prevented,true,k);}
  assert.equal(s.writes.length,2,'no metadata write from a shortcut');s.writes[1].resolve(receipt(JSON.parse(s.writes[1].options.body).request_id,{asset_ids:['a']}));await done;
  const event={key:'k',target:{tagName:'BUTTON'},preventDefault(){this.prevented=true;}};await s.dispatch('keydown',event);assert.equal(s.writes.length,2,'still inert after the move while the dialog is open');
});
// ---- #1797 polish ----
test('With the dialog gone, an uncertain or busy answer says to preview again; with it open the Check again text is unchanged',async()=>{
  const gone=async answer=>{const s=await previewed();const done=s.el('#migrationApply').onclick();s.run('assetPrivacyEpoch++');s.el('#migrationDialog').close();s.writes[1].reject(answer);await done;return s;};
  let s=await gone(Error('network'));let text=s.el('#assetMessage').textContent;
  assert.match(text,/^The move may or may not have happened \(network\)\. Preview the move again to check this same move; the server never moves it twice\./);assert.doesNotMatch(text,/Check again/,'no pointer at a dialog that is not open');
  s.el('#previewMigration').onclick();await tick();assert.equal(s.el('#migrationDialog').open,true,'previewing again does reopen the Check again state the text promises');
  assert.equal(s.el('#migrationTitle').textContent,'Earlier move: outcome unknown');assert.equal(s.el('#migrationRecheck').hidden,false);assert.equal(s.writes.length,2);
  s=await gone(fail('migration_busy'));text=s.el('#assetMessage').textContent;assert.match(text,/^Another move is running, possibly this one\. Wait a moment, then preview the move again to check it\.$/);
  s=await previewed();const done=s.el('#migrationApply').onclick();s.writes[1].reject(Error('network'));await done;
  assert.match(s.el('#migrationStatus').textContent,/^The move may or may not have happened \(network\)\. Press Check again to ask about this same move; the server never moves it twice\./,'in-dialog text unchanged');
});
test('A hung apply is aborted after a generous timeout and treated as an unknown outcome, never a failure',async()=>{
  const s=await previewed();assert.ok(s.run('migrationApplyTimeoutMs')>=300000,'big runs copy many bytes: the limit must be generous');
  const done=s.el('#migrationApply').onclick();const w=s.writes[1],sent=w.options.body,id=JSON.parse(sent).request_id;
  assert.equal(w.options.signal.aborted,false);assert.equal(s.timers.size,1,'one timer guards the apply');assert.equal(s.el('#closeMigration').disabled,true);
  [...s.timers.values()][0]();await done;await tick();
  assert.equal(w.options.signal.aborted,true);assert.equal(s.timers.size,0);
  assert.match(s.el('#migrationStatus').textContent,/^The move may or may not have happened \(no answer within 10 minutes\)\. Press Check again to ask about this same move/);
  assert.equal(s.el('#migrationRecheck').hidden,false);assert.equal(s.el('#migrationApply').hidden,true);assert.equal(s.el('#migrationRepreview').hidden,true,'no fresh Move offer');
  assert.equal(s.el('#closeMigration').disabled,false,'the modal is released');assert.equal(s.el('#migrationApply').disabled,false);assert.equal(s.run('globalThis.refreshed'),0);assert.equal(s.writes.length,2,'no automatic retry');
  const again=s.el('#migrationRecheck').onclick();assert.equal(s.writes[2].url,APPLY);assert.equal(s.writes[2].options.body,sent,'the same body and request ID');assert.equal(JSON.parse(s.writes[2].options.body).request_id,id);
  s.writes[2].resolve(receipt(id));await again;assert.match(s.el('#migrationStatus').textContent,/^Moved 1 run/);assert.equal(s.timers.size,0,'a settled apply leaves no timer');
});
