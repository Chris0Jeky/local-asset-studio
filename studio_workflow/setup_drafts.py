"""Revisioned Create drafts and copy-only proposal application in AssetWorkspace.

The request journal is committed before staging. A repeated request only observes
its original receipt. SQL guards drafts across clients; Studio.lock keeps this
server's backend selection and existing uploader stable. No model job is created.
"""
from __future__ import annotations
import copy
import hashlib
import re
from pathlib import Path
import sqlite3
import time
import uuid

from .commands import identifier
from .core import canonical, decode, digest, need
from .setup_proposal import validate_draft, validate_reply, request as build_proposal

PREFIX='/api/workflow-studio/setup-drafts'
MAX_DRAFTS=128
MAX_REVISIONS=256
MAX_STORAGE=128*1024*1024
MAX_COMMAND=1024*1024
MAX_OPERATIONS=1024
ACTIVE={'checking','staging'}
NAMESPACE=uuid.UUID('de53f52f-e6f1-4273-af30-bd6d352f6479')


class SetupError(ValueError):
    def __init__(self,code,message,status=409):
        super().__init__(message);self.code=code;self.status=status
    def result(self):
        return {'error':str(self),'code':self.code,'generation_submitted':False,
                'recovery':'Inspect the original request receipt. Never repeat a write with a new identity automatically.'}


def validate_command(value):
    need(type(value) is dict and len(canonical(value))<=MAX_COMMAND,'Supply a bounded setup command')
    value=decode(canonical(value));action=value.get('action')
    required={'action','workspace_id','request_id'}
    extra={'create':{'draft'},'replace':{'draft_id','expected_revision','draft'},
           'apply':{'draft_id','expected_revision','proposal_json','approved_proposal_sha256'},
           'restore':{'draft_id','expected_revision','revision'},'abandon':{'draft_id','expected_revision','operation_id'}}
    need(type(action) is str and action in extra and set(value)==required|extra[action],'Unsupported or incomplete setup command')
    need(type(value['workspace_id']) is str and re.fullmatch('[a-f0-9]{32}',value['workspace_id']),'Invalid Workspace identity')
    identifier(value['request_id'])
    if action!='create':
        identifier(value['draft_id'])
        need(type(value['expected_revision']) is int and 1<=value['expected_revision']<=MAX_REVISIONS,'Invalid expected setup revision')
    if action in ('create','replace'):value['draft']=validate_draft(value['draft'])
    if action=='restore':need(type(value['revision']) is int and 1<=value['revision']<=MAX_REVISIONS,'Invalid prior setup revision')
    if action=='abandon':identifier(value['operation_id'])
    if action=='apply':
        need(type(value['proposal_json']) is str and len(value['proposal_json'].encode())<=MAX_COMMAND,'Supply bounded reviewed proposal JSON')
        need(type(value['approved_proposal_sha256']) is str and re.fullmatch('[a-f0-9]{64}',value['approved_proposal_sha256']),'Invalid acknowledged proposal hash')
    return value


