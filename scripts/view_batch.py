"""Run one Studio preset over a folder of named pictures, one job per picture, e.g. twelve rendered views of a 3D model.

  python scripts/view_batch.py --preset union-repaint-wai --in views/ --out painted/ --prompt "..." --set denoise=0.45 --set seed=1

Every *.png/*.jpg in --in (sorted) is uploaded as the `reference`, run as its own job (the Studio's job API keeps the receipts;
its 4-image batch cap is untouched) and its first output is copied to <out>/<view>.png. An optional views.json beside the
pictures overrides controls per view: {"front": {"positive": "...", "seed": 7}}. <out>/manifest.json is rewritten atomically
after every step; a rerun skips views already completed with the same source and controls.

A job whose outcome is uncertain (lost submit response, `uncertain` or any unrecognised state) is never resubmitted: the run
stops and names the job id. A failed job stops the run. Existing output files are never overwritten without --force.
Stdlib only; talks to a running Studio and touches no ComfyUI.
"""
import argparse, hashlib, http.client, json, os, sys, time
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

ORIGIN='http://127.0.0.1:8191'  # the Studio accepts mutations only from its own loopback origin
ACTIVE=('queued','waiting','submitting','running')
RETRYABLE=('failed','partial','cancelled','not_submitted','refused')  # known definite outcomes: a rerun may submit again
# `abandoned` is not one: the Studio abandons jobs whose remote outcome is unknown, unless it says never_submitted
TYPES={'.png':'image/png','.jpg':'image/jpeg'}

def digest(data): return hashlib.sha256(data).hexdigest()

def call(args,method,path,body=None,headers=None,timeout=60):
    """Raw response bytes; HTTPError, URLError and OSError propagate so each caller decides what an error means."""
    req=urlrequest.Request(args.url.rstrip('/')+path,data=body,method=method,headers=dict({'Origin':ORIGIN},**(headers or {})))
    with urlrequest.urlopen(req,timeout=timeout) as response: return response.read()

def detail(exc):
    if isinstance(exc,HTTPError):
        try: return json.loads(exc.read().decode('utf-8','replace')).get('error') or 'HTTP %d'%exc.code
        except (ValueError,AttributeError): return 'HTTP %d'%exc.code
    return str(exc)

def save(path,data):
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');os.replace(tmp,path)

def value(text):
    for kind in (int,float):
        try: return kind(text)
        except ValueError: pass
    return text

def views(folder):
    found=sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in TYPES)
    if not found: raise SystemExit('No .png/.jpg pictures in '+str(folder))
    names=[p.stem for p in found]
    clash=sorted({n for n in names if names.count(n)>1})
    if clash: raise SystemExit('Two pictures share a view name (outputs would collide): '+', '.join(clash))
    return [(p.stem,p) for p in found]

def overrides(folder,names):
    path=folder/'views.json'
    if not path.is_file(): return {}
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or not all(isinstance(v,dict) for v in data.values()): raise SystemExit('views.json must map a view name to an object of controls')
    unknown=sorted(set(data)-set(names))
    if unknown: raise SystemExit('views.json names pictures that are not in the folder: '+', '.join(unknown))
    return data

def decide(entry,sha,controls,output):
    """'run', 'skip' or 'resume' (poll the job already submitted); an unresolved entry that cannot resume stops the run."""
    if not entry: return 'run'
    same=entry['source_sha256']==sha and entry['controls']==controls
    if entry['status']=='completed':
        return 'skip' if same and output.is_file() and digest(output.read_bytes())==entry['output_sha256'] else 'run'
    if entry['status'] in RETRYABLE: return 'run'
    if entry.get('job_id') and same: return 'resume'
    raise SystemExit('Not resubmitting: %s is %s%s. Inspect it in the Studio, then delete this view from the manifest to run it again.'%(
        'job '+entry['job_id'] if entry.get('job_id') else 'an earlier submission whose outcome is unknown',entry['status'],
        '' if same or not entry.get('job_id') else ' and its source or controls have changed'))

