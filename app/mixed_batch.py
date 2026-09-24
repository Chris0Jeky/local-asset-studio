"""Explicit recovery of a known submission prefix and one unresolved POST.

The shared worker may read known history, but cannot resubmit the unknown POST.
A local disposition retains the marker and every reservation. All commands bind
an exact snapshot and a caller request identity; no read grants execution consent.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import quote

MAX_OBSERVATIONS = 64


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _evidence(job):
    # Queue/status transitions belong to this command, not to the immutable
    # submission evidence it was authorized to inspect.
    return _hash({k:v for k,v in job.items() if k not in ('status','message','mixed_batch_recovery','abandonment','put_away_at')})


def _shape(job):
    ids=job.get('prompt_ids');receipts=job.get('submissions');pending=job.get('pending_submission');count=job.get('batch_count')
    if type(count) is not int or not 2 <= count <= 4:raise ValueError('Mixed batch count is not supported')
    if type(ids) is not list or not 0 < len(ids) < count or not all(type(i) is str and i.strip() for i in ids):
        raise ValueError('Mixed batch has no consistent known prompt prefix')
    if len(set(ids))!=len(ids) or type(receipts) is not list or len(receipts)!=len(ids):
        raise ValueError('Mixed batch receipt identities are inconsistent')
    for index,(identifier,receipt) in enumerate(zip(ids,receipts)):
        if (not isinstance(receipt,dict) or type(receipt.get('index')) is not int or receipt['index']!=index
                or receipt.get('prompt_id')!=identifier or receipt.get('status') not in ('observing','completed','failed')
                or not isinstance(receipt.get('graph'),dict) or not receipt['graph']):
            raise ValueError('Mixed batch receipts must be a contiguous retained prefix')
    if (not isinstance(pending,dict) or type(pending.get('index')) is not int or pending['index']!=len(ids)
            or not isinstance(pending.get('graph'),dict) or not pending['graph']):
        raise ValueError('Unknown submission marker is incomplete or inconsistent; inspect retained files')
    if type(job.get('outputs')) is not list or not all(isinstance(o,dict) for o in job['outputs']):
        raise ValueError('Retained outputs are inconsistent')
    recovery=job.get('mixed_batch_recovery',{'version':1,'history':[]})
    if (not isinstance(recovery,dict) or recovery.get('version')!=1 or type(recovery.get('history')) is not list
            or not all(isinstance(r,dict) for r in recovery['history'])):
        raise ValueError('Mixed batch recovery history is invalid')
    history=recovery['history']
    if len(history)>MAX_OBSERVATIONS+1:raise ValueError('Mixed batch recovery history exceeds its limit')
    seen=set()
    for index,record in enumerate(history):
        identifier=record.get('request_id');action=record.get('action')
        if (not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',identifier) or identifier in seen
                or action not in ('observe','dispose') or record.get('new_work_authorized') is not False
                or any(not isinstance(record.get(k),str) or not re.fullmatch(r'[0-9a-f]{64}',record[k])
                       for k in ('request_sha256','expected_revision','evidence_sha256'))
                or record.get('status') not in (('queued','running','finished') if action=='observe' else ('recorded',))
                or action=='dispose' and index!=len(history)-1):
            raise ValueError('Mixed batch recovery history is invalid')
        seen.add(identifier)
    return receipts,pending,history


def snapshot(job):
    if not isinstance(job,dict) or 'pending_submission' not in job or not job.get('prompt_ids'):return None
    result={'version':1,'can_observe':False,'can_dispose':False}
    try:
        receipts,pending,history=_shape(job)
        result.update(revision=_hash(job),known=[{k:s[k] for k in ('index','prompt_id','status')} for s in receipts],
                      unknown_index=pending['index'],never_submitted_count=job['batch_count']-pending['index']-1,
                      last_observation=next((copy.deepcopy(r) for r in reversed(history) if r['action']=='observe'),None))
        inactive=job.get('status')=='uncertain' and 'abandonment' not in job
        result.update(can_observe=inactive and len(history)<MAX_OBSERVATIONS,can_dispose=inactive)
        result['message']='The later submission remains unknown. Known results and never-submitted remainder are separate; no automatic retry is permitted.'
        if inactive and len(history)>=MAX_OBSERVATIONS:result['message']='Observation history limit reached; preserve the evidence or explicitly abandon this batch locally.'
    except (ValueError,TypeError,KeyError) as exc:result['message']=str(exc)
    return result


def _commit(studio,job,prospective):
    # The single state publication is the commit point. Do not rewrite the
    # original recipe/workflow or mutate in-memory receipts before it succeeds.
    studio._write_json_atomic(studio.runs/job['id']/'state.json',{k:v for k,v in prospective.items() if k!='graph'})
    job.update(prospective)


def _request(payload,action):
    if not isinstance(payload,dict):raise ValueError('Mixed batch command must be an object')
    allowed={'request_id','expected_revision'} | ({'reason','acknowledge_unknown'} if action=='dispose' else set())
    if set(payload)-allowed:raise ValueError('Unsupported mixed batch command field')
    request_id=payload.get('request_id');revision=payload.get('expected_revision')
    if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request_id):raise ValueError('A stable request_id of 8 to 80 characters is required')
    if not isinstance(revision,str) or not re.fullmatch(r'[0-9a-f]{64}',revision):raise ValueError('Read the current mixed batch revision first')
    if action=='dispose':
        reason=payload.get('reason')
        if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:raise ValueError('Give a local disposition reason of 1 to 1000 characters')
        if payload.get('acknowledge_unknown') is not True:raise ValueError('Acknowledge all unresolved remote outcomes; this does not cancel remote work')
    return request_id,_hash({'action':action,'payload':payload})


def command(studio,job_id,action,payload):
    if action not in ('observe','dispose'):raise ValueError('Unknown mixed batch command')
    request_id,request_hash=_request(payload,action)
    with studio.lock:
        job=studio.jobs.get(job_id)
        if job is None:raise ValueError('Unknown job')
        receipts,pending,history=_shape(job)
        previous=next((r for r in history if r.get('request_id')==request_id),None)
        if previous:
            if previous.get('request_sha256')!=request_hash:raise ValueError('This request_id already identifies a different command')
            return studio.public(job)
        if payload['expected_revision']!=_hash(job):raise ValueError('Mixed batch evidence changed; refresh before issuing a new command')
        if job.get('status')!='uncertain' or 'abandonment' in job:raise ValueError('Only an inactive uncertain mixed batch can be changed')
        if action=='observe':
            studio.require_worker_observation()
            if studio.backends.busy:raise ValueError('Wait for the backend switch to finish')
            if len(history)>=MAX_OBSERVATIONS:raise ValueError('Observation history limit reached; all prior evidence is retained')
        record={'request_id':request_id,'request_sha256':request_hash,'expected_revision':payload['expected_revision'],
                'action':action,'recorded_at':time.time(),'status':'queued' if action=='observe' else 'recorded',
                'new_work_authorized':False,'evidence_sha256':_evidence(job)}
        prospective=copy.deepcopy(job)
        prospective['mixed_batch_recovery']={'version':1,'history':copy.deepcopy(history)+[record]}
        if action=='observe':
            prospective.update(status='queued',message='Queued to check known batch receipts only. The unknown submission will not be repeated.')
        else:
            record['reason']=payload['reason'].strip()
            disposition={'basis':'mixed_batch_unknown','reason':record['reason'],'recorded_at':record['recorded_at'],
                         'event_id':request_id,'acknowledged_unknown':True,'remote_cancelled':False,'new_work_authorized':False,
                         'known':[{k:s[k] for k in ('index','prompt_id','status')} for s in receipts],
                         'unknown_index':pending['index'],'pending_sha256':_hash(pending),
                         'never_submitted_count':job['batch_count']-pending['index']-1}
            prospective.update(status='abandoned',abandonment=disposition,
                               message='Batch abandoned locally. Unresolved remote outcomes remain unknown; no remote work was cancelled. Outputs, receipts and reservations are retained. New work requires an explicit repair branch.')
        _commit(studio,job,prospective)
        if action=='observe':studio.queue.put(('observe-mixed',(job_id,request_id)))
        return studio.public(job)


def _history(response,submission):
    """Require explicit terminal evidence; malformed or absent history is unknown."""
    if not isinstance(response,dict):raise ValueError('Invalid history response')
    history=response.get(submission['prompt_id'])
    if history is None:return 'observing',[],'No retained history was returned'
    if not isinstance(history,dict) or not isinstance(history.get('status'),dict):raise ValueError('Invalid prompt history')
    status=history['status'];state=status.get('status_str')
    if state=='success' and status.get('completed') is True:outcome='completed'
    elif state=='error' and status.get('completed') is False and any(isinstance(m,list) and len(m)>1 and m[0]=='execution_error' and isinstance(m[1],dict) for m in status.get('messages',[])):
        outcome='failed'
    else:return 'observing',[],'History does not establish a terminal outcome'
    nodes=history.get('outputs',{})
    if not isinstance(nodes,dict):raise ValueError('Invalid history outputs')
    outputs=[]
    for node in nodes.values():
        if not isinstance(node,dict):raise ValueError('Invalid output node')
        for kind in ('images','gifs','videos','audio','3d'):
            collection=node.get(kind,[])
            if not isinstance(collection,list):raise ValueError('Invalid output collection')
            for output in collection:
                if not isinstance(output,dict) or not isinstance(output.get('filename'),str) or not output['filename']:
                    raise ValueError('Invalid output descriptor')
                if not isinstance(output.get('subfolder',''),str) or output.get('type') not in ('output','temp'):
                    raise ValueError('Invalid output location')
                ext=Path(output['filename']).suffix.lower()
                media_type='video' if ext in ('.mp4','.webm','.mov') else '3d' if ext in ('.glb','.gltf','.obj','.ply','.stl') else 'audio' if ext in ('.mp3','.wav','.flac') else 'image'
                outputs.append(dict(filename=output['filename'],subfolder=output.get('subfolder',''),type=output['type'],
                                    seed=submission.get('seed'),prompt_id=submission['prompt_id'],media_type=media_type))
                if len(outputs)>1024:raise ValueError('History output limit exceeded; inspect the retained prompt directly')
    return outcome,outputs,'Terminal history observed for this known prompt only'


def run(studio,job_id,request_id):
    """One bounded read per unresolved known ID, on the existing Studio worker."""
    with studio.lock:
        job=studio.jobs.get(job_id)
        if job is None:return
        receipts,pending,history=_shape(job)
        record=history[-1] if history else {}
        if job.get('status')!='queued' or record.get('request_id')!=request_id or record.get('status')!='queued' or 'abandonment' in job:return
        if record.get('evidence_sha256')!=_evidence(job):raise ValueError('Mixed batch evidence changed before observation; no history was requested')
        prospective=copy.deepcopy(job);active=prospective['mixed_batch_recovery']['history'][-1]
        active.update(status='running',observations=[])
        prospective.update(status='running',message='Reading known batch history only; the later submission remains unknown.')
        _commit(studio,job,prospective)
        unresolved=[copy.deepcopy(s) for s in receipts if s['status']=='observing']
        pending_hash=_hash(pending)
    for submission in unresolved:
        with studio.lock:read_revision=_hash(job)
        try:
            response=studio._request('/history/'+quote(submission['prompt_id'],safe=''),timeout=15,base_url=job.get('comfy_url'))
            outcome,outputs,message=_history(response,submission)
        except Exception as exc:
            outcome,outputs,message='observing',[],type(exc).__name__+': '+str(exc)[:300]
        with studio.lock:
            # Refuse stale completions, even if an external local edit changed the
            # evidence while a GET was in flight. Never overwrite a disposition.
            _,current_pending,current_history=_shape(job)
            if (_hash(job)!=read_revision or job.get('status')!='running' or 'abandonment' in job or _hash(current_pending)!=pending_hash
                    or current_history[-1].get('request_id')!=request_id):
                raise ValueError('Mixed batch changed during observation; results were not applied')
            prospective=copy.deepcopy(job)
            target=prospective['submissions'][submission['index']]
            if target['prompt_id']!=submission['prompt_id'] or target['status']!='observing':raise ValueError('Known receipt changed during observation')
            target['status']=outcome
            for output in outputs:
                if not any(all(o.get(k)==output.get(k) for k in ('filename','subfolder','type','prompt_id')) for o in prospective['outputs']):
                    prospective['outputs'].append(output)
            prospective['mixed_batch_recovery']['history'][-1]['observations'].append(
                {'index':submission['index'],'prompt_id':submission['prompt_id'],'status':outcome,'message':message})
            _commit(studio,job,prospective)
    # Materialization follows durable descriptors. If indexing fails, a new
    # explicit check can retry only indexing, never an already-terminal prompt.
    with studio.lock:
        index_revision=_hash(job);prospective=copy.deepcopy(job)
    studio.index_outputs(prospective)
    with studio.lock:
        if _hash(job)!=index_revision:raise ValueError('Mixed batch changed during output indexing; job state was not overwritten')
        prospective['mixed_batch_recovery']['history'][-1].update(status='finished',finished_at=time.time())
        prospective.update(status='uncertain',message='Known batch receipts checked. The later submission is still unknown; no duplicate or later output was submitted. Inspect results or explicitly abandon the unresolved remainder locally.')
        _commit(studio,job,prospective)


def record_failure(studio,job,exc):
    """Only publish local recovery state; original source files stay byte-exact."""
    with studio.lock:
        prospective=copy.deepcopy(job)
        if job.get('status') not in ('abandoned','completed','partial','failed'):
            prospective.update(status='uncertain',message='Known batch observation or recording failed; remote outcomes remain unknown. Nothing was resubmitted: '+str(exc)[:300])
        _commit(studio,job,prospective)


def disposed(job):
    """A recorded LOCAL disposition; never proof of remote termination."""
    if not isinstance(job,dict) or job.get('status')!='abandoned':return False
    try:
        receipts,pending,history=_shape(job);record=job.get('abandonment',{})
        return (record.get('basis')=='mixed_batch_unknown' and record.get('acknowledged_unknown') is True
                and record.get('remote_cancelled') is False and record.get('new_work_authorized') is False
                and record.get('pending_sha256')==_hash(pending)
                and record.get('known')==[{k:s[k] for k in ('index','prompt_id','status')} for s in receipts]
                and bool(history) and history[-1].get('evidence_sha256')==_evidence(job)
                and history[-1].get('action')=='dispose' and history[-1].get('request_id')==record.get('event_id'))
    except (ValueError,TypeError,KeyError):return False
