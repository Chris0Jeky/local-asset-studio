// #1766: Make's picture picker reads /api/assets/page a page at a time (limit <= 60) instead of the whole Workspace list.
// Runs the picker's own source in vm with synthetic replies; nothing is submitted.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {test}=require('node:test');
const make=fs.readFileSync(path.join(__dirname,'../app/static/make.js'),'utf8'),workspace=fs.readFileSync(path.join(__dirname,'../app/static/workspace.js'),'utf8');
const between=(start,end)=>{assert.ok(make.includes(start)&&make.includes(end),start);return make.slice(make.indexOf(start),make.indexOf(end,make.indexOf(start)));};
const flowCode=[between('  const LINEUP_MAX','  // One-time migration'),between('  async function chooseCharacter(','  const chosenCharacter='),between('  const fillsKey','  function rememberFills'),between('  async function redoRun(','  async function goalGenerate')].join('\n');
const pageCode=[between('  // state.pictures lists','  // Round 5'),between('  const picture=o=>','\n'),between('  // The picker reads /api/assets/page','  async function fillPictures'),between('  function renderGrid(','  function figureSvg')].join('\n');

const same=(a,b,m)=>assert.deepEqual(JSON.parse(JSON.stringify(a)),b,m);   // vm values come from another realm
const asset=(i,extra={})=>({id:'a'+i,title:'Picture '+i,filename:'p'+i+'.png',media_type:'image',created_at:1000-i,tags:[],...extra});
// A fake server over the images: newest first, the filters Make sends, cursors that are offsets.
function setup({total=150,assets}={}){
  const selections=[],said=[],all=assets||Array.from({length:total},(_,i)=>asset(i)),requests=[],epoch={n:0},nodes={};
  const node=id=>nodes[id]||(nodes[id]={innerHTML:'',setAttribute(){}});
  const context={window:{},readScope:()=>'regular',agentRun:a=>typeof a.run_label==='string'&&a.run_label!==''&&!a.run_label.startsWith('Make · '),
    assetReadURL:vm.runInNewContext(workspace.match(/function assetReadURL.*\n/)[0]+';assetReadURL'),pictureLabel:a=>a.title||'Picture',pictureMeta:()=>'',thumbUrl:a=>'/thumb/'+a.id,escape:v=>String(v??''),
    q:s=>s.startsWith('#')?node(s.slice(1)):s.startsWith('[data-make-all')?node('all'):null,hold:null,selections,said,
    classified:v=>v?.privacy==='private'?'private':'regular',requestPrivacy:(scope,privacy='regular')=>({scope,privacy}),say:text=>said.push(text),
    usePrivacy:()=>true,runPrivacy:r=>r.privacy||'regular',GOALS:[{id:'edit',intent:'edit'}],POLISH:{},PE:()=>null,remember(){},render(){},
    makeStorage:{getItem:()=>null},fillsKey:id=>'k'+id,usableCharacters:()=>context.characters||[],lookPictures:()=>[],goal:()=>({intent:'edit'}),
    view:{querySelectorAll:()=>context.boxes||[]}};
  context.state={grids:{},library:null,found:{},agentsAny:null,queries:{},allPictures:false,pick:null,pose:null,form:{},review:{}};
  context.selectionReply=body=>({items:body.ids.map(id=>({id,state:'missing',asset:null}))});
  context.json=async(url,body,captured)=>{
    if(url==='/api/assets/selection'){selections.push({body,scope:captured.scope});return context.selectionReply(body);}
    const u=new URL(url,'http://x'),p=Object.fromEntries(u.searchParams);requests.push({path:u.pathname,...p});
    assert.equal(u.pathname,'/api/assets/page','the picker never reads the whole Workspace');assert.ok(Number(p.limit)>=1&&Number(p.limit)<=60,'limit '+p.limit);
    if(context.stale&&p.cursor){const code=context.stale;context.stale=null;throw Object.assign(Error('Asset catalogue changed'),{status:409,code});}
    const rows=all.filter(a=>a.media_type===p.media_type&&!a.trashed_at&&(p.source!=='mine'||!context.agentRun(a))&&(p.source!=='agent'||context.agentRun(a))&&(!p.q||JSON.stringify(a).toLowerCase().includes(p.q)));
    const from=p.cursor?Number(p.cursor):0,page=rows.slice(from,from+Number(p.limit));
    if(context.hold)await context.hold;
    return{workspace_id:'w'.repeat(32),assets:page,next_cursor:from+page.length<rows.length?String(from+page.length):null};};
  Object.defineProperty(context,'privacyEpoch',{get:()=>epoch.n});
  vm.createContext(context);vm.runInContext(pageCode,context);
  vm.runInContext(flowCode,context);
  const run=name=>vm.runInContext(name,context);
  return{context,requests,epoch,all,node,selections,said,run,state:context.state,load:(id,more)=>run('loadPictures')(id,more),draw:()=>run('renderGrid')('makePictures','data-make-pick')};
}

