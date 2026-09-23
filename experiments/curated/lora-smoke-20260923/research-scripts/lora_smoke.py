"""LoRA smoke tests for issues #757 (WAI v170 / Illustrious), #758 (NoobAI-XL 1.1 eps, hobby/non-commercial) and #759 (Pony V6), 23 September 2026.

Each run is the shipped preset API graph (workflows/api/{wai,noob,pony}-api.json) with LoRA slot 8 set to one LoRA at one strength
(model and clip) and slot 9 left at 0. Per checkpoint: one fixed seed, one prompt, one negative, one no-LoRA control, and two
strengths per LoRA. A trigger token is appended only when the civitai version lists one (recorded per run as `trigger`).
Straight to ComfyUI on 127.0.0.1:8188: POST /prompt, poll /history, one job at a time, never a resubmission of an uncertain prompt.
Before every submission the GPU lease file named by $LEASE must say free_for == "lora-smoke"; otherwise the script stops.

  python lora_smoke.py wai|noob|pony [--only name,name]     results append to $OUT/results.json (default .runtime/lora-smoke)
"""
import copy,datetime,json,os,sys,time,urllib.error,urllib.request
from pathlib import Path
REPO=Path(__file__).resolve().parents[4];COMFY='http://127.0.0.1:8188'
OUT=Path(os.environ.get('OUT',REPO/'.runtime/lora-smoke'));LEASE=os.environ.get('LEASE','')
SEED=2026092301;W,H=832,1216
SUBJECT=('1girl, solo, adult woman, elf, fantasy mage, long silver hair, green eyes, dark blue robe with gold trim, long sleeves, '
         'holding a glowing crystal orb with both hands, upper body, looking at viewer, library, bookshelves, candlelight, depth of field')
CHECKPOINTS={
 'wai':dict(graph='wai-api.json',positive=SUBJECT+', masterpiece, best quality, amazing quality',
            negative='bad quality, worst quality, worst detail, sketch, censor, nsfw',
            loras=[('stabilizer','illustriousXLv01_stabilizer_v1.198.safetensors',(0.5,0.7),''),
                   ('hands','detailed_hand_focus_style_illustriousXL_v1.1.safetensors',(0.6,0.85),''),
                   ('masterpiece','illustrious_masterpieces_v3.safetensors',(0.4,0.6),''),
                   ('microdetails','AddMicroDetails_Illustrious_v7.safetensors',(0.35,0.5),'addmicrodetails'),
                   ('velvet-colorlines','iLLC0lorL1nes.safetensors',(0.6,0.85),'C0lorL1nes')]),
 'noob':dict(graph='noob-api.json',positive='masterpiece, best quality, newest, absurdres, highres, safe, '+SUBJECT,
             negative=('worst quality, low quality, worst aesthetic, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, '
                       'fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, mammal, anthro, furry, ambiguous form, feral, nsfw'),
             loras=[('stabilizer-nbep11','noobai_ep11_stabilizer_v0.205_fp16.safetensors',(0.6,1.0),''),
                    ('masterpiece-eps','illustrious_noobai_epsilon_pred_1_masterpieces_v1.safetensors',(0.4,0.6),''),
                    ('flatcolor-il','illustrious_flat_color_v2.safetensors',(0.6,0.85),'flat color, no lineart')]),
 'pony':dict(graph='pony-api.json',positive='score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, rating_safe, '+SUBJECT,
             negative='score_4, score_5, score_6, worst quality, low quality, blurry, text, watermark, rating_explicit, rating_questionable, nsfw',
             loras=[('gothic-neon','g0th1cPXL.safetensors',(0.6,0.85),'g0thicPXL'),
                    ('dramatic-lighting','S1_Dramatic_Lighting_v3.safetensors',(0.6,0.85),'s1_dram'),
                    ('hands-pony','Hand_pony_style_v1.safetensors',(0.6,0.85),'')]),
}
def now():return datetime.datetime.now().isoformat(timespec='seconds')
def pins():
 lib=json.loads((REPO/'models/library.json').read_text(encoding='utf-8'))['assets']
 return {m['file'].split('/',1)[1]:m for m in lib if m.get('file','').startswith('loras/')}
def lease_ok():
 if not LEASE:return True
 try:return json.loads(Path(LEASE).read_text(encoding='utf-8')).get('free_for')=='lora-smoke'
 except Exception:return False
def plan(ck):
 c=CHECKPOINTS[ck];runs=[dict(name=f'{ck}-control',lora=None,strength=0.0,trigger='')]
 for name,f,strengths,trig in c['loras']:
  for s in strengths:runs.append(dict(name=f'{ck}-{name}-{s:g}',lora=f,strength=s,trigger=trig))
 return runs
