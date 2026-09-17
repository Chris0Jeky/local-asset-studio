"""Durable, single-attempt reference analysis on the existing Studio worker.

SQLite is the existing Workspace's database. No extra queue, thread, server,
model installer or asset store. Unknown inference outcomes retain a resource hold.
"""
from __future__ import annotations
import copy
import hashlib
from http.client import HTTPException
import re
import threading
import time
from .schema import canonical, decode, digest, fields, need
from .reference_analysis import validate_request, make_report, validate_report
from .reference_vision import request_payload
from .reference_review import _images
from .local_helper import http_json

MAX_JOBS = 64
MAX_BYTES = 128 * 1024 * 1024
PAYLOAD_LIMIT = 16 * 1024 * 1024
ACTIVE = ('queued', 'preparing', 'submitting')
CONFIG_FIELDS = ('model', 'model_digest', 'port', 'min_available_ram_bytes',
                 'min_commit_headroom_bytes', 'min_free_vram_bytes', 'timeout_seconds')


def configuration(studio):
    value = studio.config.get('reference_helper')
    need(type(value) is dict, 'Configure an installed local reference_helper in config/local.json before analyzing')
    fields(value, CONFIG_FIELDS)
    need(type(value['model']) is str and re.fullmatch(r'[A-Za-z0-9_./:-]{1,160}', value['model'])
         and 'cloud' not in value['model'].lower() and '://' not in value['model'], 'An installed local model name is required')
    need(type(value['model_digest']) is str and re.fullmatch('[a-f0-9]{64}',value['model_digest']), 'Pin the installed helper model digest')
    for key, low, high in [('port',1024,65535), ('timeout_seconds',1,180),
            *[(k,1,2**50) for k in CONFIG_FIELDS if k.startswith('min_')]]:
        need(type(value[key]) is int and low <= value[key] <= high, 'Invalid helper configuration: '+key)
    return copy.deepcopy(value)


def resources(studio):
    """Fresh independent physical RAM, Windows commit and Comfy device readings."""
    import psutil
    import host_memory
    stats = studio._request('/system_stats', timeout=5)
    devices = stats.get('devices') if type(stats) is dict else None
    # A multi-device or unavailable observation is not the configured Radeon.
    free = devices[0].get('vram_free') if type(devices) is list and len(devices)==1 and type(devices[0]) is dict else None
    return {'available_ram_bytes':psutil.virtual_memory().available,
            'commit_headroom_bytes':host_memory.read().get('available_bytes'), 'free_vram_bytes':free}