def wait(args,job_id):
    """The job once it leaves the active states. Polls only read, so a slow Studio is retried; ten silent minutes or the
    timeout stops the run (never resubmits). A host out of memory can stall every reply for minutes."""
    deadline=time.monotonic()+args.timeout;heard=time.monotonic()
    while True:
        try:
            job=json.loads(call(args,'GET','/api/jobs/'+job_id));heard=time.monotonic()
            if job.get('status') not in ACTIVE: return job
        except (OSError,ValueError,http.client.HTTPException) as exc:
            if time.monotonic()-heard>args.silence: raise SystemExit('Lost sight of job %s (%s); it was not resubmitted. Check it in the Studio.'%(job_id,detail(exc)))
        if time.monotonic()>deadline: raise SystemExit('Job %s is still running after %ds; it was not resubmitted. Check it in the Studio.'%(job_id,args.timeout))
        time.sleep(args.poll)

def submit(args,manifest,entry,path,controls):
    """Upload, then create exactly one job. Returns its id; the entry is marked `submitting` first so a lost reply is never retried."""
    try: uploaded=json.loads(call(args,'POST','/api/upload',path.read_bytes(),{'Content-Type':TYPES[path.suffix.lower()],'X-Filename':path.name},timeout=120))['file']
    except (OSError,ValueError,KeyError) as exc: raise SystemExit('Upload of %s failed, no job was created: %s'%(path.name,detail(exc)))
    entry.update(status='submitting');save(args.manifest_path,manifest)
    body=json.dumps({'preset_id':args.preset,'controls':dict(controls,reference=uploaded),'batch_count':1}).encode()
    try: job=json.loads(call(args,'POST','/api/jobs',body,{'Content-Type':'application/json'}))
    except HTTPError as exc:
        if exc.code<500:
            entry.update(status='refused',message=detail(exc));save(args.manifest_path,manifest)
            raise SystemExit('The Studio refused %s: %s'%(path.name,detail(exc)))
        job=exc  # a 5xx may still have queued the job
    except (OSError,ValueError) as exc: job=exc
    if not isinstance(job,dict) or not job.get('id'):
        raise SystemExit('Submission of %s has an unknown outcome (%s). Not resubmitted: look for it in the Studio job list, then delete this view from the manifest to run it again.'%(path.name,detail(job) if isinstance(job,Exception) else 'no job id in the reply'))
    print('job    %s %s'%(path.stem,job['id']),flush=True)  # before the save: a locked manifest must not lose the id
    entry.update(job_id=job['id'],status=job.get('status') or 'queued');save(args.manifest_path,manifest)
    return job['id']

