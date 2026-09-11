"""Serial, resumable ComfyUI batch submission using only Python's standard library."""
import argparse,copy,hashlib,json,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--graph',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--count',type=int,default=1);p.add_argument('--seed',type=int,default=4200)
p.add_argument('--dry-run',action='store_true');a=p.parse_args()
if not 1<=a.count<=100: p.error('count must be 1..100')
base='http://127.0.0.1:8188';g=json.loads(a.graph.read_text(encoding='utf-8-sig'))
if not isinstance(g,dict) or any('class_type' not in v or 'inputs' not in v for v in g.values()):p.error('Use an API graph, not a visual workflow')
identity={'graph_sha256':hashlib.sha256(json.dumps(g,sort_keys=True).encode()).hexdigest(),'count':a.count,'seed':a.seed}
if a.dry_run:
 print(json.dumps({'valid_api_shape':True,'nodes':len(g),**identity},indent=2));raise SystemExit()
a.out.mkdir(parents=True,exist_ok=True)
def save(path,data):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');tmp.replace(path)
def request(path,data=None):
 r=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=60) as f:
  b=f.read();return json.loads(b) if b else None
manifest=a.out/'batch.json'
if manifest.exists():
 if json.loads(manifest.read_text())!=identity:raise SystemExit('This output folder belongs to different inputs. Choose a new folder.')
else:save(manifest,identity)
for i in range(a.count):
 folder=a.out/f'{i:03}';folder.mkdir(exist_ok=True);state=folder/'submission.json';result=folder/'result.json'
 if result.exists():
  if json.loads(result.read_text())['status']['status_str']!='success':raise SystemExit('Prior failed job: inspect '+str(result))
  print('Already complete:',folder,flush=True);continue
 if state.exists():prompt_id=json.loads(state.read_text())['prompt_id']
 else:
  # A lost POST response must be reconciled manually rather than duplicated.
  marker=folder/'submission-started.json'
  if marker.exists():raise SystemExit('Submission outcome uncertain. Inspect ComfyUI history before retrying '+str(folder))
  deadline=time.monotonic()+24*3600
  while True:
   q=request('/queue')
   if not q['queue_running'] and not q['queue_pending']:break
   if time.monotonic()>deadline:raise TimeoutError('Queue did not become idle')
   time.sleep(5)
  graph=copy.deepcopy(g)
  for node in graph.values():
   for field in ['seed','noise_seed']:
    if field in node['inputs']:node['inputs'][field]=a.seed+i
  save(folder/'graph.json',graph);save(marker,{'started':time.time()})
  reply=request('/prompt',{'prompt':graph,'client_id':'local-asset-batch'});save(state,reply);prompt_id=reply['prompt_id']
 print('Waiting:',prompt_id,flush=True);deadline=time.monotonic()+24*3600
 while True:
  history=request('/history/'+prompt_id)
  if prompt_id in history:
   rec=history[prompt_id];save(result,rec)
   if rec['status']['status_str']!='success':raise SystemExit('Generation failed; see '+str(result))
   print('Complete:',folder,'Images remain in ComfyUI/output; locations recorded in result.json',flush=True);break
  if time.monotonic()>deadline:raise TimeoutError('Server may still be generating. Resume the same output folder.')
  time.sleep(5)