class SetupDrafts:
    def __init__(self,studio):
        self.studio=studio;self.workspace=studio.assets
        with self.workspace.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS setup_drafts_v1(id TEXT PRIMARY KEY,head INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS setup_versions_v1(
                    draft_id TEXT NOT NULL REFERENCES setup_drafts_v1(id), revision INTEGER NOT NULL,
                    record TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL,
                    PRIMARY KEY(draft_id,revision));
                CREATE TABLE IF NOT EXISTS setup_operations_v1(
                    request_id TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL, draft_id TEXT NOT NULL,
                    receipt TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS setup_operation_draft_v1 ON setup_operations_v1(draft_id);
            ''')

    def _runtime(self):
        s=self.studio
        need(not s.backends.busy,'An environment operation is active; inspect before applying a setup')
        return {'backend_id':s.backends.active,'endpoint':s.comfy_url,'root':str(s.comfy_root.resolve())}

    def _read(self,db,key,revision=None):
        identifier(key)
        if revision is not None:self._revision(revision)
        row=db.execute('''SELECT v.*,d.head FROM setup_drafts_v1 d JOIN setup_versions_v1 v
            ON v.draft_id=d.id AND v.revision=COALESCE(?,d.head) WHERE d.id=?''',(revision,key)).fetchone()
        if row is None:raise SetupError('setup_not_found','Setup draft or revision not found',404)
        record=decode(row['record'])
        need(digest(record)==row['sha256'],'Stored setup revision failed its integrity check; retain it for inspection')
        validate_draft(record['draft'])
        return {'draft_id':key,'revision':row['revision'],'head_revision':row['head'],**record,
                'draft_sha256':digest(record['draft']),'record_sha256':row['sha256'],'record_json':row['record'],
                'workspace_id':self.workspace._workspace_id(db),'generation_submitted':False}

    def get(self,key,revision=None):
        with self.workspace.connection() as db:return self._read(db,key,revision)

    def list(self):
        with self.workspace.connection() as db:
            rows=[dict(r) for r in db.execute('SELECT id AS draft_id,head AS revision FROM setup_drafts_v1 ORDER BY id')]
            return {'workspace_id':self.workspace._workspace_id(db),'drafts':rows,
                    'limits':{'drafts':MAX_DRAFTS,'revisions':MAX_REVISIONS,'storage_bytes':MAX_STORAGE},'generation_submitted':False}

    @staticmethod
    def _revision(value):need(type(value) is int and 1<=value<=MAX_REVISIONS,'Invalid setup revision')

    def _operation(self,db,key):
        row=db.execute('SELECT * FROM setup_operations_v1 WHERE request_id=?',(identifier(key),)).fetchone()
        if row is None:return None
        receipt=decode(row['receipt'])
        need(digest(receipt)==row['sha256'] and receipt['request_id']==key and receipt['draft_id']==row['draft_id'],
             'Stored setup receipt failed its integrity check; retain it for inspection')
        return row,receipt

    def recover(self,key):
        with self.workspace.connection() as db:
            previous=self._operation(db,key)
            if previous is None:raise SetupError('request_not_found','No receipt for this request; no write was repeated',404)
            return self._result(db,previous[1],True)

    def _result(self,db,receipt,replayed=False):
        result={**receipt,'receipt_json':canonical(receipt).decode(),'receipt_sha256':digest(receipt),'replayed':replayed,'workspace_id':self.workspace._workspace_id(db),'generation_submitted':False}
        if receipt.get('revision'):
            result.update(self._read(db,receipt['draft_id'],receipt['revision']))
        return result

    def _budget(self,db,extra):
        used=sum(db.execute(f'SELECT COALESCE(SUM(bytes),0) FROM {table}').fetchone()[0]
                 for table in ('setup_versions_v1','setup_operations_v1'))
        need(used+extra<=MAX_STORAGE,'Setup history budget reached; no history or source files were removed')

    def _save_receipt(self,db,receipt,request_sha):
        raw=canonical(receipt);old=db.execute('SELECT bytes FROM setup_operations_v1 WHERE request_id=?',(receipt['request_id'],)).fetchone()
        self._budget(db,len(raw)-(old[0] if old else 0))
        db.execute('''INSERT INTO setup_operations_v1 VALUES(?,?,?,?,?,?) ON CONFLICT(request_id)
            DO UPDATE SET receipt=excluded.receipt,sha256=excluded.sha256,bytes=excluded.bytes''',
            (receipt['request_id'],request_sha,receipt['draft_id'],raw.decode(),digest(receipt),len(raw)))

    def _guard(self,db,key,expected,owned=None):
        self._revision(expected);current=self._read(db,key)
        if current['revision']!=expected:raise SetupError('setup_revision_conflict','The shared setup revision changed; inspect before choosing what to keep')
        for row in db.execute('SELECT request_id FROM setup_operations_v1 WHERE draft_id=?',(key,)):
            _,receipt=self._operation(db,row['request_id'])
            if receipt['status'] in ACTIVE and row['request_id']!=owned:
                raise SetupError('setup_operation_pending','A setup operation is pending; inspect its original receipt before changing this draft')
        return current

    def _append(self,db,key,revision,record):
        self._revision(revision);raw=canonical(record);self._budget(db,len(raw))
        db.execute('INSERT INTO setup_versions_v1 VALUES(?,?,?,?,?)',(key,revision,raw.decode(),digest(record),len(raw)))
        db.execute('UPDATE setup_drafts_v1 SET head=? WHERE id=?',(revision,key))

    def _inputs(self,draft):
        """Bind current staged bytes for later undo/load, without copying anything."""
        from app.references import image_record
        need(not draft['pendingInputs'],'Attach or remove pending local inputs before checkpointing; no browser File bytes are persisted')
        names={}
        for key in ('reference','last_reference'):
            value=draft['recipe']['controls'].get(key)
            if value:names[value]=None
        for row in draft['recipe']['references']:
            if row.get('file'):
                need(not row.get('missing'),'Reattach missing references before checkpointing')
                old=names.get(row['file']);expected=row.get('sha256')
                need(old is None or old==expected,'Conflicting saved reference hashes')
                names[row['file']]=expected
        result=[]
        for name,sha in names.items():
            need(type(name) is str and name==Path(name).name and '\\' not in name,'Invalid staged input name')
            left=image_record(self.studio.experiments/'uploads',name,strict_pixels=True)
            right=image_record(self.studio.comfy_root/'input',name,strict_pixels=True)
            need(left==right and (sha is None or left['sha256']==sha),'A staged input changed or is absent from this backend; reattach explicitly')
            result.append(left)
        return result

    def _graph_identity(self,draft):
        current=[p for p in self.studio.catalog()['presets'] if p['id']==draft['recipe']['preset']]
        need(len(current)==1,'The saved recipe is no longer available')
        _,path=self.studio.graph_for(current[0])
        with path.open('rb') as stream:raw=stream.read(2*1024*1024+1)
        need(len(raw)<=2*1024*1024,'Saved graph exceeds the checkpoint bound')
        observed=hashlib.sha256(raw).hexdigest();expected=draft['templateHash']
        need(expected is None or expected==observed,'The saved graph changed; inspect the revision before loading')
        return observed

    def _check_record(self,record):
        need(record['runtime']==self._runtime(),'Switch explicitly to the recorded backend before loading this revision')
        need(record['inputs']==self._inputs(record['draft']),'Staged input bytes changed; the saved revision was preserved')
        need(record['graph_sha256']==self._graph_identity(record['draft']),'The saved graph changed; old revision retained')

    def check(self,key,revision=None):
        with self.studio.lock:
            saved=self.get(key,revision);self._check_record(saved)
            return {**saved,'inputs_available':True}

    def command(self,value):
        value=validate_command(value);action=value['action'];sha=digest(value)
        # All calls use the same existing runtime lock; no new GPU semaphore.
        with self.studio.lock:
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');scope=self.workspace._check_scope(db,value['workspace_id'])
                old=self._operation(db,value['request_id'])
                if old:
                    if old[0]['request_sha256']!=sha:raise SetupError('setup_request_conflict','Request ID already has different content')
                    return self._result(db,old[1],True)
                key=uuid.uuid5(NAMESPACE,scope+':'+value['request_id']).hex if action=='create' else identifier(value['draft_id'])
                if action!='create':current=self._guard(db,key,value['expected_revision'],value.get('operation_id') if action=='abandon' else None)
                if action=='create':
                    need(db.execute('SELECT COUNT(*) FROM setup_drafts_v1').fetchone()[0]<MAX_DRAFTS,'Setup draft limit reached; retain existing history')
                elif action in ('replace','restore','apply'):self._revision(current['revision']+1)
                need(db.execute('SELECT COUNT(*) FROM setup_operations_v1 WHERE draft_id=?',(key,)).fetchone()[0]<MAX_OPERATIONS,'Setup request history limit reached; retain receipts before starting another draft')
                # Check ample bounded headroom before any copies, not after the side effect.
                self._budget(db,4*1024*1024 if action=='apply' else 512*1024)
                receipt={'request_id':value['request_id'],'draft_id':key,'action':action,'status':'checking',
                         'revision':None,'request_sha256':sha,'created_at':time.time(),'staged':[],'attempting_slot':None,'staging_may_have_occurred':False}
                if action=='abandon':
                    previous=self._operation(db,identifier(value['operation_id']))
                    need(previous is not None and previous[1]['draft_id']==key and previous[1]['status'] in ACTIVE,'No matching pending setup operation to abandon')
                    prior=previous[1];prior.update(status='abandoned',message='Explicitly abandoned; possible staged copies were retained. No revision committed.')
                    self._save_receipt(db,prior,previous[0]['request_sha256'])
                    receipt.update(status='abandoned',operation_id=value['operation_id'],staged=prior['staged'],staging_may_have_occurred=prior['staging_may_have_occurred'])
                elif action in ('create','replace','restore'):
                    if action=='restore':
                        source=self._read(db,key,value['revision']);record={k:source[k] for k in ('draft','inputs','runtime','graph_sha256')}
                        self._check_record(record)
                    else:
                        draft=validate_draft(value['draft']);record={'draft':draft,'inputs':self._inputs(draft),'runtime':self._runtime(),'graph_sha256':self._graph_identity(draft)}
                    revision=1 if action=='create' else current['revision']+1
                    if action=='create':db.execute('INSERT INTO setup_drafts_v1 VALUES(?,0)',(key,))
                    self._append(db,key,revision,record);receipt.update(status='committed',revision=revision)
                self._save_receipt(db,receipt,sha)
                if action!='apply':return self._result(db,receipt)
            return self._apply(value,sha,receipt,current)

    def _progress(self,receipt,sha):
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE');old=self._operation(db,receipt['request_id'])
            need(old and old[0]['request_sha256']==sha and old[1]['status'] in ACTIVE,'Setup operation was superseded; copies retained and draft unchanged')
            self._save_receipt(db,receipt,sha)

    def _apply(self,value,sha,receipt,current):
        try:
            exact=value['proposal_json'];need(type(exact) is str and len(exact.encode())<=1048576,'Supply the exact bounded reviewed proposal JSON')
            need(hashlib.sha256(exact.encode()).hexdigest()==value['approved_proposal_sha256'],'Approval must name the exact reviewed proposal')
            core=decode(exact);report={**core,'proposal_json':exact,'proposal_sha256':value['approved_proposal_sha256']}
            validate_reply(report,core['request'])
            need(canonical(core['before'])==canonical(current['draft']),'Reviewed before-state differs from the shared setup revision')
            runtime=self._runtime();need(current['runtime']==runtime,'Shared draft backend changed; checkpoint deliberately on the intended backend')
            fresh=build_proposal(core['request'],self.studio)
            need(fresh['proposal_sha256']==value['approved_proposal_sha256'],'The proposal context changed; build and review a fresh proposal')
            intent=fresh['intent'];need(intent['backend_id']==runtime['backend_id'],'Switch explicitly to the proposed backend before applying')
            receipt.update(status='staging',approved_proposal_sha256=value['approved_proposal_sha256'])
            self._progress(receipt,sha)
            for source in intent['sources']:
                receipt.update(attempting_slot=source['slot'],staging_may_have_occurred=True);self._progress(receipt,sha)
                uploaded=self.studio.asset_reference(source['asset_id'])
                need(type(uploaded) is dict and uploaded.get('parent_asset')==source['asset_id'],'Staging returned a different source identity')
                from app.references import image_record
                name=uploaded.get('file');need(type(name) is str and name==Path(name).name and '\\' not in name,'Invalid staged reference name')
                # Retain the known filename even if later verification fails.
                row={'file':name,'parent_asset':source['asset_id'],'slot':source['slot'],'role':source['role'],
                     'contribution':source['contribution'],'avoid':source['avoid'],'sha256':source['sha256']}
                receipt['staged'].append(copy.deepcopy(row));self._progress(receipt,sha)
                left=image_record(self.studio.experiments/'uploads',name,strict_pixels=True)
                right=image_record(self.studio.comfy_root/'input',name,strict_pixels=True)
                need(left==right and all(left[k]==source[k] for k in ('sha256','bytes','width','height')),'Staged reference bytes do not match the reviewed source')
                row.update(left);receipt['staged'][-1]=row;receipt['attempting_slot']=None;self._progress(receipt,sha)
            fresh_again=build_proposal(core['request'],self.studio)
            need(fresh_again['proposal_sha256']==fresh['proposal_sha256'] and runtime==self._runtime(),'Source, graph or runtime changed during staging; draft unchanged')
            controls=copy.deepcopy(intent['controls']);board=intent.get('reference_board')
            named=all(x['role_mode']=='prompt-guidance' for x in intent['sources'])
            if board:
                need(all(x['role_mode']=='style-board' for x in intent['sources']),'Mixed board source modes are not supported')
                references=copy.deepcopy(receipt['staged'])
                for index in range(len(references),board['slot_count']):
                    references.append({'slot':index+1,'role':board['roles'][index],'file':None,'pruned':True,'contribution':'','avoid':''})
            else:
                controls['reference']=receipt['staged'][0]['file'];references=copy.deepcopy(receipt['staged']) if named else []
                if not named and len(receipt['staged'])==2:controls['last_reference']=receipt['staged'][1]['file']
            draft={'version':1,'updatedAt':0,'templateHash':intent['template_sha256'],'pendingInputs':[],
                   'recipe':{'preset':intent['preset_id'],'controls':controls,'batch':1,'references':references,
                             'parent_assets':intent['lineage']['parents'],'parent_by_input':intent['lineage']['by_input']}}
            validate_draft(draft)
            record={'draft':draft,'inputs':self._inputs(draft),'runtime':runtime,'graph_sha256':self._graph_identity(draft)}
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE');self.workspace._check_scope(db,value['workspace_id'])
                self._guard(db,current['draft_id'],current['revision'],receipt['request_id'])
                old=self._operation(db,receipt['request_id']);need(old and old[1]['status'] in ACTIVE,'Setup operation no longer owns the draft')
                revision=current['revision']+1;self._append(db,current['draft_id'],revision,record)
                receipt.update(status='committed',revision=revision,previous_revision=current['revision'])
                self._save_receipt(db,receipt,sha);return self._result(db,receipt)
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error,RecursionError) as exc:
            receipt.update(status='failed',message=str(exc)[:500])
            # If storage itself failed, preserve its earlier pending journal rather
            # than falsely certifying failure/rollback to the caller.
            self._progress(receipt,sha)
            with self.workspace.connection() as db:return self._result(db,receipt)