test('the first page asks for at most 60 of my newest images and Show more appends the next page',async()=>{
  const t=setup(),g=await t.load('makePictures');
  same({...t.requests.find(r=>r.source==='mine')},{path:'/api/assets/page',media_type:'image',visibility:'active',limit:'60',source:'mine',details:'true',archive:'all'});
  assert.equal(g.items.length,60);assert.equal(g.next,'60');assert.equal(t.state.pictures.length,60);
  const more=await t.load('makePictures',true);
  assert.equal(t.requests.at(-1).cursor,'60');assert.equal(t.requests.at(-1).source,'mine');assert.equal(more.items.length,120);
  same(more.items.map(a=>a.id),t.all.slice(0,120).map(a=>a.id),'pages join in order with no repeats');
  assert.equal((await t.load('makePictures',true)).items.length,150);assert.equal(t.state.grids.makePictures.next,null);
  const reads=t.requests.length;await t.load('makePictures',true);assert.equal(t.requests.length,reads,'no read once the list ends');
});

test('Show all drops the mine filter, a search sends its longest word, masks never reach the grid',async()=>{
  const t=setup({assets:[asset(0,{filename:'face_mask_00001_.png'}),asset(1,{run_label:'Lab 1016c',title:'lantern wide'}),asset(2,{title:'lantern small'}),asset(3)]});
  let g=await t.load('makePictures');same(g.items.map(a=>a.id),['a2','a3'],'agent run hidden, mask removed');assert.equal(t.state.agentsAny,true,'one probe says Show all has something to add');
  t.state.allPictures=true;g=await t.load('makePictures');assert.equal(t.requests.at(-1).source,undefined);same(g.items.map(a=>a.id),['a1','a2','a3']);
  t.state.queries.makePictures='a  lantern';t.state.allPictures=false;g=await t.load('makePictures');assert.equal(t.requests.find(r=>r.q).q,'lantern');same(g.items.map(a=>a.id),['a2']);
  const reads=t.requests.length;await t.load('makePictures');assert.equal(t.requests.length,reads,'the same query is served from the loaded page');
});

test('a stale or invalid cursor restarts from the first page and never mixes lists',async()=>{
  for(const code of ['asset_cursor_stale','asset_cursor_mismatch','asset_cursor_invalid']){
    const t=setup();await t.load('makePictures');t.context.stale=code;
    const g=await t.load('makePictures',true);
    same(t.requests.slice(-2).map(r=>r.cursor),['60',null],'the refused cursor read is followed by a first-page read');
    same(g.items.map(a=>a.id),t.all.slice(0,60).map(a=>a.id),code);assert.equal(g.restarted,true);assert.equal(g.next,'60');
  }
  const t=setup();await t.load('makePictures');t.context.json=async()=>{throw Object.assign(Error('Library metadata is unavailable'),{status:503,code:'asset_read_unavailable'});};
  await assert.rejects(t.load('makePictures',true),/unavailable/);assert.equal(t.state.grids.makePictures.items.length,60,'any other refusal keeps what was loaded');
});

test('a privacy switch or a reset while a page loads discards the result',async()=>{
  for(const drop of [t=>{t.epoch.n++;},t=>{t.state.pictures=null;}]){
    const t=setup();let release;t.context.hold=new Promise(r=>{release=r;});
    const pending=t.load('makePictures');drop(t);release();await pending;
    assert.equal(t.state.grids.makePictures,undefined,'nothing from before the switch is kept');assert.equal(t.state.pictures,null);
  }
  const t=setup();await t.load('makePictures');t.state.pictures=null;
  same([t.state.grids,t.state.library,t.state.agentsAny],[{},null,null],'null clears every cache');
});

test('the chosen picture stays in the grid when it is not on a loaded page',async()=>{
  const t=setup();await t.load('makePictures');
  const cards=()=>[...t.node('makePictures').innerHTML.matchAll(/data-make-pick="([^"]+)"/g)].map(m=>m[1]);
  t.state.pick=asset(149);t.draw();
  assert.equal(cards()[0],'a149');assert.equal(cards().length,61);assert.match(t.node('makePictures').innerHTML,/data-make-more="makePictures"/);
  t.state.pick=asset(3);t.draw();assert.equal(cards().length,60,'on the page already: not repeated');
  t.state.pick=asset(149);t.state.queries.makePictures='picture';t.draw();assert.equal(cards().includes('a149'),false,'a search shows only matches');
});

// ---- fix round for the review of #1790 ----
const privateCanon={id:'canon-old',media_type:'image',privacy:'private',title:'Old canon',created_at:1};
const reply=asset=>body=>({items:body.ids.map(id=>asset&&asset.id===id?{id,state:'active',asset}:{id,state:'missing',asset:null})});

