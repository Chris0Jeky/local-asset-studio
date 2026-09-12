"""Explicit, pinned CPU voice takes on the existing Production coordinator."""
from __future__ import annotations
import json
from pathlib import Path
import re
import shutil
import time
import uuid
import wave
from studio_av.project import file_hash,need,fields,number,safe_path
from studio_av.render import _run_owned,RenderCancelled,inspect_wav

OPERATION='native.voice-baseline.v1'


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
    pinned=bundle(production.studio);ffmpeg=production.studio.config.get('ffmpeg','');need(Path(ffmpeg).is_absolute() and Path(ffmpeg).is_file(),'Configure FFmpeg for scene interchange')
    runner=production.studio.root/'scripts/kokoro_baseline.py';need(runner.is_file(),'Voice runner unavailable')
    identifier=uuid.uuid4().hex;directory=production.root/identifier
    need(shutil.disk_usage(production.root).free>=2*1024**3,'Voice take needs 2 GiB free')
    from production import fingerprint
    plan={'version':1,'kind':'voice','name':payload['name'],'speaker_id':payload['speaker_id'],'lines':lines,'bundle':pinned,
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


def run(production,identifier,plan):
    studio=production.studio;directory=production.root/identifier;out=directory/'voice';job_id=uuid.uuid5(uuid.NAMESPACE_URL,'studio-voice:'+identifier).hex
    if (directory/'request.json').exists():
        production._mutate(identifier,status='interrupted',message='A prior voice attempt exists. Inspect retained files; prepare a new take to retry.');return
    def cancelled():return bool(production._get(identifier)['state'].get('stop_requested'))
    try:
        if cancelled():raise RenderCancelled('Voice take cancelled before execution')
        need(bundle(studio)==plan['bundle'],'Voice runtime bundle changed since Prepare')
        runner=studio.root/'scripts/kokoro_baseline.py';need(file_hash(runner)==plan['runner_sha256'] and file_hash(plan['ffmpeg'])==plan['ffmpeg_sha256'],'Voice tools changed since Prepare')
        need(shutil.disk_usage(directory).free>=2*1024**3,'Voice take needs 2 GiB free')
        request={k:plan[k] for k in ('speaker_id','lines','bundle')};studio._write_json_atomic(directory/'request.json',request)
        production._attempt(identifier,0,operation=OPERATION,job_id=job_id,status='running')
        job={'id':job_id,'operation':OPERATION,'project_id':identifier,'status':'running','created_at':time.time(),'preset_id':'voice-baseline','preset_name':plan['name'],
             'controls':{},'batch_count':0,'prompt_ids':[],'submissions':[],'parent_assets':[],'references':[],'graph':{},'graph_path':'','outputs':[],
             'native_recipe':request,'message':'Generating a CPU baseline take; no accepted custom identity.'}
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
        job.update(status='completed',message='Dry and scene-ready baseline takes completed; listening review remains open.')
        job['native_recipe'].update(receipt=receipt,qc=qc);studio.index_outputs(job)
        need(all(o.get('asset_id') and not o.get('snapshot_error') for o in job['outputs']),'Voice output registration failed; inspect retained files')
        studio._save(job);studio.jobs[job_id]=job
        production._mutate(identifier,status='completed',message=job['message'],artifacts=artifacts(production,identifier),measurements=qc,finished_at=time.time())
    except Exception as exc:
        status='cancelled' if isinstance(exc,RenderCancelled) else 'failed'
        if job_id in studio.jobs:
            studio.jobs[job_id].update(status=status,message=str(exc)[:500]);studio._save(studio.jobs[job_id])
        production._mutate(identifier,status=status,message=str(exc)[:500],artifacts=artifacts(production,identifier),finished_at=time.time())