def build(ck,run):
 c=CHECKPOINTS[ck];g=copy.deepcopy(json.loads((REPO/'workflows/api'/c['graph']).read_text(encoding='utf-8')))
 g['2']['inputs']['text']=c['positive']+(', '+run['trigger'] if run['trigger'] else '');g['3']['inputs']['text']=c['negative']
 g['4']['inputs'].update(width=W,height=H);g['5']['inputs']['seed']=SEED
 if run['lora']:g['8']['inputs'].update(lora_name=run['lora'],strength_model=run['strength'],strength_clip=run['strength'])
 else:g['8']['inputs'].update(strength_model=0,strength_clip=0)
 g['9']['inputs'].update(strength_model=0,strength_clip=0);g['7']['inputs']['filename_prefix']='Research/lora-smoke-'+run['name']
 return g
UNRESOLVED=('submitted','timeout')   # a prompt ID whose outcome is unknown: inspect /history, never resubmit
def submit(g):
 """POST /prompt only. Returns (prompt_id, None) or (None, rejection text); nothing is queued when it is rejected."""
 req=urllib.request.Request(COMFY+'/prompt',json.dumps({'prompt':g}).encode(),{'Content-Type':'application/json'})
 try:return json.load(urllib.request.urlopen(req,timeout=30))['prompt_id'],None
 except urllib.error.HTTPError as e:return None,e.read().decode('utf-8','replace')[:800]
def wait(pid,limit=1800):
 """Poll /history; a transient polling failure keeps polling, and the deadline leaves the run 'timeout' (unresolved)."""
 t0=time.time()
 while time.time()-t0<limit:
  time.sleep(4)
  try:h=json.load(urllib.request.urlopen(COMFY+'/history/'+pid,timeout=30))
  except (urllib.error.URLError,OSError,ValueError):continue
  if pid in h:
   st=h[pid].get('status',{});files=[o['filename'] for n in h[pid].get('outputs',{}).values() for o in n.get('images',[])]
   err=[m[1].get('exception_message','')[:300] for m in st.get('messages',[]) if isinstance(m,list) and m[0]=='execution_error']
   return st.get('status_str'),round(time.time()-t0,1),files,err
 return 'timeout',round(time.time()-t0,1),[],[]
def main(argv):
 ck=argv[0];only=set(argv[2].split(',')) if len(argv)>2 and argv[1]=='--only' else None
 OUT.mkdir(parents=True,exist_ok=True);path=OUT/'results.json'
 results=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
 save=lambda:path.write_text(json.dumps(results,indent=1,ensure_ascii=False),encoding='utf-8')
 open_=[r for r in results if r['status'] in UNRESOLVED]
 if open_:print('unresolved prompt IDs (inspect /history, then record the outcome; never resubmit):',[r['prompt_id'] for r in open_],flush=True);return 4
 # Only a success counts as done. A history-confirmed 'error' is a known failure, so the next deliberate
 # invocation may run that step again; 'rejected' never reached the queue.
 done={r['name'] for r in results if r['status']=='success'};p=pins()
 for run in plan(ck):
  if run['name'] in done or (only and run['name'] not in only):continue
  if not lease_ok():print('GPU lease is not free_for lora-smoke; stopping',flush=True);return 2
  q=json.load(urllib.request.urlopen(COMFY+'/queue',timeout=30))
  if q.get('queue_running') or q.get('queue_pending'):print('ComfyUI queue is busy; stopping',flush=True);return 3
  g=build(ck,run);(OUT/(run['name']+'.graph.json')).write_text(json.dumps(g,indent=1),encoding='utf-8')
  pin=p.get(run['lora'] or '',{})
  rec=dict(run,issue={'wai':757,'noob':758,'pony':759}[ck],checkpoint=g['1']['inputs']['ckpt_name'],seed=SEED,width=W,height=H,
           steps=g['5']['inputs']['steps'],cfg=g['5']['inputs']['cfg'],sampler=g['5']['inputs']['sampler_name'],scheduler=g['5']['inputs']['scheduler'],
           positive=g['2']['inputs']['text'],negative=g['3']['inputs']['text'],lora_sha256=pin.get('sha256'),lora_source=pin.get('source'),
           started=now())
  pid,rejected=submit(g)
  if pid is None:rec.update(prompt_id=None,status='rejected',seconds=0,files=[],error=[rejected],finished=now())
  else:
   # Persist the prompt ID before polling, so a crash while waiting leaves a recoverable 'submitted' record.
   rec.update(prompt_id=pid,status='submitted');results.append(rec);save()
   st,secs,files,err=wait(pid);rec.update(status=st,seconds=secs,files=files,error=err,finished=now());results.remove(rec)
  results.append(rec);save()
  print(run['name'],(pid or '-')[:8],rec['status'],rec['seconds'],rec['files'],rec['error'],flush=True)
  if rec['status']!='success':print('stopping after a non-success; inspect before any further submission',flush=True);return 1
 return 0
if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