def finish(args,manifest,name,entry,job,output):
    status=job.get('status')
    if status=='abandoned' and (job.get('abandonment') or {}).get('basis')=='never_submitted': status='not_submitted'
    entry.update(status=status,prompt_id=(job.get('prompt_ids') or [None])[0],message=job.get('message'))
    if status!='completed':
        save(args.manifest_path,manifest)
        if status in RETRYABLE: raise SystemExit('View %s failed (job %s, %s): %s'%(name,entry['job_id'],status,job.get('message') or 'no message'))
        raise SystemExit('View %s: job %s is %s, an outcome this run cannot confirm. Not resubmitted; inspect it in the Studio. %s'%(name,entry['job_id'],status,job.get('message') or ''))
    if not job.get('outputs'):
        entry['status']='running';save(args.manifest_path,manifest)  # stay resumable: the job is done but nothing was copied
        raise SystemExit('View %s: job %s completed with no outputs listed. Not resubmitted.'%(name,entry['job_id']))
    try: data=call(args,'GET','/api/image/%s/0'%entry['job_id'],timeout=120)
    except OSError as exc:
        entry['status']='running';save(args.manifest_path,manifest)
        raise SystemExit('View %s: job %s completed but its image could not be fetched (%s). Rerun to fetch it; nothing is resubmitted.'%(name,entry['job_id'],detail(exc)))
    tmp=output.with_name(output.name+'.tmp');tmp.write_bytes(data);os.replace(tmp,output)
    entry.update(status='completed',output=str(output),output_sha256=digest(data),seconds=job.get('elapsed_seconds'))
    save(args.manifest_path,manifest)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--preset',required=True);parser.add_argument('--in',dest='inp',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--prompt',help='the positive prompt for every view (a views.json entry overrides it)')
    parser.add_argument('--set',dest='sets',action='append',default=[],metavar='CONTROL=VALUE',help='a control for every view; repeatable')
    parser.add_argument('--url',default='http://127.0.0.1:8191');parser.add_argument('--force',action='store_true',help='overwrite existing output files')
    parser.add_argument('--dry-run',action='store_true',help='print the plan and submit nothing');parser.add_argument('--poll',type=float,default=2.0,help='seconds between job polls')
    parser.add_argument('--timeout',type=int,default=3600,help='seconds to wait for one job before stopping')
    parser.add_argument('--silence',type=int,default=600,help='seconds of failed polls before stopping')
    args=parser.parse_args(argv)
    if not args.inp.is_dir(): parser.error('--in is not a folder: '+str(args.inp))
    base={}
    if args.prompt is not None: base['positive']=args.prompt
    for item in args.sets:
        key,eq,text=item.partition('=')
        if not eq or not key or key=='reference': parser.error('--set needs CONTROL=VALUE (reference is set per picture): '+item)
        base[key]=value(text)
    found=views(args.inp);extra=overrides(args.inp,[n for n,_ in found])
    args.manifest_path=args.out/'manifest.json'
    manifest=json.loads(args.manifest_path.read_text(encoding='utf-8')) if args.manifest_path.is_file() else {}
    if manifest and manifest.get('preset')!=args.preset: raise SystemExit('%s belongs to preset %s; choose another --out for %s'%(args.manifest_path,manifest.get('preset'),args.preset))
    manifest.update(version=1,preset=args.preset,url=args.url,controls=base);manifest.setdefault('views',{})
    plan=[]
    for name,path in found:
        controls=dict(base,**extra.get(name,{}));controls.pop('reference',None)
        sha=digest(path.read_bytes());output=args.out/(name+'.png')
        action=decide(manifest['views'].get(name),sha,controls,output)
        if action!='skip' and output.exists() and not args.force:
            raise SystemExit('Refusing to overwrite %s (use --force)'%output)
        plan.append((name,path,sha,controls,output,action))
    for name,path,sha,controls,output,action in plan:
        print('%-6s %s <- %s %s'%(action,name,path,json.dumps(controls,sort_keys=True)))
    if args.dry_run: return 0
    args.out.mkdir(parents=True,exist_ok=True)
    lock=args.out/'.view_batch.lock'
    try: os.close(os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY))
    except FileExistsError: raise SystemExit('Another run holds %s. Two runs would submit the same views twice. Delete it only if no run is active.'%lock)
    try: run_plan(args,manifest,plan)
    finally: lock.unlink(missing_ok=True)
    return 0

def run_plan(args,manifest,plan):
    for name,path,sha,controls,output,action in plan:
        if action=='skip': continue
        if action=='run':
            entry=manifest['views'][name]=dict(source=str(path),source_sha256=sha,controls=controls,job_id=None,prompt_id=None,status='submitting',output=None,output_sha256=None,seconds=None,message=None)
            submit(args,manifest,entry,path,controls)
        entry=manifest['views'][name]
        print('wait   %s job %s'%(name,entry['job_id']),flush=True)
        finish(args,manifest,name,entry,wait(args,entry['job_id']),output)
        print('done   %s -> %s'%(name,output),flush=True)
    return 0

if __name__=='__main__': sys.exit(main())