test('a character canon older than the loaded pages is resolved through /api/assets/selection under its privacy, never a stub',async()=>{
  const t=setup();await t.load('makePictures');   // 60 loaded; the canon is not among them
  t.context.characters=[{id:'mira',canon_asset_id:'canon-old',privacy:'private',body:{who:'Mira'}}];t.context.selectionReply=reply(privateCanon);
  const note=await t.run('chooseCharacter')('mira');
  assert.notEqual(note,false);assert.equal(t.state.pick.title,'Old canon');assert.equal(t.state.pick.privacy,'private','the picture keeps its privacy');assert.equal(t.state.character,'mira');
  same(t.selections,[{body:{ids:['canon-old'],workspace_id:'w'.repeat(32),details:true},scope:'private'}]);
  await t.run('resolveAsset')('canon-old','private');assert.equal(t.selections.length,1,'a resolved picture is not asked for twice');
  const u=setup();await u.load('makePictures');u.state.pick=asset(1);u.context.characters=[{id:'mira',canon_asset_id:'gone',body:{}}];
  assert.equal(await u.run('chooseCharacter')('mira'),false);assert.equal(u.state.pick.id,'a1','the old choice is kept');assert.equal(u.state.character,undefined);assert.match(u.said.at(-1),/not available/);
});

test('pinned pictures resolve without a request, for the main picture and the pose picture',async()=>{
  const t=setup();t.state.pick=asset(149);t.state.pose={asset:asset(148)};
  assert.equal((await t.run('resolveAsset')('a149')).id,'a149');assert.equal((await t.run('resolveAsset')('a148')).id,'a148');assert.equal(t.selections.length+t.requests.length,0);
  assert.match(make,/posePick\)\{void needAsset\(posePick/,'the pose click resolves through needAsset');assert.match(make,/if\(pick\)\{void needAsset\(pick/,'the main click resolves through needAsset');
});

test('Edit and re-run resolves an off-page picture and pose, and a missing one refuses before changing anything',async()=>{
  const pose={id:'pose-old',media_type:'image',title:'Pose old',created_at:1},t=setup();await t.load('makePictures');
  t.context.selectionReply=body=>({items:body.ids.map(id=>({id,state:'active',asset:id==='canon-old'?privateCanon:pose}))});
  const run={goal:'edit',privacy:'private',redo:{pick:'canon-old',form:{},pose:{asset:'pose-old'}}};
  assert.equal(await t.run('redoRun')(run),true);assert.equal(t.state.pick.privacy,'private');assert.equal(t.state.pose.asset.title,'Pose old');
  same(t.selections.map(x=>x.scope),['private','private']);
  const u=setup();u.state.pick=asset(1);u.context.selectionReply=reply(privateCanon);
  assert.equal(await u.run('redoRun')({goal:'edit',redo:{pick:'canon-old',form:{},pose:{asset:'pose-gone'}}}),false);
  assert.equal(u.state.pick.id,'a1','nothing changed');assert.equal(u.state.pose,null);assert.match(u.said.at(-1),/not available/);
});

test('a reply for a query the box no longer holds is dropped (cleared back to the cached query)',async()=>{
  const t=setup({assets:[...Array.from({length:70},(_,i)=>asset(i)),asset(900,{title:'lighthouse'})]});
  await t.load('makePictures');t.state.queries.makePictures='lighthouse';
  let release;t.context.hold=new Promise(r=>{release=r;});const pending=t.load('makePictures');
  t.state.queries.makePictures='';t.context.hold=null;const cached=await t.load('makePictures');assert.equal(cached.items.length,60,'the empty query is still cached');
  release();await pending;
  assert.equal(t.state.grids.makePictures.items.length,60);assert.equal(t.state.grids.makePictures.items.some(a=>a.id==='a900'),false,'the old search reply did not replace the unfiltered grid');
});

test('the line-up uses the library it read even when a reset lands mid-read',async()=>{
  const t=setup();t.context.characters=[{id:'mira',name:'Mira',canon_asset_id:'canon',lineage:[],body:{}}];
  const box={dataset:{makeLineup:'mira'},innerHTML:'',isConnected:true,closest:()=>({open:true})};t.context.boxes=[box];
  t.context.json=async()=>{t.state.pictures=null;return{assets:[{id:'canon',media_type:'image',created_at:2},{id:'kept',media_type:'image',created_at:1,lineage:['canon'],review:'selected'}]};};
  t.context.inScope=()=>true;t.context.picture=()=>true;
  await t.run('fillLineups')();
  assert.match(box.innerHTML,/data-make-canon="kept"/,'the kept picture is listed');assert.doesNotMatch(box.innerHTML,/No kept picture comes from the canon yet/);
});
