"""Explicit, pinned CPU voice takes on the existing Production coordinator."""
from __future__ import annotations
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid
import wave
from studio_av.project import file_hash,need,fields,number,safe_path
from studio_av.render import _run_owned,RenderCancelled,inspect_wav

OPERATION='native.voice-baseline.v1'


def observed_versions(studio, python, expected):
    """Read only distribution metadata in the configured isolated interpreter."""
    need(isinstance(expected,dict) and 1<=len(expected)<=32,'Record one to 32 runtime package versions')
    names=[]
    for name,version in expected.items():
        need(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',name),'Invalid runtime distribution name')
        need(isinstance(version,str) and 1<=len(version)<=128,'Invalid pinned runtime version')
        names.append(name)
    probe=studio.root/'scripts/voice_runtime_probe.py';need(probe.is_file(),'Voice runtime metadata probe is unavailable')
    try:
        with tempfile.TemporaryFile(mode='w+b') as stdout:
            process=subprocess.Popen([str(python),str(probe),*sorted(names)],cwd=str(studio.root),stdout=stdout,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+10
                while process.poll() is None:
                    if time.monotonic()>=deadline:raise subprocess.TimeoutExpired(process.args,10)
                    time.sleep(.05)
                if process.returncode:raise subprocess.CalledProcessError(process.returncode,process.args)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            stdout.seek(0);raw=stdout.read(64*1024+1)
    except (OSError,subprocess.SubprocessError) as exc:
        raise ValueError('Voice runtime metadata probe failed') from exc
    need(len(raw)<=64*1024,'Voice runtime metadata probe returned oversized output')
    try:observed=json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError('Voice runtime metadata probe returned invalid JSON') from exc
    need(isinstance(observed,dict) and set(observed)==set(names) and all(isinstance(value,str) for value in observed.values()),'Voice runtime metadata probe did not report every package')
    return observed


def _require_versions(expected, observed, prior=None):
    need(observed==expected,'Voice runtime package versions changed from the bundle manifest')
    if prior is not None:need(observed==prior,'Voice runtime package versions changed since Prepare')


def bundle(studio):
    configured=studio.config.get('voice_baseline_bundle','')
    need(isinstance(configured,str) and Path(configured).is_absolute(),'Configure an isolated voice_baseline_bundle first')
    path=Path(configured);need(path.is_file() and path.stat().st_size<=64*1024,'Voice bundle manifest is missing or oversized')
    result=json.loads(path.read_text(encoding='utf-8'))
    fields(result,('schema_version','model_id','revision','python','voice','lang_code','files','versions','license'))
    need(result['schema_version']==1 and result['model_id']=='hexgrad/Kokoro-82M' and result['voice']=='af_heart' and result['lang_code']=='a','Unsupported baseline bundle')
    need(isinstance(result['revision'],str) and re.fullmatch('[0-9a-f]{40}',result['revision']),'Pin the full model revision')
    need(isinstance(result['files'],dict) and set(result['files'])=={'model','config','voice'},'Pin all baseline model files')
    for name,item in result['files'].items():
        fields(item,('path','bytes','sha256'));need(isinstance(item['path'],str) and Path(item['path']).is_absolute(),'Use absolute local bundle files')
        target=Path(item['path']);need(target.is_file(),'Missing voice bundle file');number(item['bytes'],1,1024**3,'model bytes',True)
        need(isinstance(item['sha256'],str) and re.fullmatch('[0-9a-f]{64}',item['sha256']),'Pin voice file SHA256')
        need(target.stat().st_size==item['bytes'] and file_hash(target)==item['sha256'],'Voice bundle file changed')
    python=Path(result['python']);need(python.is_absolute() and python.is_file(),'Voice Python is unavailable')
    need(isinstance(result['versions'],dict) and isinstance(result['license'],dict),'Record runtime versions and model terms')
    return {**result,'python_sha256':file_hash(python)}


def capabilities(studio):
    # Readiness is presence-only on page load; full hashes are checked at Prepare and Start.
    configured=studio.config.get('voice_baseline_bundle','')
    ready=isinstance(configured,str) and Path(configured).is_absolute() and Path(configured).is_file()
    return {'configured':ready,'voice':'af_heart','language':'American English','model':'Kokoro-82M CPU baseline',
            'supported':['original text','built-in baseline voice','24 kHz dry PCM','48 kHz scene interchange','explicit owned queue'],
            'unsupported':['voice design','cloning','acting instructions','ASR','alignment','creative acceptance']}


def prepare(production,payload):
    fields(payload,('name','speaker_id','lines'));need(isinstance(payload['name'],str) and 1<=len(payload['name'])<=120,'Name the voice take')
    need(isinstance(payload['speaker_id'],str) and re.fullmatch('[a-z][a-z0-9_-]{0,63}',payload['speaker_id']),'Use a stable fictional speaker ID')
    lines=payload['lines'];need(isinstance(lines,list) and 1<=len(lines)<=6,'Use one to six original lines');ids=set();total=0
    for line in lines:
        fields(line,('id','text'));need(isinstance(line['id'],str) and re.fullmatch('[a-z][a-z0-9_-]{0,63}',line['id']) and line['id'] not in ids,'Use distinct stable line IDs')
        need(isinstance(line['text'],str) and line['text'].strip() and len(line['text'])<=600 and '\0' not in line['text'],'Line text must contain 1 to 600 characters')
        ids.add(line['id']);total+=len(line['text'])
    need(total<=2000,'Voice text budget is 2000 characters')
    pinned=bundle(production.studio);observed=observed_versions(production.studio,pinned['python'],pinned['versions']);_require_versions(pinned['versions'],observed)
    ffmpeg=production.studio.config.get('ffmpeg','');need(Path(ffmpeg).is_absolute() and Path(ffmpeg).is_file(),'Configure FFmpeg for scene interchange')
    runner=production.studio.root/'scripts/kokoro_baseline.py';need(runner.is_file(),'Voice runner unavailable')
    identifier=uuid.uuid4().hex;directory=production.root/identifier
    need(shutil.disk_usage(production.root).free>=2*1024**3,'Voice take needs 2 GiB free')
    from production import fingerprint
    plan={'version':1,'kind':'voice','name':payload['name'],'speaker_id':payload['speaker_id'],'lines':lines,'bundle':pinned,'observed_versions':observed,
          'runner_sha256':file_hash(runner),'ffmpeg':str(ffmpeg),'ffmpeg_sha256':file_hash(ffmpeg),'stages':[],'created_at':time.time()}
    plan['sha256']=fingerprint(plan);state={'status':'planned','message':'Voice take prepared. Generate explicitly; no voice identity or performance is accepted.',
        'attempts':{},'artifacts':[],'stop_requested':False,'review':{'status':'unreviewed'}}
    directory.mkdir();production.studio._write_json_atomic(directory/'plan.json',plan)
    with production.connect() as db:
        db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO budgets(id,allowance) VALUES (?,0)',(identifier,))
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(identifier,identifier,json.dumps(plan),json.dumps(state),time.time()))
    return production.get(identifier)


def artifacts(production,identifier):
    base=production.root/identifier;result=[]
    for relative in ['voice.log','resample.log','request.json']+[p.relative_to(base).as_posix() for p in (base/'voice').glob('*') if p.is_file()]:
        path=base/relative
        if path.is_file():result.append({'path':relative,'url':f'/api/production/{identifier}/files/{relative}','sha256':file_hash(path),'role':'audio' if path.suffix=='.wav' else 'evidence'})
    return result


def resume_eligibility(production, project):
    """Report whether an interrupted voice plan has no durable execution evidence."""
    identifier=project['id'];state=project['state'];directory=production.root/identifier
    if state.get('status')!='interrupted':return {'eligible':False,'message':'Only an interrupted voice take can resume.'}
    if state.get('stop_requested'):return {'eligible':False,'message':'This take has a recorded stop request; inspect it and prepare a new take if needed.'}
    if state.get('attempts'):return {'eligible':False,'message':'A durable voice attempt exists; Studio will not retry it.'}
    if state.get('artifacts'):return {'eligible':False,'message':'Retained voice artifacts exist; Studio will not retry the take.'}
    job_id=uuid.uuid5(uuid.NAMESPACE_URL,'studio-voice:'+identifier).hex
    with production.studio.lock:jobs=dict(production.studio.jobs)
    recorded_job=job_id in jobs or any(job.get('project_id')==identifier and job.get('operation')==OPERATION for job in jobs.values()) or (production.studio.runs/job_id).exists()
    if recorded_job:return {'eligible':False,'message':'A durable owned voice job exists; Studio will not retry it.'}
    if (directory/'request.json').exists():return {'eligible':False,'message':'A durable voice request exists; Studio will not retry it.'}
    if (directory/'voice').exists():return {'eligible':False,'message':'Retained voice output files exist; Studio will not retry the take.'}
    return {'eligible':True,'message':'No request, attempt, owned job or voice output exists. Resume only queues this unstarted plan.'}


def resume(production, identifier):
    with production.studio.lock,production.lock:
        project=production._get(identifier);eligibility=resume_eligibility(production,project)
        need(eligibility['eligible'],eligibility['message'])
        production._mutate(identifier,status='queued',stop_requested=False,message='Explicitly resumed an unstarted voice plan; no inference was repeated.')
        production.studio.queue.put(('production',identifier));return production.get(identifier)


def run(production,identifier,plan):
    studio=production.studio;directory=production.root/identifier;out=directory/'voice';job_id=uuid.uuid5(uuid.NAMESPACE_URL,'studio-voice:'+identifier).hex
    if (directory/'request.json').exists():
        production._mutate(identifier,status='interrupted',message='A prior voice attempt exists. Inspect retained files; prepare a new take to retry.');return
    def cancelled():return bool(production._get(identifier)['state'].get('stop_requested'))
    attempt_started=False;job=None
    try:
        production._attempt(identifier,0,operation=OPERATION,job_id=job_id,status='running',started_at=time.time());attempt_started=True
        if cancelled():raise RenderCancelled('Voice take cancelled before execution')
        need(bundle(studio)==plan['bundle'],'Voice runtime bundle changed since Prepare')
        observed=observed_versions(studio,plan['bundle']['python'],plan['bundle']['versions'])
        _require_versions(plan['bundle']['versions'],observed,plan.get('observed_versions'))
        runner=studio.root/'scripts/kokoro_baseline.py';need(file_hash(runner)==plan['runner_sha256'] and file_hash(plan['ffmpeg'])==plan['ffmpeg_sha256'],'Voice tools changed since Prepare')
        need(shutil.disk_usage(directory).free>=2*1024**3,'Voice take needs 2 GiB free')
        request={k:plan[k] for k in ('speaker_id','lines','bundle')};studio._write_json_atomic(directory/'request.json',request)
        job={'id':job_id,'operation':OPERATION,'project_id':identifier,'status':'running','created_at':time.time(),'preset_id':'voice-baseline','preset_name':plan['name'],
              'controls':{},'batch_count':0,'prompt_ids':[],'submissions':[],'parent_assets':[],'references':[],'graph':{},'graph_path':'','outputs':[],
              'native_recipe':request,'publication_status':'publishing','message':'Generating a CPU baseline take; no accepted custom identity.'}
        (studio.runs/job_id).mkdir(exist_ok=True);studio._save(job);studio.jobs[job_id]=job
        _run_owned([plan['bundle']['python'],str(runner),'--request',str(directory/'request.json'),'--output',str(out)],directory/'voice.log',180,cancelled)
        receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'));need([r['id'] for r in receipt['lines']]==[r['id'] for r in plan['lines']],'Voice receipt line IDs differ')
        command=[plan['ffmpeg'],'-hide_banner','-nostdin','-loglevel','error','-n']
        for line in receipt['lines']:
            source=safe_path(out,line['id']+'.wav');need(file_hash(source)==line['sha256'],'Dry take changed')
            with wave.open(str(source),'rb') as w:need(w.getframerate()==24000 and w.getsampwidth()==2 and w.getnchannels()==1 and w.getnframes()==line['samples'],'Invalid dry voice WAV')
            command+=['-f','wav','-i',str(source)]
        for i,line in enumerate(receipt['lines']):command+=['-map',f'{i}:a:0','-ar','48000','-ac','1','-c:a','pcm_s16le',str(out/(line['id']+'-scene.wav'))]
        _run_owned(command,directory/'resample.log',60,cancelled)
        if cancelled():raise RenderCancelled('Voice take cancelled before publication')
        qc={}
        for line in receipt['lines']:
            preview=out/(line['id']+'-scene.wav');qc[line['id']]=inspect_wav(preview)
            need(qc[line['id']]['samples']==line['samples']*2,'Voice interchange sample count differs')
            for name in (line['id']+'.wav',line['id']+'-scene.wav'):
                job['outputs'].append({'filename':name,'native_path':'voice/'+name,'type':'output','media_type':'audio'})
        if cancelled():raise RenderCancelled('Voice take cancelled before Workspace publication')
        job['native_recipe'].update(receipt=receipt,qc=qc)
        studio._save(job);studio.jobs[job_id]=job
        studio.index_outputs(job)
        published=bool(job['outputs']) and all(output.get('asset_id') and not output.get('snapshot_error') for output in job['outputs'])
        need(published,'Voice output registration failed; inspect retained files')
        production.finish_voice(identifier,job,qc)
    except Exception as exc:
        status='cancelled' if isinstance(exc,RenderCancelled) else 'failed'
        if job is not None:
            job.update(status=status,publication_status=status,message=str(exc)[:500]);studio.jobs[job_id]=job;studio._save(job)
        if attempt_started:production._attempt(identifier,0,status=status,finished_at=time.time(),message=str(exc)[:500])
        production._mutate(identifier,status=status,message=str(exc)[:500],artifacts=artifacts(production,identifier),finished_at=time.time())
