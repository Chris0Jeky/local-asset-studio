"""Explicit setup authoring and read-only request recovery; never retries writes."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from .client import ClientError, read_response
from .core import canonical, decode, digest, need
from .commands import identifier
from .setup_drafts import PREFIX,MAX_COMMAND,MAX_REVISIONS,validate_command
from .setup_history import FLAGS,MAX_PAGE,MAX_READ_BYTES,MAX_EXPORT_BYTES,recorded_time


def _history_integer(value,maximum=MAX_REVISIONS):
    need(type(value) is int and 1<=value<=maximum,'Invalid bounded history integer')
    return value


def _history_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


class UnknownSetupOutcome(ValueError):
    def __init__(self,request_id,message):
        self.request_id=request_id
        super().__init__(message+' Inspect request '+request_id+'; no write was retried.')


def validate_record(result):
    need(type(result) is dict and result.get('generation_submitted') is False,'Invalid setup response')
    if 'draft' in result:
        from .setup_proposal import validate_draft
        validate_draft(result['draft']);record=decode(result['record_json'])
        need(digest(record)==result['record_sha256'] and all(record[k]==result[k] for k in ('draft','inputs','runtime'))
             and digest(result['draft'])==result['draft_sha256'],'Setup revision identity does not match its contents')
        need(type(result.get('revision')) is int and type(result.get('head_revision')) is int
             and 1<=result['revision']<=result['head_revision'],'Invalid setup revision')
    if 'receipt_json' in result:
        receipt=decode(result['receipt_json'])
        need(digest(receipt)==result.get('receipt_sha256') and all(result.get(k)==v for k,v in receipt.items()),'Setup receipt does not match its projection')
    return result


class SetupDraftClient:
    def __init__(self,transport):self.transport=transport
    def _request(self,path,value=None):
        try:return self.transport(path,value) if value is not None else self.transport(path)
        except HTTPError as exc:
            try:
                with exc:result=decode(read_response(exc,65536))
            except (ValueError,OSError,HTTPException):
                result={'error':'Unverified setup read error; no write was submitted' if value is None
                        else 'Unverified setup error; inspect the original request receipt'}
            raise ClientError(exc.code,result) from exc
    def _history_read(self,key,action,workspace_id,expected_head,**values):
        identifier(key);need(key not in ('.','..','requests'),'Invalid setup history identifier')
        need(type(workspace_id) is str and re.fullmatch('[a-f0-9]{32}',workspace_id),'Invalid Workspace identity')
        query={'workspace_id':workspace_id,**{k:v for k,v in values.items() if v is not None}}
        if expected_head is not None:query['expected_head']=_history_integer(expected_head)
        result=self._request(PREFIX+'/'+key+'/'+action+'?'+urlencode(query))
        need(type(result) is dict and len(json.dumps(result,allow_nan=False).encode('utf-8'))<=MAX_READ_BYTES,'Invalid or oversized setup history response')
        kind='page' if action=='history' else action
        need(result.get('format')=='studio.setup-history-'+kind+'/v2'
             and result.get('workspace_id')==workspace_id and result.get('draft_id')==key
             and all(result.get(k) is v for k,v in FLAGS.items()),'Setup history response belongs to another read')
        head=_history_integer(result.get('head_revision'))
        need((expected_head is None or head==expected_head) and _history_sha(result.get('head_record_sha256')),'Setup history head does not match')
        return result
    def history(self,key: str,*,workspace_id: str,limit: int=MAX_PAGE,
                before_revision: int | None=None,expected_head: int | None=None) -> dict:
        """Read one bounded page; continue only against its explicitly observed head."""
        _history_integer(limit,MAX_PAGE)
        if before_revision is not None:
            _history_integer(before_revision)
            need(expected_head is not None and before_revision<=_history_integer(expected_head),'A continuation requires the observed expected head')
        result=self._history_read(key,'history',workspace_id,expected_head,limit=limit,before_revision=before_revision)
        rows=result.get('revisions');need(type(rows) is list and len(rows)<=limit and type(result.get('limit')) is int and result['limit']==limit,'Invalid setup history page')
        start=before_revision if before_revision is not None else result['head_revision']+1
        expected=list(range(start-1,max(0,start-1-limit),-1));observed=[]
        for row in rows:
            need(type(row) is dict and recorded_time(row.get('recorded_at')),'Invalid setup history summary');revision=_history_integer(row.get('revision'))
            observed.append(revision)
        need(observed==expected,'Setup history page is incomplete or not contiguous')
        cursor=result.get('next_before_revision')
        expected_cursor=expected[-1] if expected and expected[-1]>1 else None
        need('next_before_revision' in result and cursor==expected_cursor and (cursor is None or type(cursor) is int),'Invalid setup history continuation')
        return result
    def compare(self,key: str,left: int,right: int,*,workspace_id: str,expected_head: int | None=None) -> dict:
        """Compare retained revisions without checking dependencies or staging inputs."""
        result=self._history_read(key,'compare',workspace_id,expected_head,left=_history_integer(left),right=_history_integer(right))
        need(type(result.get('left_revision')) is int and result['left_revision']==left
             and type(result.get('right_revision')) is int and result['right_revision']==right
             and max(left,right)<=result['head_revision'] and type(result.get('sections')) is list
             and _history_sha(result.get('left_record_sha256')) and _history_sha(result.get('right_record_sha256')),'Invalid setup history comparison')
        return result
    def export_revision(self,key: str,revision: int,*,workspace_id: str,expected_head: int | None=None) -> dict:
        """Return hash-bound inspection metadata with no import or execution authority."""
        _history_integer(revision)
        result=self._history_read(key,'export',workspace_id,expected_head,revision=revision)
        raw=result.get('export_json');need(type(raw) is str and len(raw.encode('utf-8'))<=MAX_EXPORT_BYTES,'Invalid setup history export bytes')
        value=decode(raw)
        need(type(value) is dict and canonical(value)==raw.encode('utf-8') and canonical(value)==canonical(result.get('export'))
             and digest(value)==result.get('export_sha256') and type(result.get('export_bytes')) is int
             and result['export_bytes']==len(raw.encode('utf-8')),'Setup inspection export identity does not match its contents')
        need(value.get('format')=='studio.setup-revision-inspection/v2' and value.get('workspace_id')==workspace_id
             and value.get('draft_id')==key and type(value.get('revision')) is int and value['revision']==revision
             and revision<=result['head_revision'] and value.get('authority')=='none' and digest(value.get('draft'))==value.get('draft_sha256')
             and all(value.get(k) is v for k,v in FLAGS.items()),'Setup inspection export belongs to another read')
        return result
    def list(self):return self._request(PREFIX)
    def get(self,key,revision=None):
        path=PREFIX+'/'+identifier(key)
        if revision is not None:
            need(type(revision) is int and 1<=revision<=256,'Invalid setup revision');path+='/revisions/'+str(revision)
        return validate_record(self._request(path))
    def check(self,key,revision):
        need(type(revision) is int and 1<=revision<=256,'Invalid setup revision')
        return validate_record(self._request(PREFIX+'/'+identifier(key)+'/check/'+str(revision)))
    def recover(self,key):
        result=validate_record(self._request(PREFIX+'/requests/'+identifier(key)))
        need(result.get('request_id')==key,'Receipt belongs to another request')
        return result
    def command(self,value):
        q=validate_command(value)
        try:
            r=validate_record(self._request(PREFIX,q))
            need(r.get('request_id')==q['request_id'] and r.get('workspace_id')==q['workspace_id']
                 and r.get('action')==q['action'] and r.get('request_sha256')==digest(q),'Reply belongs to another setup request')
            need(r.get('status') in ('committed','failed','checking','staging','abandoned'),'Unknown setup operation state')
            if q['action']!='create':need(r.get('draft_id')==q['draft_id'],'Reply belongs to another setup draft')
            if r['status']=='committed':
                need('draft' in r and r['revision']==(1 if q['action']=='create' else q['expected_revision']+1),'Committed setup has the wrong revision')
            return r
        except ClientError as exc:
            if exc.status>=500:raise UnknownSetupOutcome(q['request_id'],'Setup server failure may follow a committed write: '+str(exc)) from exc
            raise
        except (ValueError,KeyError,TypeError,OSError,HTTPException) as exc:
            raise UnknownSetupOutcome(q['request_id'],'Setup result is unknown: '+str(exc)) from exc
    def create(self,draft,*,workspace_id,request_id):
        return self.command({'action':'create','workspace_id':workspace_id,'request_id':request_id,'draft':draft})
    def replace(self,key,draft,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'replace','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,'draft':draft})
    def apply(self,key,proposal,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'apply','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,
                             'proposal_json':proposal['proposal_json'],'approved_proposal_sha256':proposal['proposal_sha256']})
    def restore(self,key,revision,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'restore','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,'revision':revision})


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit shared setup drafts. Apply copies references but never starts generation.')
    parser.add_argument('--url',default='http://127.0.0.1:8191')
    subs=parser.add_subparsers(dest='action',required=True)
    subs.add_parser('list');subs.add_parser('command').add_argument('file',type=Path)
    subs.add_parser('recover').add_argument('request_id')
    get=subs.add_parser('get');get.add_argument('draft_id');get.add_argument('--revision',type=int)
    for name in ('history','compare','export'):
        read=subs.add_parser(name);read.add_argument('draft_id');read.add_argument('--workspace-id',required=True)
        read.add_argument('--expected-head',type=int)
        if name=='history':read.add_argument('--limit',type=int,default=MAX_PAGE);read.add_argument('--before-revision',type=int)
        elif name=='compare':read.add_argument('left',type=int);read.add_argument('right',type=int)
        else:read.add_argument('revision',type=int)
    args=parser.parse_args(argv);q=None;sent=False
    try:
        from .client import Client
        c=SetupDraftClient(Client(args.url).request)
        if args.action=='command':
            with args.file.open('rb') as stream:raw=stream.read(MAX_COMMAND+1)
            need(len(raw)<=MAX_COMMAND,'Setup command exceeds 1 MiB');q=validate_command(decode(raw));sent=True;r=c.command(q)
        elif args.action=='recover':r=c.recover(args.request_id)
        elif args.action=='get':r=c.get(args.draft_id,args.revision)
        elif args.action=='history':r=c.history(args.draft_id,workspace_id=args.workspace_id,limit=args.limit,before_revision=args.before_revision,expected_head=args.expected_head)
        elif args.action=='compare':r=c.compare(args.draft_id,args.left,args.right,workspace_id=args.workspace_id,expected_head=args.expected_head)
        elif args.action=='export':r=c.export_revision(args.draft_id,args.revision,workspace_id=args.workspace_id,expected_head=args.expected_head)
        else:r=c.list()
        print(json.dumps(r,ensure_ascii=False,allow_nan=False))
        return 0 if r.get('status','committed')=='committed' else 3
    except (ValueError,OSError,HTTPException) as exc:
        unknown=isinstance(exc,UnknownSetupOutcome) or sent and not isinstance(exc,ClientError)
        error={'error':str(exc),'code':'setup_outcome_unknown' if unknown else getattr(exc,'code','invalid_setup_request'),'generation_submitted':False}
        if q:error['request_id']=q['request_id'];error['recovery']='Use recover with this original request ID. No write is replayed.'
        print(json.dumps(error),file=sys.stderr);return 3 if unknown else 2


if __name__=='__main__':raise SystemExit(main())
