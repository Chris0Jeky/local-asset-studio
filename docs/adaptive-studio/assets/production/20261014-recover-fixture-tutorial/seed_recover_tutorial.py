"""Public retained-state teaching fixture; no engine call or submission."""
from pathlib import Path
import argparse,hashlib,json,time
R=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo-root',type=Path,default=R/'las-next-tutorials');p.add_argument('--evidence',type=Path,default=R/'evidence/follow-on-20261014');a=p.parse_args();repo=a.repo_root.resolve();E=a.evidence.resolve();E.mkdir(parents=True,exist_ok=True);runtime=repo/'.runtime/recover-tutorial'
assert not runtime.exists(),'Never overwrite retained state';runtime.mkdir(parents=True)
config=repo/'config/local.json';settings=json.loads(config.read_text());before=hashlib.sha256(config.read_bytes()).hexdigest()
settings.update(experiments_root=str(runtime/'experiments'),comfy_root=str(runtime/'uninstalled-comfy'),comfy_url='http://127.0.0.1:18188',runtime_auto_recover=False,idle_cache_release_minutes=0,observe_job_resources=False,enable_large_job_resource_cleanup=False,enable_large_job_backend_restart=False,enable_idle_retained_commit_cleanup=False)
config.write_text(json.dumps(settings,indent=2)+'\n')
preset=next(p for p in json.loads((repo/'presets/catalog.json').read_text())['presets'] if p['id']=='anima-portrait')
graph_path=repo/preset['graph'];graph=json.loads(graph_path.read_text())
controls=dict(positive='CONTROLLED FIXTURE: no request was sent. An original brass lantern on a quiet workshop desk.',negative='worst quality, low quality, blurry, bad anatomy, bad hands, text, watermark',seed=2026101401,steps=30,cfg=4,width=768,height=1152)
for key,value in controls.items():
 if key in preset and isinstance(preset[key],list):node,field=preset[key];graph[node]['inputs'][field]=value
identifier='controlled-recover-tutorial-20261014'
state=dict(id=identifier,status='uncertain',preset_id='anima-portrait',preset_name='CONTROLLED FIXTURE - simulated unknown request',created_at=time.time(),controls=controls,batch_count=1,graph_path=preset['graph'],prompt_ids=[],submissions=[],outputs=[],references=[],parent_assets=[],message='Public simulated uncertainty. No request was sent.',pending_submission={'index':0,'fixture':True,'note':'Deliberately seeded marker; no actual remote POST or lost response.'})
target=runtime/'experiments/runs'/identifier;target.mkdir(parents=True)
for name,value in [('state.json',state),('workflow.json',graph),('recipe.json',{k:state[k] for k in ['preset_id','controls','batch_count','graph_path','created_at','references','parent_assets']})]:(target/name).write_text(json.dumps(value,indent=2)+'\n')
fixture=dict(classification='CONTROLLED PUBLIC FIXTURE; never a real request/output',job_id=identifier,seeded_state=state,graph_template=preset['graph'],graph_template_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(),graph=graph,config_before_sha256=before,config_after_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),expected='Actual server loads retained unknown-state marker; actual UI has no observation/replay button and Recipe is read-only. Stop without mutation.',backend='Unused loopback port 18188; no installed or started backend')
(E/'RECOVER-FIXTURE.json').write_text(json.dumps(fixture,indent=2)+'\n');print(json.dumps({'job':identifier,'runtime':str(runtime),'classification':fixture['classification']}))
