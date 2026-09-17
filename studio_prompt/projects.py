"""Immutable CreativeIntent documents in AssetWorkspace, not a second executor.

A save records user data and context. It does not authenticate observations,
verify current reference pixels, grant generation authority, or contact a model.
"""
from __future__ import annotations
import copy
import re
import time
import uuid
from .schema import canonical, decode, digest, fields, need, text, validate
from .reference_analysis import validate_report, validate_review

FORMAT='studio.prompt-document/v1'
MAX_PROJECTS=128
MAX_REVISIONS=256
MAX_DOCUMENT_BYTES=256*1024
MAX_HISTORY_BYTES=32*1024*1024
REQUEST_LIMIT=512*1024
PAGE_SIZE=32
NAMESPACE=uuid.UUID('497a9b1b-f50b-4d69-833f-4ef17dc580fa')
FLAGS={'generation_submitted':False,'inference_submitted':False,'execution_authorized':False}


class ProjectError(ValueError):
    def __init__(self,code,message,status=400,**details):
        super().__init__(message);self.code=code;self.status=status;self.details=details
    def response(self):return {'error':str(self),'code':self.code,**self.details,**FLAGS}


def bounded(value,limit):
    raw=canonical(value);need(len(raw)<=limit,'Prompt project exceeds its byte limit')
    return decode(raw),raw


def document(value):
    value,raw=bounded(value,MAX_DOCUMENT_BYTES)
    fields(value,('format','name','profile_id','intent','reference_context'))
    need(value['format']==FORMAT,'Unsupported prompt document format');text(value['name'],120)
    need(type(value['profile_id']) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,95}',value['profile_id']), 'Invalid profile identity')
    intent=copy.deepcopy(value['intent']);need(type(intent) is dict,'Expected CreativeIntent')
    text(intent.get('brief'),4000,empty=True)
    if not intent['brief'].strip():intent['brief']='Pending description'
    validate(intent)
    context=value['reference_context']
    if context is not None:
        fields(context,('analysis','review'))
        validate_report(context['analysis']);validate_review(context['analysis'],context['review'])
    return value


def revision(value):
    # Storage identity bounds are stable, independent of a configured append cap.
    need(type(value) is int and 1<=value<=256,'Invalid prompt revision')
    return value


