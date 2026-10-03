from pathlib import Path
import subprocess
root=Path('.')
def blob(name): return subprocess.check_output(['git','hash-object',name],text=True).strip()
for name,wanted in {'app/static/app.js':'12018d30d7df8457a6ae051e66d3fdf9dad7f989','app/static/studio-core.js':'7c005187885ae082dfb8a4bcd5558ae009e607d2','app/static/studio-workbench.js':'2e47ddfda94b3ad6041e66bf15ff98ed909b314a'}.items(): assert blob(name)==wanted,('base drift',name)
def replace(name,old,new):
 p=root/name;s=p.read_text();assert s.count(old)==1,(name,old[:60],s.count(old));p.write_text(s.replace(old,new))
code='''  // Structural draft envelope only. The server rechecks plan identity, source bytes and
  // prepared input before admission; restoring a draft never certifies those files.
  function normalizePrepared(recipe){
    const kinds=['tile','parallax'].filter(k=>recipe[k]!=null);
    if(!kinds.length)return {};
    if(kinds.length!==1||recipe.continuation!=null)return null;
    const kind=kinds[0],c=recipe[kind],common=['version','preset_id','source_asset_id','source_sha256'];
    const fields=common.concat(kind==='tile'?['rolled_file','rolled_sha256','size','band_px','feather_px','flatten_sigma_px']:['plan_id','stage','source_file','width','height','objects','view_polygons']);
    const text=(v,n=255)=>typeof v==='string'&&v.length>0&&v.length<=n;
    const sha=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
    const integer=(v,min,max)=>Number.isSafeInteger(v)&&v>=min&&v<=max;
    if(!c||typeof c!=='object'||Array.isArray(c)||Object.keys(c).length!==fields.length||fields.some(k=>!Object.hasOwn(c,k))||c.version!==1||c.preset_id!==recipe.preset||!text(c.preset_id,120)||!text(c.source_asset_id)||!sha(c.source_sha256))return null;
    if(kind==='tile'){
      if(!sha(c.rolled_sha256)||!text(c.rolled_file)||!(/^[a-f0-9]{32}_[A-Za-z0-9._-]+\\.png$/).test(c.rolled_file)||!integer(c.size,256,1536)||c.size%16||!integer(c.band_px,16,Math.min(512,c.size/2))||c.band_px%2||!integer(c.feather_px,0,64)||!integer(c.flatten_sigma_px,0,Math.floor(c.size/3)))return null;
    }else{
      if(!sha(c.plan_id)||!['plate','isolate'].includes(c.stage)||!text(c.source_file)||!(/^[a-f0-9]{32}_[A-Za-z0-9._-]+\\.(png|jpg|webp)$/).test(c.source_file)||!integer(c.width,512,1536)||!integer(c.height,512,1536)||c.width%16||c.height%16||c.width*c.height>1600000||!text(c.objects,240)||c.objects.trim().split(/\\s+/).join(' ')!==c.objects||/[{}\\[\\]]/.test(c.objects))return null;
      if(!Array.isArray(c.view_polygons)||c.view_polygons.length>4||c.view_polygons.some(p=>!Array.isArray(p)||p.length<3||p.length>16||p.some(v=>!Array.isArray(v)||v.length!==2||!integer(v[0],0,c.width)||!integer(v[1],0,c.height))))return null;
    }
    return {[kind]:JSON.parse(JSON.stringify(c))};
  }
  function preparedBlocker(recipe){
    const saved=normalizePrepared(recipe);if(!saved)return 'Invalid prepared plan. Prepare it again from the Asset library.';
    const c=saved.tile||saved.parallax;if(!c)return '';
    const action=saved.tile?'Make seamless':'Make parallax layers';
    if(Number(recipe.batch??recipe.batch_count??1)!==1)return 'A prepared edit runs one picture at a time. Set batch to 1.';
    if(!Array.isArray(recipe.parent_assets)||!recipe.parent_assets.includes(c.source_asset_id))return 'The prepared source is missing from lineage. Use '+action+' again.';
    if(recipe.controls?.reference!==(c.rolled_file||c.source_file))return 'The prepared picture is missing or was replaced. Use '+action+' again.';
    if(saved.parallax&&(Number(recipe.controls?.width)!==c.width||Number(recipe.controls?.height)!==c.height))return 'This parallax plan needs its source size, '+c.width+' × '+c.height+'. Restore that size or prepare it again.';
    return '';
  }
'''
replace('app/static/studio-core.js','  function normalizeDraft(value){',code+'  function normalizeDraft(value){')
replace('app/static/studio-core.js','    const continuation=value.recipe.continuation;', "    const prepared=normalizePrepared(value.recipe);if(!prepared)return null;\n    const continuation=value.recipe.continuation;")
replace('app/static/studio-core.js','recipe:{preset:value.recipe.preset,controls,batch,','recipe:{preset:value.recipe.preset,controls,batch,...prepared,')
replace('app/static/studio-core.js','sceneEligibility,normalizeDraft,','sceneEligibility,normalizePrepared,preparedBlocker,normalizeDraft,')
replace('app/static/app.js','  selectPreset(s.preset);', '''  const prepared=typeof StudioUX!=='undefined'?StudioUX.normalizePrepared(s):(s.tile!=null||s.parallax!=null?null:{});
  const target=catalog.presets.find(p=>p.id===s.preset);
  if(!prepared||prepared.tile&&!target.tile_route||prepared.parallax&&!target.parallax_route)throw Error('Invalid saved prepared plan for this recipe. Prepare it again from the Asset library.');
  selectPreset(s.preset);
  tileState=prepared.tile||null;parallaxState=prepared.parallax||null;
''')
replace('app/static/app.js',"  if(!continuationState)return selected?.positive", "  if(tileState||parallaxState){const problem=StudioUX.preparedBlocker({preset:selected.id,...tilePayload(),...parallaxPayload(),controls:values(),parent_assets:parentAssets,batch:$('#batch').value});if(problem)return [{code:tileState?'tile':'parallax',message:problem}];}\n  if(!continuationState)return selected?.positive")
replace('app/static/app.js','recipe:{preset:selected.id,...continuationPayload(),controls:checkedSetupControls(),','recipe:{preset:selected.id,...continuationPayload(),...tilePayload(),...parallaxPayload(),controls:checkedSetupControls(),')
replace('app/static/app.js','preset:recipe.preset_id,continuation:recipe.continuation,controls:recipe.controls,','preset:recipe.preset_id,continuation:recipe.continuation,tile:recipe.tile,parallax:recipe.parallax,controls:recipe.controls,')
replace('app/static/studio-workbench.js','recipe:{preset:selected.id,...continuationPayload(),','recipe:{preset:selected.id,...continuationPayload(),...tilePayload(),...parallaxPayload(),')
expected={'app/static/app.js':'dfb99d9e5acc5415453276690cb5690fad99008f','app/static/studio-core.js':'9ed6e149477354ee205a6b2e807e4d9733366d91','app/static/studio-workbench.js':'d6a566253e3d03c19848ef1d407baf1905084e76','tests/prepared_draft_recovery.cjs':'65f3530b782b5ded5eae8d5f6822eb0ca667e447','tests/test_prepared_draft_recovery.py':'214be7e85065250077ab971612449acb3ef57af6','tests/prepared_draft_browser.py':'35cf801ba93f2ef17937bfb8314858f980722020','.github/workflows/prepared-draft-recovery.yml':'6b5fd031559d41f6dc51a900245b3bd982c7498e'}
for name,wanted in expected.items(): assert blob(name)==wanted,('output drift',name,blob(name))
