from pathlib import Path
import subprocess
def blob(name): return subprocess.check_output(['git','hash-object',name],text=True).strip()
before={'app/static/studio-workbench.js':'d6a566253e3d03c19848ef1d407baf1905084e76','tests/prepared_draft_recovery.cjs':'65f3530b782b5ded5eae8d5f6822eb0ca667e447','tests/prepared_draft_browser.py':'35cf801ba93f2ef17937bfb8314858f980722020'}
for name,wanted in before.items(): assert blob(name)==wanted,('base drift',name)
def replace(name,old,new):
 p=Path(name);s=p.read_text();assert s.count(old)==1,(name,old[:80]);p.write_text(s.replace(old,new))
replace('app/static/studio-workbench.js',"    if(typeof backendActive==='undefined'||backendId!==backendActive)throw Error('The active backend changed before loading this revision.');", "    if(draft.recipe.tile&&!target.tile_route||draft.recipe.parallax&&!target.parallax_route)throw Error('The prepared plan does not belong to this recipe. No settings were changed.');\n    if(typeof backendActive==='undefined'||backendId!==backendActive)throw Error('The active backend changed before loading this revision.');")
replace('app/static/studio-workbench.js',"      recipeTemplateHash=draft.templateHash;pendingInputs.clear();q('#batch').value=String(draft.recipe.batch);", "      tileState=draft.recipe.tile||null;parallaxState=draft.recipe.parallax||null;\n      if(typeof StudioLooks!=='undefined')StudioLooks.restoreApplication(draft.recipe.look_application,target.id);\n      recipeTemplateHash=draft.templateHash;pendingInputs.clear();q('#batch').value=String(draft.recipe.batch);")
extra='''const workbench=fs.readFileSync(require.resolve('../app/static/studio-workbench.js'),'utf8');
const adopt=workbench.slice(workbench.indexOf('  function adoptSharedSetup('),workbench.indexOf('  window.StudioSetupDraft='));
function sharedFixture(value){
  const state=applyFixture({preset:'plain',controls:{}}),L=require('../app/static/looks.js');
  for(const p of state.catalog.presets)Object.assign(p,{positive:['1','text'],width:['1','width'],height:['1','height']});
  Object.assign(state,{U,StudioLooks:L,setupBusy:()=>false,setupStamp:()=>1,backendActive:'primary',controlKeys:['width','height'],referenceRoles:[],
    q:state.$,pendingInputs:new Set(),renderReferenceSlots(){},updateLoraHints(){},syncCreate(){},syncReady(){},saveDraft(){},hydrateContinuation(){}});
  state.values=()=>({positive:state.$('#positive').value,reference:state.uploaded,width:state.getControl('width').value,height:state.getControl('height').value});
  const select=state.selectPreset;state.selectPreset=id=>{select(id);L.clearApplication();};
  vm.runInContext(adopt,state);
  global.StudioLooks=L;
  try{state.adoptSharedSetup(value,1,'primary');return state;}finally{delete global.StudioLooks;}
}
test('shared adoption restores prepared envelopes and retained Look holds instead of dropping them',()=>{
  for(const [kind,claim] of [['tile',tile],['parallax',parallax]]){
    const state=sharedFixture(draft(recipe(kind,claim)));
    assert.deepEqual(JSON.parse(JSON.stringify(state[kind+'State'])),claim);
  }
  const value=draft({preset:'plain',controls:{},look_application:{version:1,preset_id:'plain',controls:['sampler']}});
  const state=sharedFixture(value);assert.match(state.StudioLooks.applicationBlocker('plain'),/sampler/);state.StudioLooks.clearApplication();
});
'''
replace('tests/prepared_draft_recovery.cjs',"console.log(count+' prepared-draft checks passed');",extra+"console.log(count+' prepared-draft checks passed');")
replace('tests/prepared_draft_browser.py',"                            before = len(SAVED)",'''                            # Shared revision loading uses its own mutation path, not applySaved.
                            page.evaluate('(d) => StudioSetupDraft.adopt(d,StudioSetupDraft.stamp(),backendActive)', captured)
                            assert page.evaluate('(k) => (k === "tile" ? tilePayload() : parallaxPayload())[k]', kind) == plan
                            held = copy.deepcopy(captured)
                            held['recipe']['look_application'] = {'version': 1, 'preset_id': plan['preset_id'], 'controls': ['sampler']}
                            page.evaluate('(d) => StudioSetupDraft.adopt(d,StudioSetupDraft.stamp(),backendActive)', held)
                            assert page.locator('#generate').is_disabled()
                            assert 'sampler' in page.evaluate('StudioLooks.applicationBlocker(selected.id)')
                            page.evaluate('(d) => StudioSetupDraft.adopt(d,StudioSetupDraft.stamp(),backendActive)', captured)
                            assert page.evaluate('StudioLooks.applicationBlocker(selected.id)') == ''
                            before = len(SAVED)''')
replace('tests/prepared_draft_browser.py','capture, restore, named save, checked import, stale-source hold','capture, restore, shared adoption and holds, named save, checked import, stale-source hold')
after={'app/static/studio-workbench.js':'5e6827780515aac0500e4f1541d4698ac7cbede0','tests/prepared_draft_recovery.cjs':'934dc4c086816e93bc50451eb3486242fe02fd56','tests/prepared_draft_browser.py':'9f2af19b8f90e7537b4f0df4cb84cd6a5e7d8b44'}
for name,wanted in after.items(): assert blob(name)==wanted,('output drift',name,blob(name))