def project_id(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{32}',value),'Invalid prompt project identity')
    return value


def _locked(current,candidate):
    before,after=current['intent'],candidate['intent']
    need(set(before['locked'])<=set(after['locked']),'Locked fields cannot be silently unlocked; save a deliberate alternative as a new project')
    def at(value,path):
        for part in path.split('.'):
            if part not in value:return [False,None]
            value=value[part]
        return [True,value]
    for lock in before['locked']:
        need(canonical(at(before,lock))==canonical(at(after,lock)), 'Locked field: '+lock)


class PromptProjects:
    def __init__(self,workspace):
        self.workspace=workspace
        with workspace.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS prompt_projects_v1(id TEXT PRIMARY KEY,head INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS prompt_project_revisions_v1(
                    id TEXT NOT NULL REFERENCES prompt_projects_v1(id),revision INTEGER NOT NULL,
                    document_json TEXT NOT NULL,document_sha TEXT NOT NULL,bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL,PRIMARY KEY(id,revision));
                CREATE TABLE IF NOT EXISTS prompt_project_commands_v1(
                    request_id TEXT PRIMARY KEY,command_json TEXT NOT NULL,command_sha TEXT NOT NULL,
                    id TEXT NOT NULL,revision INTEGER NOT NULL,bytes INTEGER NOT NULL,
                    FOREIGN KEY(id,revision) REFERENCES prompt_project_revisions_v1(id,revision));
            ''')

    def _scope(self,db,scope):
        self.workspace._validate_scope(scope)
        return self.workspace._check_scope(db,scope)

    def capabilities(self):
        with self.workspace.connection() as db:
            db.execute('BEGIN');scope=self.workspace._workspace_id(db)
        return {'format':'studio.prompt-projects/v1','workspace_id':scope,'limits':{
            'projects':MAX_PROJECTS,'revisions':MAX_REVISIONS,'document_bytes':MAX_DOCUMENT_BYTES,
            'history_bytes':MAX_HISTORY_BYTES},**FLAGS}

    def _read(self,db,scope,key,number=None):
        project_id(key)
        if number is not None:revision(number)
        row=db.execute('''SELECT r.*,p.head FROM prompt_projects_v1 p JOIN prompt_project_revisions_v1 r
            ON p.id=r.id AND r.revision=COALESCE(?,p.head) WHERE p.id=?''',(number,key)).fetchone()
        if row is None:raise ProjectError('project_not_found','Prompt project or revision not found',404)
        try:
            raw=row['document_json'].encode('utf-8');need(len(raw)<=MAX_DOCUMENT_BYTES,'Stored document exceeds limit')
            doc=document(decode(raw));revision(row['revision']);revision(row['head'])
            need(row['revision']<=row['head'] and len(raw)==row['bytes'] and digest(doc)==row['document_sha'], 'Stored document changed')
        except (ValueError,KeyError,TypeError,RecursionError,AttributeError) as error:
            raise ProjectError('project_storage_invalid','Stored prompt revision failed integrity checks',503) from error
        return {'format':'studio.prompt-project/v1','workspace_id':scope,'id':key,'revision':row['revision'],
                'head_revision':row['head'],'document':doc,'document_sha256':row['document_sha'],
                'source_bytes_verified':False,**FLAGS}

    def get(self,scope,key,number=None):
        with self.workspace.connection() as db:
            db.execute('BEGIN');self._scope(db,scope);return self._read(db,scope,key,number)

    def list(self,scope):
        with self.workspace.connection() as db:
            db.execute('BEGIN');self._scope(db,scope)
            rows=db.execute('''SELECT p.id,p.head,r.document_json,r.document_sha,r.bytes FROM prompt_projects_v1 p
                LEFT JOIN prompt_project_revisions_v1 r ON p.id=r.id AND r.revision=p.head
                ORDER BY p.id LIMIT ?''',(MAX_PROJECTS+1,)).fetchall()
            need(len(rows)<=MAX_PROJECTS,'Prompt project count exceeds limit')
            result=[]
            for row in rows:
                item={'id':row['id'],'revision':row['head'],'document_sha256':row['document_sha'],
                      'name':None,'unreadable':False}
                raw=None
                try:
                    raw=row['document_json'].encode('utf-8')
                    need(len(raw)<=MAX_DOCUMENT_BYTES,'Stored document exceeds limit')
                    doc=document(decode(raw));project_id(row['id']);revision(row['head'])
                    need(len(raw)==row['bytes'] and digest(doc)==row['document_sha'],'Stored document changed')
                    item['name']=doc['name']
                except (ValueError,KeyError,TypeError,RecursionError,AttributeError):
                    item['unreadable']=True
                    # Recover only a bounded display hint, never readability or authority.
                    if raw is not None and len(raw)<=MAX_DOCUMENT_BYTES:
                        try:
                            parsed=decode(raw)
                            if isinstance(parsed,dict):
                                text(parsed.get('name'),120);item['name']=parsed['name']
                        except (ValueError,KeyError,TypeError,RecursionError,AttributeError):
                            pass
                result.append(item)
        return {'workspace_id':scope,'projects':result,**FLAGS}

    def history(self,scope,key,before=None):
        if before is not None:revision(before)
        with self.workspace.connection() as db:
            db.execute('BEGIN');self._scope(db,scope);current=self._read(db,scope,key)
            rows=db.execute('''SELECT revision,document_sha,created_at FROM prompt_project_revisions_v1
                WHERE id=? AND revision<? ORDER BY revision DESC LIMIT ?''',
                (key,before or 257,PAGE_SIZE+1)).fetchall()
            page=[{'revision':row['revision'],'document_sha256':row['document_sha'],'created_at':row['created_at']} for row in rows[:PAGE_SIZE]]
        return {'workspace_id':scope,'id':key,'head_revision':current['head_revision'],'revisions':page,
                'next_before':page[-1]['revision'] if len(rows)>PAGE_SIZE else None,**FLAGS}

    def _receipt(self,db,scope,request_id,sha=None):
        self.workspace.request_id(request_id)
        row=db.execute('SELECT * FROM prompt_project_commands_v1 WHERE request_id=?',(request_id,)).fetchone()
        if row is None:return None
        try:
            raw=row['command_json'].encode('utf-8');need(len(raw)<=REQUEST_LIMIT and len(raw)==row['bytes'],'Invalid stored request size')
            command=decode(raw);fields(command,('action','request'))
            need(digest(command)==row['command_sha'],'Stored command changed')
            request=self._request(command['action'],command['request']);need(request['request_id']==request_id and request['workspace_id']==scope,'Stored command scope changed')
            expected=1 if command['action']=='create' else request['expected_revision']+1
            need(type(row['revision']) is int and row['revision']==expected,'Command revision association changed')
            if command['action']!='create':need(request['id']==row['id'],'Command project identity changed')
            else:need(uuid.uuid5(NAMESPACE,scope+':'+request_id).hex==row['id'],'Command project identity changed')
            result=self._read(db,scope,row['id'],row['revision'])
            if command['action'] in ('create','save'):
                need(canonical(request['document'])==canonical(result['document']),'Command document changed')
            else:
                restored=self._read(db,scope,row['id'],request['restore_revision'])
                need(restored['document_sha256']==result['document_sha256'],'Restored revision changed')
        except (ValueError,KeyError,TypeError,RecursionError,AttributeError) as error:
            raise ProjectError('project_storage_invalid','Stored prompt command failed integrity checks',503) from error
        if sha is not None and sha!=row['command_sha']:
            raise ProjectError('request_conflict','Request ID already belongs to different content',409)
        return {'format':'studio.prompt-command/v1','workspace_id':scope,'request_id':request_id,
                'action':command['action'],'request':request,'request_sha256':row['command_sha'],
                'project':result,'replayed':True,**FLAGS}

    def status(self,scope,request_id):
        with self.workspace.connection() as db:
            db.execute('BEGIN');self._scope(db,scope);result=self._receipt(db,scope,request_id)
            if result is None:raise ProjectError('request_unknown','No saved receipt for this request; nothing was retried',404)
            return result

    def _request(self,action,value):
        need(action in ('create','save','restore'),'Unknown prompt project command')
        value,raw=bounded(value,REQUEST_LIMIT-64)
        required=('workspace_id','request_id')+ (('document',) if action=='create' else
            ('id','expected_revision','document' if action=='save' else 'restore_revision'))
        fields(value,required);self.workspace.request_id(value['request_id'])
        if action!='create':project_id(value['id']);revision(value['expected_revision'])
        if action=='restore':revision(value['restore_revision'])
        else:document(value['document'])
        return value

    def command(self,action,value):
        value=self._request(action,value)
        command={'action':action,'request':value};raw=canonical(command);sha=digest(command)
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE');scope=self._scope(db,value['workspace_id'])
            previous=self._receipt(db,scope,value['request_id'],sha)
            if previous is not None:return previous
            if action=='create':
                need(db.execute('SELECT COUNT(*) FROM prompt_projects_v1').fetchone()[0]<MAX_PROJECTS,'Prompt project count limit reached')
                key=uuid.uuid5(NAMESPACE,scope+':'+value['request_id']).hex;number=1;doc=value['document']
                db.execute('INSERT INTO prompt_projects_v1 VALUES (?,?)',(key,number))
            else:
                key=value['id'];current=self._read(db,scope,key)
                if current['revision']!=value['expected_revision']:
                    raise ProjectError('revision_conflict','This brief changed on the server; inspect it before saving',409,
                        current_revision=current['revision'],id=key)
                number=current['revision']+1
                doc=value['document'] if action=='save' else self._read(db,scope,key,value['restore_revision'])['document']
                _locked(current['document'],doc)
            need(number<=MAX_REVISIONS,'Prompt revision limit reached; no history was removed')
            data=canonical(doc)
            used=db.execute('''SELECT (SELECT COALESCE(SUM(bytes),0) FROM prompt_project_revisions_v1)
                                +(SELECT COALESCE(SUM(bytes),0) FROM prompt_project_commands_v1)''').fetchone()[0]
            need(used+len(data)+len(raw)<=MAX_HISTORY_BYTES,'Prompt history byte limit reached; no receipts were removed')
            db.execute('INSERT INTO prompt_project_revisions_v1 VALUES (?,?,?,?,?,?)',(key,number,data.decode('utf-8'),digest(doc),len(data),time.time()))
            db.execute('INSERT INTO prompt_project_commands_v1 VALUES (?,?,?,?,?,?)',(value['request_id'],raw.decode('utf-8'),sha,key,number,len(raw)))
            db.execute('UPDATE prompt_projects_v1 SET head=? WHERE id=?',(number,key))
            result=self._receipt(db,scope,value['request_id']);result['replayed']=False;return result