class ReferenceJobs:
    def __init__(self, studio):
        self.studio=studio; self.workspace=studio.assets; self.intake=threading.Lock(); self.failure_hold=False
        with self.workspace.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS reference_jobs_v1(
                id TEXT PRIMARY KEY, request_sha TEXT NOT NULL, request TEXT NOT NULL,
                payload TEXT NOT NULL, payload_sha TEXT NOT NULL, context TEXT NOT NULL,
                state TEXT NOT NULL, state_sha TEXT NOT NULL, result TEXT, bytes INTEGER NOT NULL);''')
            db.execute('BEGIN IMMEDIATE')
            for row in db.execute('SELECT id,state,state_sha FROM reference_jobs_v1').fetchall():
                state=self._state(row)
                if state['status'] in ACTIVE:
                    pending=state['resource_hold']
                    state.update(status='uncertain' if pending else 'cancelled',
                        message='Studio restarted. No analysis was replayed; inspect the retained operation.',updated_at=time.time())
                    self._save_state(db,row['id'],state)

    @staticmethod
    def _state(row):
        state=decode(row['state'].encode())
        need(digest(state)==row['state_sha'] and type(state.get('resource_hold')) is bool
             and type(state.get('inference_attempts')) is int and state['inference_attempts'] in (0,1)
             and state.get('status') in (*ACTIVE,'completed','failed','uncertain','cancelled'), 'Stored reference state failed integrity checks')
        return state

    @staticmethod
    def _save_state(db,key,state):
        need(len(canonical(state))<=8192,'Reference state exceeds 8 KiB')
        db.execute('UPDATE reference_jobs_v1 SET state=?,state_sha=? WHERE id=?',(canonical(state).decode(),digest(state),key))

    def busy(self, holds_only=False):
        if self.failure_hold:return True
        with self.workspace.connection() as db:
            states=[self._state(row) for row in db.execute('SELECT state,state_sha FROM reference_jobs_v1')]
        return any(s['resource_hold'] or (not holds_only and s['status'] in ACTIVE) for s in states)

    def require_available(self):
        need(not self.busy(holds_only=True), 'Reference analysis may still own resources. Inspect its operation and release the hold before starting work.')

    def capabilities(self):
        with self.workspace.connection() as db:
            db.execute('BEGIN');scope=self.workspace._workspace_id(db)
            recent=[{'request_id':row['id'],**{k:v for k,v in self._state(row).items() if k in ('status','resource_hold','updated_at')}}
                    for row in db.execute('SELECT id,state,state_sha FROM reference_jobs_v1')]
            recent=sorted(recent,key=lambda x:x['updated_at'],reverse=True)[:8]
        try:config=configuration(self.studio);enabled=True;message='Analyze with the configured local model; one call through the Studio worker.'
        except ValueError as exc:config=None;enabled=False;message=str(exc)
        return {'format':'studio.reference-jobs/v1','workspace_id':scope,'enabled':enabled,
                'model':config['model'] if config else None,'message':message,'busy':self.busy(),'recent':recent,
                'limits':{'references':4,'retained_operations':MAX_JOBS,'retained_bytes':MAX_BYTES},'generation_submitted':False}

    def _row(self,db,key):
        self.workspace.request_id(key)
        row=db.execute('SELECT * FROM reference_jobs_v1 WHERE id=?',(key,)).fetchone()
        need(row is not None,'Unknown analysis request; nothing was replayed')
        return row

    def _public(self,db,row):
        result=decode(row['result'].encode()) if row['result'] else None
        state=self._state(row)
        if result is not None:
            need(digest(result)==state['result_sha256'], 'Stored analysis result failed integrity checks')
            validate_report(result['analysis'])
        return {'format':'studio.reference-job/v1','workspace_id':self.workspace._workspace_id(db),
                'request_id':row['id'],'request':decode(row['request'].encode()),
                'state':state,'state_sha256':row['state_sha'],'result':result,'generation_submitted':False}

    def get(self,scope,key):
        self.workspace._validate_scope(scope)
        with self.workspace.connection() as db:
            db.execute('BEGIN');self.workspace._check_scope(db,scope)
            return self._public(db,self._row(db,key))

    def _runtime(self):
        s=self.studio
        need(not s.backends.busy,'A backend operation is active')
        return {'backend':s.backends.active,'endpoint':s.comfy_url,'root':str(s.comfy_root)}

    def create(self,value):
        need(self.intake.acquire(blocking=False), 'Reference intake is already busy')
        try:return self._create(value)
        finally:self.intake.release()

    def _create(self,value):
        """Called with the intake lock, before any expensive image decoding."""
        fields(value,('workspace_id','request_id','request','images'))
        self.workspace._validate_scope(value['workspace_id']);self.workspace.request_id(value['request_id'])
        q=validate_request(value['request']);raw=canonical(value)
        need(len(raw)<=48*1024*1024,'Analysis request exceeds 48 MiB');sha=hashlib.sha256(raw).hexdigest();del raw
        with self.studio.lock:
            with self.workspace.connection() as db:
                self.workspace._check_scope(db,value['workspace_id'])
                old=db.execute('SELECT * FROM reference_jobs_v1 WHERE id=?',(value['request_id'],)).fetchone()
                if old:
                    need(not self._state(old).get('retired_without_dispatch'), 'This analysis request was retired before dispatch; use a new request ID')
                    need(old['request_sha']==sha,'Request ID already has different content')
                    return self._public(db,old)
            self.studio.require_worker();need(not self.busy(),'An analysis is already outstanding; inspect it first')
            config=configuration(self.studio);runtime=self._runtime()
        originals=_images({'request':q},value['images'])
        payload,inputs=request_payload(q,config['model'],source_bytes=originals);del originals
        serialized=canonical(payload);need(len(serialized)<=PAYLOAD_LIMIT,'Prepared helper request exceeds 16 MiB')
        context={'configuration':config,'runtime':runtime,'analysis_inputs':inputs}
        state={'status':'queued','resource_hold':False,'inference_attempts':0,'response_done':False,
               'message':'Queued for reference analysis, not image generation.','updated_at':time.time(),
               'request_sha256':digest(q),'context_sha256':digest(context),'result_sha256':None}
        size=len(serialized)+len(canonical(q))+len(canonical(context))+1024*1024+8192  # Reserve a bounded result before any call.
        with self.studio.lock:
            self.studio.require_worker();need(config==configuration(self.studio) and runtime==self._runtime(),'Helper context changed during capture')
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');self.workspace._check_scope(db,value['workspace_id'])
                old=db.execute('SELECT * FROM reference_jobs_v1 WHERE id=?',(value['request_id'],)).fetchone()
                if old:
                    need(not self._state(old).get('retired_without_dispatch'), 'This analysis request was retired before dispatch; use a new request ID')
                    need(old['request_sha']==sha,'Request ID already has different content');return self._public(db,old)
                states=[self._state(row) for row in db.execute('SELECT state,state_sha FROM reference_jobs_v1')]
                need(not any(s['resource_hold'] or s['status'] in ACTIVE for s in states),'An analysis is already outstanding')
                count,used=db.execute('SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM reference_jobs_v1').fetchone()
                need(count<MAX_JOBS and used+size<=MAX_BYTES,'Reference operation history is full; no history was removed')
                db.execute('INSERT INTO reference_jobs_v1 VALUES(?,?,?,?,?,?,?,?,?,?)',(
                    value['request_id'],sha,canonical(q).decode(),serialized.decode(),digest(payload),canonical(context).decode(),
                    canonical(state).decode(),digest(state),None,size))
            self.studio.queue.put(('reference-analysis',value['request_id']))
            return self.get(value['workspace_id'],value['request_id'])

    def _idle(self):
        need(not any(
            job.get('status') in ('submitting','running')
            or (job.get('status') == 'uncertain' and not self.studio._tracking_stopped(job))
            for job in self.studio.jobs.values()
        ), 'Reconcile existing generation work before reference analysis')
        queue=self.studio._request('/queue',timeout=5)
        need(type(queue) is dict and all(type(queue.get(k)) is list and not queue[k] for k in ('queue_running','queue_pending')),
             'Comfy queue is busy or unknown; no helper inference started')

    @staticmethod
    def _empty(config):
        status=http_json(config['port'],'GET','/api/ps',timeout=5)
        return type(status) is dict and type(status.get('models')) is list and not status['models']

    def _admit(self,context):
        config=context['configuration']
        need(config==configuration(self.studio) and context['runtime']==self._runtime(),'Helper or backend configuration changed after queueing')
        self._idle()
        listing=http_json(config['port'],'GET','/api/tags',timeout=5)
        need(type(listing) is dict and type(listing.get('models')) is list,'Invalid helper inventory')
        matches=[x for x in listing['models'] if type(x) is dict and config['model'] in (x.get('name'),x.get('model'))]
        need(len(matches)==1 and matches[0].get('digest')==config['model_digest'] and not matches[0].get('remote_host')
             and not matches[0].get('remote_model'),'The pinned local model is absent or changed; nothing was downloaded')
        need(self._empty(config),'Another helper model is resident; use a dedicated idle helper')

    def _resources(self,config):
        reading=resources(self.studio)
        for observed,required in [('available_ram_bytes','min_available_ram_bytes'),('commit_headroom_bytes','min_commit_headroom_bytes'),('free_vram_bytes','min_free_vram_bytes')]:
            value=reading.get(observed)
            need(type(value) is int and value>=config[required], 'Insufficient or unknown '+observed+'; configured threshold '+str(config[required]))
        return {**reading,'observed_at':time.time()}

    def run(self,key):
        """Called only from Studio._work. Duplicate queue deliveries never re-infer."""
        try:
            with self.studio.lock:
                with self.workspace.connection() as db:
                    db.execute('BEGIN IMMEDIATE');row=self._row(db,key);state=self._state(row)
                    if state['status']!='queued':return
                    q=decode(row['request'].encode());payload=decode(row['payload'].encode(),limit=PAYLOAD_LIMIT)
                    need(digest(payload)==row['payload_sha'],'Stored model request changed')
                    context=decode(row['context'].encode())
                    need(digest(q)==state['request_sha256'] and digest(context)==state['context_sha256'], 'Stored analysis context changed')
                    validate_request(q)
                    state.update(status='preparing',message='Checking fresh resources and the pinned local helper.',updated_at=time.time())
                    self._save_state(db,key,state)
            self._admit(context)
            with self.studio.lock:
                need(context['runtime']==self._runtime() and context['configuration']==configuration(self.studio),'Helper context changed before dispatch')
                self._idle()  # Recheck after helper inventory/residency observations.
                reading=self._resources(context['configuration'])
                with self.workspace.connection() as db:
                    db.execute('BEGIN IMMEDIATE');state=self._state(self._row(db,key))
                    if state['status']!='preparing':return
                    state.update(status='submitting',resource_hold=True,inference_attempts=1,
                        resources=reading,message='Analyzing references. Closing this page does not cancel the local model.',updated_at=time.time())
                    self._save_state(db,key,state)
            config=context['configuration']
            reply=http_json(config['port'],'POST','/api/chat',payload,timeout=config['timeout_seconds'])
            need(type(reply) is dict and reply.get('done') is True,'Incomplete helper response; remote outcome remains uncertain')
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');state=self._state(self._row(db,key));state['response_done']=True;self._save_state(db,key,state)
            answer=decode(reply['message']['content'].encode())
            report=make_report(q,answer,context['analysis_inputs'])
            result={'analysis':report,'helper_evidence':{'provider':'ollama-studio-worker','model':config['model'],
                'model_digest':config['model_digest'],'request_sha256':digest(payload),'inference_calls':1,
                'image_count':len(q['references']),'generation_submitted':False}}
            result_raw=canonical(result);need(len(result_raw)<=1024*1024,'Analysis result exceeds reserved storage')
            try:released=self._empty(config)
            except (OSError,ValueError,HTTPException):released=False
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');state=self._state(self._row(db,key))
                state.update(status='completed',resource_hold=not released,result_sha256=digest(result),
                    message='Analysis ready for review.'+(' Resource release is still unconfirmed; inspect the hold.' if not released else ''),updated_at=time.time())
                db.execute('UPDATE reference_jobs_v1 SET result=? WHERE id=?',(result_raw.decode(),key));self._save_state(db,key,state)
        except Exception as exc:self.record_failure(key,exc)

    def record_failure(self,key,exc):
        try:
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');state=self._state(self._row(db,key))
                state.update(status='uncertain' if state['resource_hold'] and not state['response_done'] else 'failed',
                    message=str(exc)[:500]+'. Nothing was replayed.',updated_at=time.time())
                self._save_state(db,key,state)
        except Exception:
            # A failed journal write cannot release a client whose remote work may live.
            self.failure_hold=True
            raise


    def retire(self,value):
        """Fence a never-created ID; an existing operation is only observed.

        The commit is the no-late-arrival boundary. A 404 alone cannot establish
        that a slow create will never arrive. This action never cancels a model.
        """
        fields(value,('workspace_id','request_id'))
        self.workspace._validate_scope(value['workspace_id']);self.workspace.request_id(value['request_id'])
        with self.studio.lock:
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');self.workspace._check_scope(db,value['workspace_id'])
                old=db.execute('SELECT * FROM reference_jobs_v1 WHERE id=?',(value['request_id'],)).fetchone()
                if old:return self._public(db,old)
                count,used=db.execute('SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM reference_jobs_v1').fetchone()
                need(count<MAX_JOBS and used+8192<=MAX_BYTES,'Reference operation history is full; no history was removed')
                state={'status':'cancelled','resource_hold':False,'inference_attempts':0,'response_done':False,
                    'retired_without_dispatch':True,'message':'Request retired before creation. A late arrival cannot start analysis.',
                    'updated_at':time.time(),'request_sha256':digest({}),'context_sha256':digest({}),'result_sha256':None}
                db.execute('INSERT INTO reference_jobs_v1 VALUES(?,?,?,?,?,?,?,?,?,?)',(
                    value['request_id'],digest({'retired_without_dispatch':value}),'{}','{}',digest({}),'{}',
                    canonical(state).decode(),digest(state),None,8192))
                return self._public(db,self._row(db,value['request_id']))

    def _command(self,value,action):
        fields(value,('workspace_id','request_id','expected_state_sha256')+(('acknowledge_unknown',) if action=='release' else ()))
        self.workspace._validate_scope(value['workspace_id'])
        if action=='release':need(type(value['acknowledge_unknown']) is bool,'Explicit acknowledgement must be boolean')
        with self.studio.lock:
            with self.workspace.connection() as db:
                db.execute('BEGIN');self.workspace._check_scope(db,value['workspace_id'])
                row=self._row(db,value['request_id']);state=self._state(row)
                need(row['state_sha']==value['expected_state_sha256'],'Analysis state changed; inspect it before acting')
                context=decode(row['context'].encode())
            if action=='cancel':
                need(state['status']=='queued','Only a queued, never-dispatched analysis can be cancelled')
                state.update(status='cancelled',message='Cancelled before helper dispatch; zero inference calls.')
            else:
                need(state['resource_hold'] and state['status'] not in ACTIVE,'Analysis is still active or has no held resources')
                need(state['response_done'] or value['acknowledge_unknown'],
                     'A lost reply is not cancellation. Confirm the specific helper call has stopped before releasing.')
                need(context['configuration']==configuration(self.studio),'Return to the recorded helper configuration before release')
                # Network observations never hold a Workspace write transaction.
                self._idle();need(self._empty(context['configuration']),'Helper residency is not empty; hold retained')
                state.update(resource_hold=False,release_acknowledged_unknown=not state['response_done'],
                             message='Resource hold explicitly released; the previous inference outcome is unchanged. No call was repeated.')
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');self.workspace._check_scope(db,value['workspace_id'])
                current=self._row(db,value['request_id'])
                need(current['state_sha']==value['expected_state_sha256'],'Analysis state changed; inspect it before acting')
                state['updated_at']=time.time();self._save_state(db,row['id'],state)
                return self._public(db,self._row(db,row['id']))

    def cancel(self,value):return self._command(value,'cancel')
    def release(self,value):return self._command(value,'release')
